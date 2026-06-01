"""
Runs all v2 graders on a run_result and stores eval_scores.
Uses GRADERS_V2 registry (code + LLM + VLM graders).
"""
import uuid
import json
import sqlite3
import os
from pathlib import Path
from database import get_db
from graders_v2.registry_v2 import GRADERS_V2, get_grader_v3_meta
from project_paths import AGENT_DB
from source_snapshots import get_case_snapshot, normalize_images

# trend-seller-agent DB path (sources table is here, populated by eval_bridge._backfill_source)
_TREND_SELLER_DB = AGENT_DB
_FAST_SKIP_GRADERS = {
    "copy_factual_grounding",
    "selling_point_evidence",
    "body_copy_quality",
    "image_text_layout_quality",
    "image_foreign_text_residual",
    "image_platform_ui_overlay",
    "image_internal_text_leak",
    "image_source_reuse",
    "cross_case_pollution",
}


def _load_source_data(source_url: str, test_case_id: str = "") -> dict:
    """Load source page data from trend-seller DB given source_url.
    Returns dict with attributes / images / raw_data, or empty dict if not found / DB missing."""
    if test_case_id:
        db = get_db()
        try:
            snapshot = get_case_snapshot(db, test_case_id)
        finally:
            db.close()
        if snapshot:
            return snapshot

    if not source_url or not Path(_TREND_SELLER_DB).exists():
        return {}
    try:
        sdb = sqlite3.connect(_TREND_SELLER_DB)
        sdb.row_factory = sqlite3.Row
        row = sdb.execute(
            "SELECT title, price, image_url, images, attributes, raw_attributes, supplier, location, raw_data "
            "FROM sources WHERE url=? ORDER BY id DESC LIMIT 1",
            (source_url,)
        ).fetchone()
        sdb.close()
        if not row:
            return {}
        raw_data = json.loads(row["raw_data"] or "{}")
        images = normalize_images(row["images"], row["image_url"] or raw_data.get("image_url", ""))
        return {
            "title": row["title"] or "",
            "price": row["price"] or 0,
            "images": images,
            "attributes": json.loads(row["attributes"] or "{}"),
            "raw_attributes": row["raw_attributes"] or "",
            "supplier": row["supplier"] or "",
            "location": row["location"] or "",
            "raw_data": raw_data,
        }
    except Exception:
        return {}


def run_evals_for_result(result_id: str):
    db = get_db()
    row = db.execute(
        "SELECT rr.*, tc.category, tc.difficulty, tc.source_url, "
        "tc.taobao_ref_url, tc.douyin_ref_url, tc.xiaohongshu_ref_url "
        "FROM run_results rr "
        "JOIN test_cases tc ON tc.id = rr.test_case_id "
        "WHERE rr.id=?", (result_id,)
    ).fetchone()

    if not row:
        db.close()
        return

    d = dict(row)
    output = json.loads(d["output"] or "null") or {}
    trace = json.loads(d["trace"] or "null")

    # Determine platform from task_run if not on run_result
    platform = d.get("platform", "")
    if not platform:
        tr = db.execute("SELECT platform FROM task_runs WHERE id=(SELECT task_run_id FROM run_results WHERE id=?)", (result_id,)).fetchone()
        if tr:
            platform = tr["platform"] or "taobao"

    category = d.get("category", "")
    ref_url = {
        "taobao": d.get("taobao_ref_url"),
        "douyin": d.get("douyin_ref_url"),
        "xiaohongshu": d.get("xiaohongshu_ref_url"),
    }.get(platform, "")

    # Load source data from trend-seller DB (filled by eval_bridge._backfill_source)
    source_data = _load_source_data(d.get("source_url", ""), d.get("test_case_id", ""))

    kwargs = {
        "run_result_id": d.get("id"),
        "task_run_id": d.get("task_run_id"),
        "run_result_status": d.get("status", ""),
        "agent_error": d.get("agent_error", ""),
        "output": output,
        "trace": trace,
        "platform": platform,
        "category": category,
        "duration_ms": d.get("duration_ms"),
        "cost_rmb": d.get("cost_rmb"),
        "source_url": d.get("source_url", ""),
        "source_data": source_data,                           # full dict from trend-seller sources table
        "source_attributes": source_data.get("attributes", {}),
        "source_images": source_data.get("images", []),
        "ref_url": ref_url,
        "main_images": output.get("main_images", []),
        "body_copy": output.get("body_copy", ""),
    }

    # Delete old scores for this result (re-run scenario)
    db.execute("DELETE FROM eval_scores WHERE run_result_id=?", (result_id,))

    for grader_id, fn, grader_type, severity, scope, label in GRADERS_V2:
        meta = get_grader_v3_meta(grader_id)
        fast_mode = os.getenv("EVAL_FAST_MODE", "").lower() in {"1", "true", "yes"}
        run_quality_in_fast = os.getenv("EVAL_RUN_QUALITY", "").lower() in {"1", "true", "yes"}
        is_quality_grader = meta.get("score_bucket") == "listing_quality"
        if fast_mode and not (run_quality_in_fast and is_quality_grader) and (
            grader_type in {"llm", "vlm"} or grader_id in _FAST_SKIP_GRADERS
        ):
            result = {
                "grader_id": grader_id,
                "verdict": "skipped",
                "severity": severity,
                "failures": [],
                "critique": "EVAL_FAST_MODE 跳过耗时或外部依赖型 grader",
                "confidence": "low",
                "skipped_reason": "fast_mode",
            }
        else:
            try:
                result = fn(**kwargs)
            except Exception as e:
                result = {
                    "grader_id": grader_id,
                    "verdict": None,
                    "severity": severity,
                    "failures": [],
                    "critique": f"Grader 异常: {str(e)[:200]}",
                    "confidence": "low",
                }

        failures = result.get("failures", [])
        if isinstance(failures, list):
            enriched_failures = []
            for failure in failures:
                if isinstance(failure, dict):
                    f = dict(failure)
                    f.setdefault("harness_layer", meta.get("harness_layer"))
                    f.setdefault("agent_stage", meta.get("stage"))
                    f.setdefault("target", meta.get("target"))
                    f.setdefault("calibration", meta.get("calibration"))
                    enriched_failures.append(f)
                else:
                    enriched_failures.append(failure)
            failures = enriched_failures

        # Store structured result: verdict + full JSON reason
        reason_json = json.dumps({
            "critique": result.get("critique", ""),
            "failures": failures,
            "confidence": result.get("confidence", ""),
            "skipped_reason": result.get("skipped_reason"),
            "label": label,
            "scope": scope,
            "harness_layer": meta.get("harness_layer"),
            "target": meta.get("target"),
            "stage": meta.get("stage"),
            "calibration": meta.get("calibration"),
            "score_bucket": meta.get("score_bucket"),
            "requires_human_review": meta.get("requires_human_review"),
            "score": result.get("score"),
            "quality_verdict": result.get("quality_verdict"),
            "dimension_scores": result.get("dimension_scores", {}),
            "issues": result.get("issues", []),
            "positives": result.get("positives", []),
            "rubric_version": result.get("rubric_version"),
        }, ensure_ascii=False)

        db.execute(
            "INSERT INTO eval_scores (id, run_result_id, grader_id, grader_type, "
            "severity, verdict, score, confidence, reason) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), result_id, grader_id, grader_type,
             result.get("severity", severity),
             result.get("verdict"),
             result.get("score"),
             result.get("confidence", ""),
             reason_json)
        )

    db.commit()
    db.close()
