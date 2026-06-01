"""
Generates duty reports from completed task runs.
"""
import uuid, json, os
from datetime import datetime
from collections import defaultdict
from database import get_db


def _parse_reason_meta(reason: str) -> dict:
    try:
        parsed = json.loads(reason or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _ai_analysis(fatal_failures: list, warning_failures: list, review_failures=None,
                 quality_issues=None, listing_quality_score=None) -> str:
    """Use LLM to generate analysis. Falls back to rule-based if no API key."""
    review_failures = review_failures or []
    quality_issues = quality_issues or []
    if not fatal_failures and not warning_failures and not review_failures and not quality_issues:
        return "今日评测结果良好，未发现明显问题。建议保持当前 Agent 版本不变。"

    try:
        from openai import OpenAI
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("no key")
        base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        client = OpenAI(api_key=api_key, base_url=base_url)

        fatal_text = "\n".join(
            f"- [{f['grader_id']}] {f['reason']} (category: {f.get('category','')})"
            for f in fatal_failures[:10]
        )
        warning_text = "\n".join(
            f"- [{w['grader_id']}] {w['reason']}"
            for w in warning_failures[:5]
        )
        review_text = "\n".join(
            f"- [{r['grader_id']}] {r['reason']}"
            for r in review_failures[:5]
        )
        quality_text = "\n".join(
            f"- [{q.get('grader_id','quality')}] {q.get('code','')} {q.get('reason','')} (case: {q.get('category','')}, score: {q.get('score','')})"
            for q in quality_issues[:8]
        )

        prompt = f"""你是一名资深电商 AI 产品专家。以下是今日 Listing Agent 评测中发现的问题：

FATAL 失败（{len(fatal_failures)} 例）：
{fatal_text if fatal_text else '无'}

WARNING 失败（{len(warning_failures)} 例）：
{warning_text if warning_text else '无'}

REVIEW 信号（{len(review_failures)} 例）：
{review_text if review_text else '无'}

上架质量分：{listing_quality_score if listing_quality_score is not None else '未计算'}
上架质量问题：
{quality_text if quality_text else '无'}

请用 3-4 句话分析主要问题模式，并给出 2-3 条针对 Agent prompt 或策略的改进建议。
直接输出分析内容，不要有标题或格式符号。"""

        resp = client.chat.completions.create(
            model=os.getenv("GRADER_MODEL", "qwen-plus"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()

    except Exception:
        # rule-based fallback
        grader_counts = defaultdict(int)
        for f in fatal_failures + warning_failures + review_failures:
            grader_counts[f["grader_id"]] += 1
        for q in quality_issues:
            grader_counts[q.get("code") or q.get("grader_id") or "quality_issue"] += 1
        top = sorted(grader_counts.items(), key=lambda x: -x[1])[:3]
        lines = [
            f"今日共发现 {len(fatal_failures)} 个 FATAL 失败，"
            f"{len(warning_failures)} 个 WARNING 失败，"
            f"{len(review_failures)} 个 REVIEW 信号。"
        ]
        if listing_quality_score is not None:
            lines.append(f"上架质量分 {listing_quality_score}。")
        if top:
            issues = "、".join(f"{k}({v}例)" for k, v in top)
            lines.append(f"主要问题集中在：{issues}。")
        lines.append("建议重点排查上述维度对应的 Agent 步骤和 prompt 配置。")
        return " ".join(lines)


def generate_report_for_run(run_id: str) -> dict:
    db = get_db()

    run = db.execute("SELECT * FROM task_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        db.close()
        return {}
    run = dict(run)

    results = db.execute(
        "SELECT rr.id, rr.status, rr.platform, tc.category "
        "FROM run_results rr "
        "JOIN test_cases tc ON tc.id = rr.test_case_id "
        "WHERE rr.task_run_id=?", (run_id,)
    ).fetchall()

    total = len(results)
    if total == 0:
        db.close()
        return {}

    result_ids = [r["id"] for r in results]
    result_meta = {r["id"]: dict(r) for r in results}

    # gather all scores
    scores = db.execute(
        f"SELECT * FROM eval_scores WHERE run_result_id IN ({','.join('?'*len(result_ids))})",
        result_ids
    ).fetchall()

    fatal_fails = []
    warning_fails = []
    review_fails = []
    run_validity_fails = []
    fatal_pass_by_result = defaultdict(lambda: True)
    warning_pass_by_result = defaultdict(lambda: True)
    grader_stats = defaultdict(lambda: {"pass": 0, "fail": 0, "total": 0})
    quality_scores_by_result = defaultdict(list)
    quality_dimension_totals = defaultdict(list)
    quality_issues = []

    for s in scores:
        s = dict(s)
        if s["verdict"] is None or s["verdict"] == "skipped":
            continue
        gid = s["grader_id"]
        sev = s["severity"]
        reason_meta = _parse_reason_meta(s["reason"])
        harness_layer = reason_meta.get("harness_layer", "")
        calibration = reason_meta.get("calibration", "trusted")
        numeric_score = s.get("score")
        if numeric_score is None:
            numeric_score = reason_meta.get("score")
        if numeric_score is not None:
            try:
                numeric_score = float(numeric_score)
            except Exception:
                numeric_score = None

        if harness_layer == "listing_quality" and numeric_score is not None:
            quality_scores_by_result[s["run_result_id"]].append(numeric_score)
            for dim, value in (reason_meta.get("dimension_scores") or {}).items():
                try:
                    quality_dimension_totals[dim].append(float(value))
                except Exception:
                    pass
            meta = result_meta.get(s["run_result_id"], {})
            for issue in reason_meta.get("issues") or []:
                if isinstance(issue, dict):
                    quality_issues.append({
                        "run_result_id": s["run_result_id"],
                        "grader_id": gid,
                        "score": round(numeric_score, 1),
                        "category": meta.get("category", ""),
                        "platform": meta.get("platform", ""),
                        "code": issue.get("code", "quality_issue"),
                        "field": issue.get("field", ""),
                        "reason": issue.get("reason", ""),
                        "impact": issue.get("impact", ""),
                        "suggested_fix": issue.get("suggested_fix", ""),
                    })
        grader_stats[gid]["total"] += 1
        if s["verdict"] == "pass":
            grader_stats[gid]["pass"] += 1
        else:
            grader_stats[gid]["fail"] += 1
            meta = result_meta.get(s["run_result_id"], {})
            entry = {
                "run_result_id": s["run_result_id"],
                "grader_id": gid,
                "reason": s["reason"],
                "platform": meta.get("platform", ""),
                "category": meta.get("category", ""),
                "harness_layer": harness_layer,
                "stage": reason_meta.get("stage", ""),
                "calibration": calibration,
                "score_bucket": reason_meta.get("score_bucket", ""),
            }
            if harness_layer == "run_validity":
                run_validity_fails.append(entry)
            if sev in ("fatal", "blocker"):
                # Only trusted outcome blockers are automatic publish blockers.
                if harness_layer == "outcome_verification" and calibration == "trusted":
                    fatal_fails.append(entry)
                    fatal_pass_by_result[s["run_result_id"]] = False
                else:
                    review_fails.append(entry)
            elif sev == "warning":
                warning_fails.append(entry)
                warning_pass_by_result[s["run_result_id"]] = False

    # compute pass rate (cases where all trusted outcome blockers pass)
    fatal_pass_count = sum(1 for rid in result_ids if fatal_pass_by_result[rid])
    pass_rate = fatal_pass_count / total if total else 0

    # quality score
    warning_pass_count = sum(1 for rid in result_ids if warning_pass_by_result[rid])
    warning_rate = warning_pass_count / total if total else 0
    publish_quality_score = round(pass_rate * 60 + warning_rate * 30, 1)

    case_quality = []
    all_quality_scores = []
    for rid in result_ids:
        values = quality_scores_by_result.get(rid) or []
        if not values:
            continue
        case_score = round(sum(values) / len(values), 1)
        all_quality_scores.extend(values)
        meta = result_meta.get(rid, {})
        case_quality.append({
            "run_result_id": rid,
            "platform": meta.get("platform", ""),
            "category": meta.get("category", ""),
            "listing_quality_score": case_score,
            "quality_verdict": (
                "strong" if case_score >= 86 else
                "ok" if case_score >= 75 else
                "weak" if case_score >= 60 else
                "fail"
            ),
        })

    listing_quality_score = (
        round(sum(all_quality_scores) / len(all_quality_scores), 1)
        if all_quality_scores else None
    )
    quality_score = listing_quality_score if listing_quality_score is not None else publish_quality_score

    if listing_quality_score is not None:
        health_score = round((pass_rate * 0.45 + warning_rate * 0.15 + (listing_quality_score / 100) * 0.40) * 100, 1)
    else:
        health_score = round((pass_rate * 0.7 + warning_rate * 0.3) * 100, 1)

    # per-grader pass rates for report
    grader_rates = {
        gid: round(v["pass"] / v["total"] * 100, 1) if v["total"] > 0 else None
        for gid, v in grader_stats.items()
    }

    quality_dimension_scores = {
        dim: round(sum(values) / len(values), 1)
        for dim, values in quality_dimension_totals.items()
        if values
    }
    quality_issue_counts = defaultdict(int)
    for issue in quality_issues:
        quality_issue_counts[issue.get("code") or "quality_issue"] += 1

    ai_analysis = _ai_analysis(
        fatal_fails,
        warning_fails,
        review_fails,
        quality_issues=quality_issues,
        listing_quality_score=listing_quality_score,
    )

    report_json = {
        "run_id": run_id,
        "run_name": run["name"],
        "platform": run["platform"],
        "total_cases": total,
        "pass_rate": round(pass_rate * 100, 1),
        "quality_score": quality_score,
        "publish_quality_score": publish_quality_score,
        "listing_quality_score": listing_quality_score,
        "health_score": health_score,
        "fatal_failures_count": len(fatal_fails),
        "warning_failures_count": len(warning_fails),
        "review_failures_count": len(review_fails),
        "run_validity_failures_count": len(run_validity_fails),
        "fatal_failures": fatal_fails[:20],
        "warning_failures": warning_fails[:10],
        "review_failures": review_fails[:20],
        "run_validity_failures": run_validity_fails[:20],
        "case_quality": case_quality,
        "quality_dimension_scores": quality_dimension_scores,
        "quality_issues": quality_issues[:30],
        "quality_issue_counts": dict(sorted(quality_issue_counts.items(), key=lambda x: -x[1])),
        "grader_rates": grader_rates,
        "ai_analysis": ai_analysis,
    }

    report_id = str(uuid.uuid4())
    report_date = datetime.now().strftime("%Y-%m-%d")

    db.execute(
        "INSERT INTO duty_reports (id, task_run_id, report_date, health_score, "
        "pass_rate, quality_score, fatal_failures, warning_failures, total_cases, "
        "ai_analysis, report_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (report_id, run_id, report_date, health_score,
         round(pass_rate * 100, 1), quality_score,
         len(fatal_fails), len(warning_fails), total,
         ai_analysis, json.dumps(report_json, ensure_ascii=False))
    )
    db.commit()
    db.close()

    report_json["id"] = report_id
    return report_json
