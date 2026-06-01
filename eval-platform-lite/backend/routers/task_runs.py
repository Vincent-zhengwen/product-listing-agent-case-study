import uuid, json, os, re, sqlite3, mimetypes
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, BackgroundTasks, Body, Query
from fastapi.responses import FileResponse
from database import get_db
from models import TaskRunCreate, AgentCallback, HumanAnnotation
from eval_runner import run_evals_for_result
from graders_v2.registry_v2 import get_grader_meta_v2
from project_paths import AGENT_DB, PROJECT_ROOT
from source_snapshots import get_case_snapshot, normalize_images, upsert_case_snapshot

router = APIRouter()

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8000")
SELF_URL = os.getenv("SELF_URL", "http://localhost:8001")
USE_MOCK = os.getenv("USE_MOCK_AGENT", "true").lower() == "true"

DEFAULT_FAILURE_CODES = [
    ("blank-main-image", "主图空白/主体不可见", "image", "blocker", "主图缺少可识别产品主体，通常来自渲染或分割失败。", "render", "image_render_pipeline", "重新渲染对应主图，并在最终自检中读取真实图片像素。"),
    ("duplicate-main-image", "主图重复", "image", "blocker", "5 张主图缺少角度/场景差异，图片规划或渲染复用出错。", "image_plan", "image_plan_diversity", "强制 5 张主图角色差异，并在渲染后做 pHash 去重和重试。"),
    ("low-resolution-image", "主图分辨率不足", "image", "blocker", "图片未达到平台发布尺寸要求。", "render", "image_render_pipeline", "统一输出尺寸 contract，保存前检查宽高。"),
    ("source-snapshot-missing", "源页快照缺失", "grounding", "warning", "source title/attributes/images/raw_data 不完整，grounding 评测可信度下降。", "source_fetch", "source_snapshot_persistence", "把源页爬取结果持久化为 case snapshot package。"),
    ("fabricated-fact", "文案疑似虚构事实", "grounding", "blocker", "标题、卖点或正文包含源页无法支撑的具体 claim。", "copy", "source_grounding_missing", "生成文案前先抽取 source facts，具体 claim 必须引用 source evidence。"),
    ("b2b-copy-not-converted", "B2B 话术未转 C 端", "conversion", "warning", "文案停留在批发/参数描述，没有转成购买理由。", "strategy", "consumer_positioning_gap", "把卖点组织成场景、痛点和可观察证据，而不是复述批发参数。"),
    ("title-pollution", "标题污染", "conversion", "warning", "标题含批发、工厂、乱码、SKU 或不适合前台展示的词。", "copy", "platform_copy_contract", "标题生成后做平台污染词和 SKU 串检查。"),
    ("trace-missing", "Trace 缺失/不完整", "process", "warning", "无法定位 Agent 哪个阶段失败。", "executor", "trace_contract_missing", "callback 必须回传 source/fact/copy/image/render/qa 关键阶段。"),
    ("artifact-unreadable", "产物文件不可读", "process", "warning", "output 指向的图片路径不存在或无法打开。", "persistence", "artifact_persistence", "callback 返回 local_path/output_path，并保证路径在评测环境可解析。"),
    ("qa-did-not-see-final-artifact", "自检未看最终产物", "process", "warning", "QA/Judge 阶段没有读取最终 main_images/detail_image。", "qa", "judge_not_grounded_in_artifact", "JudgeAgent 必须读取最终图片文件，而不是只看内部计划。"),
]


def _ensure_eval_center_tables(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS case_ai_analyses (
        id TEXT PRIMARY KEY,
        run_result_id TEXT REFERENCES run_results(id) ON DELETE CASCADE,
        analysis_json TEXT DEFAULT '{}',
        summary TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS failure_codes (
        code TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        category TEXT DEFAULT '',
        severity TEXT DEFAULT 'warning',
        description TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS case_failure_codes (
        id TEXT PRIMARY KEY,
        run_result_id TEXT REFERENCES run_results(id) ON DELETE CASCADE,
        code TEXT REFERENCES failure_codes(code),
        source TEXT DEFAULT 'human',
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(run_result_id, code)
    );
    """)
    existing_cols = {
        row[1] for row in db.execute("PRAGMA table_info(failure_codes)").fetchall()
    }
    for name in ("stage", "root_cause", "suggested_fix"):
        if name not in existing_cols:
            db.execute(f"ALTER TABLE failure_codes ADD COLUMN {name} TEXT DEFAULT ''")
    for code, label, category, severity, description, stage, root_cause, suggested_fix in DEFAULT_FAILURE_CODES:
        db.execute(
            "INSERT INTO failure_codes (code, label, category, severity, description, stage, root_cause, suggested_fix) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(code) DO UPDATE SET "
            "label=excluded.label, category=excluded.category, severity=excluded.severity, "
            "description=excluded.description, stage=excluded.stage, root_cause=excluded.root_cause, "
            "suggested_fix=excluded.suggested_fix",
            (code, label, category, severity, description, stage, root_cause, suggested_fix),
        )


def _json_loads(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _source_snapshot(source_url: str, test_case_id: str = "", db=None) -> dict:
    if db is not None and test_case_id:
        snapshot = get_case_snapshot(db, test_case_id)
        if snapshot:
            return snapshot
    if not source_url or not Path(AGENT_DB).exists():
        return {}
    try:
        sdb = sqlite3.connect(AGENT_DB)
        sdb.row_factory = sqlite3.Row
        row = sdb.execute(
            "SELECT id, platform, title, price, url, image_url, supplier, raw_data, "
            "detail_url, location, keyword, attributes, raw_attributes, images, "
            "estimated_selling_price, estimated_profit, profit_margin, supplier_tier, "
            "supports_dropshipping, shipping_promise, transactions_30d, verified "
            "FROM sources WHERE url=? ORDER BY id DESC LIMIT 1",
            (source_url,),
        ).fetchone()
        sdb.close()
    except Exception:
        return {}
    if not row:
        return {}

    raw_data = _json_loads(row["raw_data"], {})
    attrs = _json_loads(row["attributes"], {})
    images = normalize_images(row["images"], row["image_url"] or raw_data.get("image_url", ""))
    image_url = row["image_url"] or raw_data.get("image_url") or ""

    return {
        "id": row["id"],
        "platform": row["platform"],
        "title": row["title"] or raw_data.get("title", ""),
        "price": row["price"] or raw_data.get("price"),
        "url": row["url"] or source_url,
        "detail_url": row["detail_url"] or raw_data.get("detail_url", ""),
        "supplier": row["supplier"] or raw_data.get("supplier", ""),
        "location": row["location"] or raw_data.get("location", ""),
        "keyword": row["keyword"] or raw_data.get("keyword", ""),
        "attributes": attrs,
        "raw_attributes": row["raw_attributes"] or "",
        "images": images,
        "raw_data": raw_data,
        "business": {
            "estimated_selling_price": row["estimated_selling_price"] or raw_data.get("estimated_selling_price"),
            "estimated_profit": row["estimated_profit"] or raw_data.get("estimated_profit"),
            "profit_margin": row["profit_margin"] or raw_data.get("profit_margin"),
            "supplier_tier": row["supplier_tier"] or raw_data.get("supplier_tier"),
            "supports_dropshipping": bool(row["supports_dropshipping"] or raw_data.get("supports_dropshipping")),
            "shipping_promise": row["shipping_promise"] or raw_data.get("shipping_promise"),
            "transactions_30d": row["transactions_30d"] or raw_data.get("transactions_30d"),
            "verified": bool(row["verified"] or raw_data.get("verified")),
        },
        "completeness": {
            "score": sum([
                10 if row["url"] or source_url else 0,
                20 if row["title"] or raw_data.get("title") else 0,
                25 if attrs else 0,
                25 if images or image_url else 0,
                15 if raw_data else 0,
                5 if row["platform"] else 0,
            ]),
            "attributes_count": len(attrs),
            "images_count": len(images),
            "raw_data_available": bool(raw_data),
        },
    }


def _image_local_path(img: dict) -> str:
    if not isinstance(img, dict):
        return ""
    for key in ("local_path", "output_path", "path"):
        value = img.get(key) or ""
        if value and Path(value).exists():
            return value
    return ""


def _image_preview(img: dict) -> dict:
    info = dict(img) if isinstance(img, dict) else {}
    path = _image_local_path(info)
    if path:
        info["artifact_url"] = f"/api/tasks/analysis/artifact-image?path={quote(path)}"
        try:
            from PIL import Image
            with Image.open(path) as im:
                info["width"], info["height"] = im.size
                info["format"] = im.format
                info["readable"] = True
        except Exception as exc:
            info["readable"] = False
            info["read_error"] = str(exc)[:160]
    else:
        info["readable"] = False
        if info.get("url", "").startswith("http"):
            info["artifact_url"] = info["url"]
    return info


def _enrich_images(output: dict) -> dict:
    output = dict(output or {})
    output["main_images"] = [_image_preview(img) for img in output.get("main_images", []) or []]
    if output.get("detail_image"):
        output["detail_image"] = _image_preview(output["detail_image"])
    output["detail_images"] = [_image_preview(img) for img in output.get("detail_images", []) or []]
    return output


def _parse_score(row) -> dict:
    d = dict(row)
    reason_json = _json_loads(d.get("reason"), {})
    if not isinstance(reason_json, dict):
        reason_json = {"critique": str(d.get("reason") or "")}
    d["reason_json"] = reason_json
    d["label"] = reason_json.get("label") or d["grader_id"]
    d["harness_layer"] = reason_json.get("harness_layer") or "outcome_verification"
    d["target"] = reason_json.get("target") or "output"
    d["stage"] = reason_json.get("stage") or "final_artifact"
    d["calibration"] = reason_json.get("calibration") or "trusted"
    d["score_bucket"] = reason_json.get("score_bucket") or "publishability"
    d["requires_human_review"] = bool(reason_json.get("requires_human_review"))
    d["failures"] = reason_json.get("failures") or []
    d["critique"] = reason_json.get("critique") or ""
    return d


def _layer_summary(scores: list[dict]) -> dict:
    layers = ["run_validity", "outcome_verification", "grounding", "conversion_quality", "listing_quality", "process_quality"]
    summary = {}
    for layer in layers:
        items = [s for s in scores if s.get("harness_layer") == layer]
        judged = [s for s in items if s.get("verdict") in {"pass", "fail"}]
        failed = [s for s in judged if s.get("verdict") == "fail"]
        provisional = [s for s in failed if s.get("calibration") != "trusted" or s.get("requires_human_review")]
        summary[layer] = {
            "total": len(items),
            "judged": len(judged),
            "pass": len([s for s in judged if s.get("verdict") == "pass"]),
            "fail": len(failed),
            "skipped": len([s for s in items if s.get("verdict") == "skipped"]),
            "trusted_blockers": len([
                s for s in failed
                if s.get("severity") == "blocker" and s.get("calibration") == "trusted"
            ]),
            "provisional_blockers": len([
                s for s in provisional if s.get("severity") == "blocker"
            ]),
        }
        summary[layer]["pass_rate"] = round(summary[layer]["pass"] / len(judged) * 100) if judged else None
    return summary


def _source_text(source: dict) -> str:
    parts = [
        source.get("title", ""),
        json.dumps(source.get("attributes") or {}, ensure_ascii=False),
        json.dumps(source.get("raw_data") or {}, ensure_ascii=False),
        source.get("raw_attributes", ""),
    ]
    return "\n".join(str(p) for p in parts if p)


def _extract_claims(output: dict, source: dict) -> list[dict]:
    source_text = _source_text(source)
    claims = []

    def add_claim(text: str, field: str):
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        if not text or len(text) < 2:
            return
        has_specific = bool(re.search(r"\d|cm|mm|kg|g|ml|w|led|usb|pp|abs|玻璃|陶瓷|木|藤条|无火|三色|四色|多色", text, re.I))
        if not has_specific:
            return
        key_terms = [t for t in re.split(r"[，,。；;、\s]+", text) if len(t) >= 2][:4]
        supported_terms = [t for t in key_terms if t and t in source_text]
        if supported_terms:
            status = "supported"
        elif source_text:
            status = "needs_review"
        else:
            status = "no_source"
        claims.append({
            "field": field,
            "text": text[:160],
            "status": status,
            "supported_terms": supported_terms,
        })

    add_claim(output.get("title", ""), "title")
    for idx, sp in enumerate(output.get("selling_points", []) or []):
        add_claim(sp, f"selling_points[{idx}]")
    for idx, line in enumerate(re.split(r"[\n。]", output.get("body_copy", "") or "")):
        add_claim(line, f"body_copy[{idx}]")
    for key, value in (output.get("attributes") or {}).items():
        add_claim(f"{key}: {value}", f"attributes.{key}")

    return claims[:40]


def _recommend_codes(scores: list[dict]) -> list[str]:
    codes = set()
    for score in scores:
        if score.get("verdict") != "fail":
            continue
        gid = score.get("grader_id")
        if gid == "image_blank_detection":
            codes.add("blank-main-image")
        elif gid == "image_duplicate_main":
            codes.add("duplicate-main-image")
        elif gid == "image_resolution":
            codes.add("low-resolution-image")
        elif gid == "source_snapshot_available":
            codes.add("source-snapshot-missing")
        elif gid == "copy_factual_grounding":
            codes.add("fabricated-fact")
        elif gid in {"title_no_pollution", "title_no_template"}:
            codes.add("title-pollution")
        elif gid in {"selling_point_evidence", "body_copy_quality"}:
            codes.add("b2b-copy-not-converted")
        elif gid == "trace_completeness":
            codes.add("trace-missing")
        elif gid == "artifact_readability":
            codes.add("artifact-unreadable")
        elif gid == "self_check_final_artifact_seen":
            codes.add("qa-did-not-see-final-artifact")
    return sorted(codes)


def _heuristic_case_analysis(result: dict, scores: list[dict], source: dict, output: dict) -> dict:
    failed = [s for s in scores if s.get("verdict") == "fail"]
    skipped = [s for s in scores if s.get("verdict") == "skipped"]
    by_stage = {}
    by_layer = {}
    for s in failed:
        by_stage[s.get("stage", "unknown")] = by_stage.get(s.get("stage", "unknown"), 0) + 1
        by_layer[s.get("harness_layer", "unknown")] = by_layer.get(s.get("harness_layer", "unknown"), 0) + 1

    if result.get("status") not in {"success", "completed"}:
        root_cause = "executor_or_callback"
        summary = "这次 trial 不是可信成功终态，优先检查 Agent 执行状态机和 callback。"
    elif any(
        s.get("harness_layer") == "run_validity"
        and s.get("verdict") == "fail"
        and s.get("severity") == "blocker"
        for s in scores
    ):
        root_cause = "harness_or_persistence"
        summary = "产物可见但评测可信度受影响，source snapshot、artifact 或 trace 有缺口。"
    elif any(s.get("stage") == "render" and s.get("verdict") == "fail" for s in scores):
        root_cause = "image_render_pipeline"
        summary = "主要失败集中在图片渲染/产物质量，优先排查 ImagePlanner、Pillow compose、素材路径和最终自检。"
    elif any(s.get("harness_layer") == "grounding" and s.get("verdict") == "fail" for s in scores):
        root_cause = "source_grounding"
        summary = "主要风险来自 source grounding，文案或图片判断缺少稳定 source 依据。"
    elif any(s.get("stage") == "copy" and s.get("verdict") == "fail" for s in scores):
        root_cause = "copy_generation"
        summary = "主要失败集中在标题/正文/卖点，优先检查 CopyAgent 的平台规则和 B2B 到 C 端转化 prompt。"
    elif failed:
        root_cause = "mixed_quality_regression"
        summary = "存在多个维度失败，需要从最高严重级别的 grader evidence 开始逐项定位。"
    else:
        root_cause = "no_blocking_issue_detected"
        summary = "自动评测没有发现明确失败；建议人工重点确认图片观感和关键 claim 是否真实。"

    suggested_fix = {
        "executor_or_callback": "先保证 run_result.status、output、trace、agent_error 四个字段一致，失败 trial 不进入发布门槛判断。",
        "harness_or_persistence": "补齐 source title/attributes/images/raw_data，并确保 callback 返回 local_path/output_path 和关键阶段 trace。",
        "image_render_pipeline": "打开失败图片，核对源图、裁剪/分割、文字叠加和 stitched detail 图；修复后用同类图片 case 回归。",
        "source_grounding": "把 source facts 固化为结构化 snapshot，要求文案中的具体参数都能回指 source evidence。",
        "copy_generation": "把 prompt 从参数复述改成“场景 + 可观察特征 + 购买理由”，并加入平台标题长度/污染词检查。",
        "mixed_quality_regression": "按 trusted blocker、provisional blocker、warning 的顺序处理，不要被未校准信号牵着走。",
        "no_blocking_issue_detected": "进入人工审核，确认主图点击欲、卖点可信度和参考竞品 parity。",
    }[root_cause]

    return {
        "summary": summary,
        "root_cause": root_cause,
        "suggested_fix": suggested_fix,
        "rerun_scope": {
            "same_case": True,
            "same_category": result.get("category") or "",
            "focus_stages": sorted(by_stage, key=by_stage.get, reverse=True)[:4],
            "recommended_failure_codes": _recommend_codes(scores),
        },
        "signals": {
            "failed_graders": [s.get("grader_id") for s in failed],
            "skipped_graders": [s.get("grader_id") for s in skipped],
            "failures_by_stage": by_stage,
            "failures_by_layer": by_layer,
            "source_snapshot_available": bool(source),
            "main_image_count": len(output.get("main_images", []) or []),
        },
    }


def _expand_platforms(platform: str):
    if platform == "all":
        return ["taobao", "douyin", "xiaohongshu"]
    return [platform]


def _get_cases(db, dataset_id, filter_category=None, filter_difficulty=None):
    sql = "SELECT * FROM test_cases WHERE dataset_id=?"
    params = [dataset_id]
    if filter_category:
        sql += " AND category=?"; params.append(filter_category)
    if filter_difficulty:
        sql += " AND difficulty=?"; params.append(filter_difficulty)
    return db.execute(sql, params).fetchall()


def enrich_run(row, db):
    if not row:
        return None
    d = dict(row)
    scores = db.execute(
        "SELECT es.* FROM eval_scores es "
        "JOIN run_results rr ON rr.id = es.run_result_id "
        "WHERE rr.task_run_id=?",
        (d["id"],)
    ).fetchall()
    parsed = [_parse_score(s) for s in scores]
    summary = {}
    for score in parsed:
        key = (
            score.get("severity") or "",
            score.get("verdict") or "",
            score.get("harness_layer") or "",
            score.get("calibration") or "",
            score.get("grader_id") or "",
        )
        summary[key] = summary.get(key, 0) + 1
    d["score_summary"] = [
        {
            "severity": severity,
            "verdict": verdict,
            "harness_layer": layer,
            "calibration": calibration,
            "grader_id": grader_id,
            "cnt": cnt,
        }
        for (severity, verdict, layer, calibration, grader_id), cnt in summary.items()
    ]
    d["layer_summary"] = _layer_summary(parsed)
    return d


@router.get("")
def list_task_runs():
    db = get_db()
    rows = db.execute("SELECT * FROM task_runs ORDER BY created_at DESC").fetchall()
    result = [enrich_run(r, db) for r in rows]
    db.close()
    return result


@router.post("")
def create_task_run(body: TaskRunCreate, background_tasks: BackgroundTasks):
    db = get_db()
    # validate dataset
    ds = db.execute("SELECT * FROM datasets WHERE id=?", (body.dataset_id,)).fetchone()
    if not ds:
        db.close()
        raise HTTPException(404, "Dataset not found")

    platforms = _expand_platforms(body.platform)
    cases = _get_cases(db, body.dataset_id, body.filter_category, body.filter_difficulty)
    if not cases:
        db.close()
        raise HTTPException(400, "No test cases match filters")

    total = len(cases) * len(platforms) * body.runs_per_case
    run_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO task_runs (id, name, dataset_id, platform, agent_version, "
        "runs_per_case, status, progress_total, started_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id, body.name, body.dataset_id, body.platform, body.agent_version,
         body.runs_per_case, "running", total, datetime.now().isoformat())
    )

    # pre-create run_result rows
    result_ids = {}
    for case in cases:
        for plat in platforms:
            for attempt in range(1, body.runs_per_case + 1):
                rid = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO run_results (id, task_run_id, test_case_id, platform, "
                    "attempt_number, status) VALUES (?,?,?,?,?,?)",
                    (rid, run_id, case["id"], plat, attempt, "pending")
                )
                result_ids[(case["id"], plat, attempt)] = rid

    db.commit()
    row = db.execute("SELECT * FROM task_runs WHERE id=?", (run_id,)).fetchone()
    db.close()

    background_tasks.add_task(dispatch_all, run_id, cases, platforms, body.runs_per_case, result_ids)
    return dict(row)


async def dispatch_all(run_id, cases, platforms, runs_per_case, result_ids):
    import httpx, asyncio

    async def call_agent(result_id, source_url, platform, task_id):
        callback_url = f"{SELF_URL}/api/tasks/callback/{result_id}"
        target = f"{SELF_URL}/api/mock/run" if USE_MOCK else f"{AGENT_URL}/api/eval/run"
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                await client.post(target, json={
                    "task_id": task_id,
                    "source_url": source_url,
                    "platform": platform,
                    "callback_url": callback_url
                })
        except Exception as e:
            # mark failed directly
            db = get_db()
            db.execute(
                "UPDATE run_results SET status='failed', agent_error=? WHERE id=?",
                (str(e), result_id)
            )
            db.execute(
                "UPDATE task_runs SET progress_failed=progress_failed+1, "
                "progress_completed=progress_completed+1 WHERE id=?", (run_id,)
            )
            db.commit()
            db.close()

    tasks = []
    sem = asyncio.Semaphore(3)  # max 3 concurrent

    async def bounded(result_id, source_url, platform, task_id):
        async with sem:
            await call_agent(result_id, source_url, platform, task_id)

    for case in cases:
        for platform in platforms:
            for attempt in range(1, runs_per_case + 1):
                rid = result_ids[(case["id"], platform, attempt)]
                tasks.append(bounded(rid, case["source_url"], platform, rid))

    await asyncio.gather(*tasks)


@router.post("/callback/{result_id}")
async def agent_callback(result_id: str, body: AgentCallback, background_tasks: BackgroundTasks):
    db = get_db()
    rr = db.execute("SELECT * FROM run_results WHERE id=?", (result_id,)).fetchone()
    if not rr:
        db.close()
        raise HTTPException(404, "RunResult not found")

    output_json = body.output.model_dump() if body.output else None
    trace_json = body.trace.model_dump() if body.trace else None

    db.execute(
        "UPDATE run_results SET status=?, duration_ms=?, cost_rmb=?, "
        "output=?, trace=?, agent_error=? WHERE id=?",
        (body.status, body.duration_ms, body.cost_rmb,
         json.dumps(output_json), json.dumps(trace_json),
         body.error or "", result_id)
    )
    db.execute(
        "UPDATE task_runs SET progress_completed=progress_completed+1 WHERE id=?",
        (rr["task_run_id"],)
    )
    if body.status == "failed":
        db.execute(
            "UPDATE task_runs SET progress_failed=progress_failed+1 WHERE id=?",
            (rr["task_run_id"],)
        )

    # check if all done
    task = db.execute("SELECT * FROM task_runs WHERE id=?", (rr["task_run_id"],)).fetchone()
    if task["progress_completed"] >= task["progress_total"]:
        db.execute(
            "UPDATE task_runs SET status='completed', completed_at=? WHERE id=?",
            (datetime.now().isoformat(), task["id"])
        )
    db.commit()
    db.close()

    if body.status != "failed" and output_json:
        background_tasks.add_task(run_evals_for_result, result_id)

    return {"ok": True}


@router.get("/analysis/grader-meta")
def grader_meta():
    return get_grader_meta_v2()


@router.get("/analysis/failure-codes")
def list_failure_codes():
    db = get_db()
    _ensure_eval_center_tables(db)
    rows = db.execute("SELECT * FROM failure_codes ORDER BY category, stage, code").fetchall()
    db.commit()
    db.close()
    return [dict(r) for r in rows]


@router.get("/analysis/failure-taxonomy")
def failure_taxonomy():
    db = get_db()
    _ensure_eval_center_tables(db)
    rows = db.execute(
        "SELECT fc.*, COUNT(cfc.id) AS case_count "
        "FROM failure_codes fc "
        "LEFT JOIN case_failure_codes cfc ON cfc.code = fc.code "
        "GROUP BY fc.code "
        "ORDER BY fc.category, fc.stage, fc.code"
    ).fetchall()
    db.commit()
    db.close()
    return [dict(r) for r in rows]


@router.get("/analysis/artifact-image")
def artifact_image(path: str = Query(...)):
    p = Path(path).expanduser().resolve()
    root = PROJECT_ROOT.resolve()
    if not str(p).startswith(str(root)):
        raise HTTPException(403, "Path outside project root")
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "Artifact not found")
    media_type = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return FileResponse(str(p), media_type=media_type)


@router.get("/analysis/coding-board")
def coding_board(limit: int = 80):
    db = get_db()
    _ensure_eval_center_tables(db)
    rows = db.execute(
        "SELECT rr.*, tr.name AS run_name, tr.agent_version, tc.source_url, tc.category, tc.difficulty, "
        "ha.biggest_issue, ca.summary AS ai_summary, ca.analysis_json "
        "FROM run_results rr "
        "JOIN task_runs tr ON tr.id = rr.task_run_id "
        "LEFT JOIN test_cases tc ON tc.id = rr.test_case_id "
        "LEFT JOIN human_annotations ha ON ha.run_result_id = rr.id "
        "LEFT JOIN case_ai_analyses ca ON ca.id = ("
        "  SELECT id FROM case_ai_analyses "
        "  WHERE run_result_id = rr.id "
        "  ORDER BY created_at DESC LIMIT 1"
        ") "
        "WHERE rr.id IN ("
        "  SELECT DISTINCT run_result_id FROM eval_scores WHERE verdict='fail'"
        ") "
        "ORDER BY rr.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        scores = db.execute("SELECT * FROM eval_scores WHERE run_result_id=?", (d["id"],)).fetchall()
        parsed_scores = [_parse_score(s) for s in scores]
        codes = db.execute(
            "SELECT c.*, cfc.source, cfc.note FROM case_failure_codes cfc "
            "JOIN failure_codes c ON c.code = cfc.code WHERE cfc.run_result_id=? "
            "ORDER BY c.category, c.code",
            (d["id"],),
        ).fetchall()
        d["output"] = _json_loads(d.get("output"), {})
        d["scores"] = parsed_scores
        d["layer_summary"] = _layer_summary(parsed_scores)
        d["failure_codes"] = [dict(c) for c in codes]
        d["recommended_codes"] = _recommend_codes(parsed_scores)
        d["analysis_json"] = _json_loads(d.get("analysis_json"), {})
        out.append(d)
    db.commit()
    db.close()
    return out


@router.get("/analysis/compare-v3")
def compare_runs_v3(run_ids: str):
    ids = [r.strip() for r in run_ids.split(",") if r.strip()]
    db = get_db()
    result = []
    for rid in ids:
        row = db.execute("SELECT * FROM task_runs WHERE id=?", (rid,)).fetchone()
        if not row:
            continue
        run = dict(row)
        scores = db.execute(
            "SELECT es.* FROM eval_scores es "
            "JOIN run_results rr ON rr.id = es.run_result_id "
            "WHERE rr.task_run_id=?",
            (rid,),
        ).fetchall()
        parsed = [_parse_score(s) for s in scores]
        failures = [s for s in parsed if s.get("verdict") == "fail"]
        run["layer_summary"] = _layer_summary(parsed)
        run["top_failed_graders"] = sorted(
            [
                {"grader_id": gid, "count": count}
                for gid, count in {
                    s["grader_id"]: len([f for f in failures if f["grader_id"] == s["grader_id"]])
                    for s in failures
                }.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:8]
        result.append(run)
    db.close()
    return result


@router.post("/{run_id}/regression-dataset")
def create_regression_dataset(run_id: str, body: dict = Body(default={})):
    scope = body.get("scope") or "failed"
    db = get_db()
    run = db.execute("SELECT * FROM task_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        db.close()
        raise HTTPException(404, "Task run not found")

    where = ""
    params = [run_id]
    if scope == "trusted_blockers":
        where = (
            "AND rr.id IN ("
            "  SELECT es.run_result_id FROM eval_scores es "
            "  WHERE es.verdict='fail' AND es.severity IN ('fatal','blocker') "
            "  AND json_extract(es.reason, '$.harness_layer')='outcome_verification' "
            "  AND coalesce(json_extract(es.reason, '$.calibration'), 'trusted')='trusted'"
            ")"
        )
    else:
        where = "AND rr.id IN (SELECT DISTINCT run_result_id FROM eval_scores WHERE verdict='fail')"

    rows = db.execute(
        "SELECT DISTINCT tc.* FROM run_results rr "
        "JOIN test_cases tc ON tc.id = rr.test_case_id "
        f"WHERE rr.task_run_id=? {where} "
        "ORDER BY tc.created_at DESC",
        params,
    ).fetchall()
    if not rows:
        db.close()
        raise HTTPException(400, "No failed cases to materialize")

    now = datetime.now().isoformat(timespec="seconds")
    dataset_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO datasets (id, name, description, version, status) VALUES (?,?,?,?,?)",
        (
            dataset_id,
            f"回归集 - {dict(run)['name'][:36]} - {now}",
            f"从实验 {run_id} 的 {scope} case 自动生成",
            "regression-v1",
            "active",
        ),
    )

    created = []
    for row in rows:
        old = dict(row)
        new_case_id = str(uuid.uuid4())
        tags = _json_loads(old.get("tags"), [])
        if "regression" not in tags:
            tags.append("regression")
        tags.append(f"from-run:{run_id}")
        db.execute(
            "INSERT INTO test_cases (id, dataset_id, source_url, category, difficulty, source_quality, "
            "taobao_ref_url, douyin_ref_url, xiaohongshu_ref_url, tags, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_case_id,
                dataset_id,
                old.get("source_url", ""),
                old.get("category", ""),
                old.get("difficulty", "medium"),
                old.get("source_quality", "medium"),
                old.get("taobao_ref_url", ""),
                old.get("douyin_ref_url", ""),
                old.get("xiaohongshu_ref_url", ""),
                json.dumps(tags, ensure_ascii=False),
                f"{old.get('notes') or ''}\nregression_source_case={old.get('id')}".strip(),
            ),
        )
        snapshot = get_case_snapshot(db, old.get("id", ""))
        if snapshot:
            upsert_case_snapshot(db, new_case_id)
        created.append(new_case_id)

    db.commit()
    db.close()
    return {"dataset_id": dataset_id, "case_count": len(created), "scope": scope}


@router.get("/{run_id}/results/{result_id}/diagnostic-context")
def diagnostic_context(run_id: str, result_id: str):
    db = get_db()
    _ensure_eval_center_tables(db)
    row = db.execute(
        "SELECT rr.*, tr.name AS run_name, tr.agent_version, tr.platform AS run_platform, "
        "tc.source_url, tc.category, tc.difficulty, tc.source_quality, "
        "tc.taobao_ref_url, tc.douyin_ref_url, tc.xiaohongshu_ref_url, tc.tags, tc.notes "
        "FROM run_results rr "
        "JOIN task_runs tr ON tr.id = rr.task_run_id "
        "LEFT JOIN test_cases tc ON tc.id = rr.test_case_id "
        "WHERE rr.id=? AND rr.task_run_id=?",
        (result_id, run_id),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Run result not found")

    result = dict(row)
    output = _enrich_images(_json_loads(result.get("output"), {}))
    trace = _json_loads(result.get("trace"), None)
    source = _source_snapshot(result.get("source_url", ""), result.get("test_case_id", ""), db)
    scores = [_parse_score(s) for s in db.execute(
        "SELECT * FROM eval_scores WHERE run_result_id=? ORDER BY created_at, grader_id",
        (result_id,),
    ).fetchall()]
    annotation = db.execute("SELECT * FROM human_annotations WHERE run_result_id=?", (result_id,)).fetchone()
    ai = db.execute(
        "SELECT * FROM case_ai_analyses WHERE run_result_id=? ORDER BY created_at DESC LIMIT 1",
        (result_id,),
    ).fetchone()
    codes = db.execute(
        "SELECT c.*, cfc.source, cfc.note FROM case_failure_codes cfc "
        "JOIN failure_codes c ON c.code = cfc.code WHERE cfc.run_result_id=? "
        "ORDER BY c.category, c.code",
        (result_id,),
    ).fetchall()
    db.commit()
    db.close()

    return {
        "result": {
            **result,
            "output": output,
            "trace": trace,
            "tags": _json_loads(result.get("tags"), []),
        },
        "source": source,
        "output": output,
        "trace": trace,
        "scores": scores,
        "layer_summary": _layer_summary(scores),
        "claims": _extract_claims(output, source),
        "annotation": dict(annotation) if annotation else None,
        "ai_analysis": {
            **dict(ai),
            "analysis_json": _json_loads(ai["analysis_json"], {}),
        } if ai else None,
        "failure_codes": [dict(c) for c in codes],
        "recommended_codes": _recommend_codes(scores),
        "grader_meta": get_grader_meta_v2(),
    }


@router.post("/{run_id}/results/{result_id}/ai-analysis")
def create_ai_analysis(run_id: str, result_id: str):
    context = diagnostic_context(run_id, result_id)
    result = context["result"]
    output = context["output"]
    source = context["source"]
    scores = context["scores"]
    analysis = _heuristic_case_analysis(result, scores, source, output)

    db = get_db()
    _ensure_eval_center_tables(db)
    db.execute(
        "INSERT INTO case_ai_analyses (id, run_result_id, analysis_json, summary) VALUES (?,?,?,?)",
        (str(uuid.uuid4()), result_id, json.dumps(analysis, ensure_ascii=False), analysis["summary"]),
    )
    db.commit()
    db.close()
    return analysis


@router.post("/{run_id}/results/{result_id}/failure-codes")
def save_case_failure_codes(run_id: str, result_id: str, body: dict = Body(...)):
    codes = body.get("codes") or []
    note = body.get("note") or ""
    source = body.get("source") or "human"
    if not isinstance(codes, list):
        raise HTTPException(400, "codes must be a list")

    db = get_db()
    _ensure_eval_center_tables(db)
    exists = db.execute(
        "SELECT id FROM run_results WHERE id=? AND task_run_id=?",
        (result_id, run_id),
    ).fetchone()
    if not exists:
        db.close()
        raise HTTPException(404, "Run result not found")

    db.execute("DELETE FROM case_failure_codes WHERE run_result_id=? AND source=?", (result_id, source))
    for code in codes:
        code = str(code)
        db.execute(
            "INSERT OR IGNORE INTO failure_codes (code, label, category) VALUES (?,?,?)",
            (code, code, "custom"),
        )
        db.execute(
            "INSERT OR IGNORE INTO case_failure_codes (id, run_result_id, code, source, note) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), result_id, code, source, note),
        )
    db.commit()
    db.close()
    return {"ok": True, "codes": codes}


@router.get("/{run_id}")
def get_task_run(run_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM task_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Task run not found")
    d = enrich_run(row, db)
    db.close()
    return d


@router.get("/{run_id}/results")
def list_run_results(run_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT rr.*, tc.source_url, tc.category, tc.difficulty "
        "FROM run_results rr "
        "JOIN test_cases tc ON tc.id = rr.test_case_id "
        "WHERE rr.task_run_id=? ORDER BY rr.created_at",
        (run_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["output"] = json.loads(d["output"] or "null")
        d["trace"] = json.loads(d["trace"] or "null")
        scores = db.execute(
            "SELECT * FROM eval_scores WHERE run_result_id=?", (d["id"],)
        ).fetchall()
        d["scores"] = [_parse_score(s) for s in scores]
        d["layer_summary"] = _layer_summary(d["scores"])
        ann = db.execute(
            "SELECT * FROM human_annotations WHERE run_result_id=?", (d["id"],)
        ).fetchone()
        d["annotation"] = dict(ann) if ann else None
        result.append(d)
    db.close()
    return result


@router.get("/{run_id}/results/{result_id}")
def get_run_result(run_id: str, result_id: str):
    db = get_db()
    row = db.execute(
        "SELECT rr.*, tc.source_url, tc.category, tc.difficulty, "
        "tc.taobao_ref_url, tc.douyin_ref_url, tc.xiaohongshu_ref_url "
        "FROM run_results rr "
        "JOIN test_cases tc ON tc.id = rr.test_case_id "
        "WHERE rr.id=? AND rr.task_run_id=?",
        (result_id, run_id)
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(404)
    d = dict(row)
    d["output"] = json.loads(d["output"] or "null")
    d["trace"] = json.loads(d["trace"] or "null")
    scores = db.execute("SELECT * FROM eval_scores WHERE run_result_id=?", (result_id,)).fetchall()
    d["scores"] = [_parse_score(s) for s in scores]
    d["layer_summary"] = _layer_summary(d["scores"])
    ann = db.execute("SELECT * FROM human_annotations WHERE run_result_id=?", (result_id,)).fetchone()
    d["annotation"] = dict(ann) if ann else None
    db.close()
    return d


@router.post("/{run_id}/results/{result_id}/annotate")
def annotate(run_id: str, result_id: str, body: HumanAnnotation):
    db = get_db()
    existing = db.execute(
        "SELECT id FROM human_annotations WHERE run_result_id=?", (result_id,)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE human_annotations SET q1_publishable=?, q2_competitor_parity=?, "
            "q3_would_click=?, biggest_issue=? WHERE run_result_id=?",
            (body.q1_publishable, body.q2_competitor_parity, body.q3_would_click,
             body.biggest_issue, result_id)
        )
    else:
        db.execute(
            "INSERT INTO human_annotations (id, run_result_id, q1_publishable, "
            "q2_competitor_parity, q3_would_click, biggest_issue) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), result_id, body.q1_publishable,
             body.q2_competitor_parity, body.q3_would_click, body.biggest_issue)
        )
    db.commit()
    db.close()
    return {"ok": True}


@router.get("/analysis/compare")
def compare_runs(run_ids: str):
    """Compare multiple runs. run_ids = comma-separated IDs."""
    ids = [r.strip() for r in run_ids.split(",") if r.strip()]
    db = get_db()
    result = []
    for rid in ids:
        row = db.execute("SELECT * FROM task_runs WHERE id=?", (rid,)).fetchone()
        if not row:
            continue
        d = dict(row)
        scores = db.execute(
            "SELECT es.grader_id, es.severity, "
            "SUM(CASE WHEN es.verdict='pass' THEN 1 ELSE 0 END) as passes, "
            "COUNT(*) as total "
            "FROM eval_scores es "
            "JOIN run_results rr ON rr.id = es.run_result_id "
            "WHERE rr.task_run_id=? "
            "GROUP BY es.grader_id, es.severity",
            (rid,)
        ).fetchall()
        d["grader_stats"] = [dict(s) for s in scores]
        result.append(d)
    db.close()
    return result
