"""
Process Graders v3 — run validity and trace/process health checks.

These graders intentionally stay code-only. They do not judge creative quality;
they decide whether a trial is trustworthy and whether the Agent execution path
left enough evidence for diagnosis.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from project_paths import resolve_agent_image_path_from_url


def _result(grader_id: str, verdict: str, severity: str,
            failures: list | None = None, critique: str = "",
            confidence: str = "high", skipped_reason: str | None = None):
    out = {
        "grader_id": grader_id,
        "verdict": verdict,
        "severity": severity,
        "failures": failures or [],
        "critique": critique,
        "confidence": confidence,
    }
    if skipped_reason:
        out["skipped_reason"] = skipped_reason
    return out


def _trace_steps(trace: Any) -> list[dict]:
    if not trace:
        return []
    if isinstance(trace, str):
        try:
            trace = json.loads(trace)
        except json.JSONDecodeError:
            return []
    if isinstance(trace, dict):
        steps = trace.get("steps") or trace.get("spans") or []
    elif isinstance(trace, list):
        steps = trace
    else:
        return []
    return [s for s in steps if isinstance(s, dict)]


def _step_text(step: dict) -> str:
    parts = [
        str(step.get("name", "")),
        str(step.get("status", "")),
        json.dumps(step.get("input", ""), ensure_ascii=False)[:1000],
        json.dumps(step.get("output", ""), ensure_ascii=False)[:1000],
        str(step.get("error", "")),
    ]
    return " ".join(parts).lower()


def _iter_images(output: dict) -> Iterable[tuple[str, dict]]:
    for i, img in enumerate(output.get("main_images", []) or []):
        if isinstance(img, dict):
            yield f"main_images[{i}]", img
    detail = output.get("detail_image")
    if isinstance(detail, dict):
        yield "detail_image", detail


def _local_path(img: dict) -> str | None:
    path = img.get("local_path") or img.get("output_path") or ""
    if path and Path(path).exists():
        return path
    candidate = resolve_agent_image_path_from_url(img.get("url", ""))
    if candidate:
        return str(candidate)
    return None


def _meaningful_attributes(attrs: dict) -> dict:
    if not isinstance(attrs, dict):
        return {}
    return {
        str(key): value
        for key, value in attrs.items()
        if key and not str(key).startswith("_") and value is not None and str(value).strip()
    }


def run_result_terminal_state(output: dict | None = None, run_result_status: str = "",
                              agent_error: str = "", **_) -> dict:
    """L0: a trial must be in a clear terminal state before its eval is trusted."""
    status = (run_result_status or "").lower()
    if status in {"success", "completed"}:
        return _result("run_result_terminal_state", "pass", "blocker",
                       critique=f"trial 已进入终态: {status}")
    if status == "partial":
        return _result(
            "run_result_terminal_state",
            "fail",
            "warning",
            [{
                "field": "run_result.status",
                "issue_type": "partial_trial",
                "evidence": {"status": status, "agent_error": agent_error[:200]},
                "evidence_quote": "trial 处于 partial 状态，产物可评但过程不完整",
                "severity": "warning",
                "suggested_fix": "检查 Agent callback 和每个阶段的完成条件，避免静默半成品",
            }],
            "trial 是 partial，评测结果只能作为诊断信号",
            confidence="medium",
        )
    if not status:
        return _result("run_result_terminal_state", "skipped", "blocker",
                       critique="缺少 run_result.status", confidence="low",
                       skipped_reason="missing_status")
    return _result(
        "run_result_terminal_state",
        "fail",
        "blocker",
        [{
            "field": "run_result.status",
            "issue_type": "non_terminal_or_failed_trial",
            "evidence": {"status": status, "agent_error": agent_error[:200]},
            "evidence_quote": f"trial 状态为 {status}，不是可信成功终态",
            "severity": "blocker",
            "suggested_fix": "先修 executor/callback 状态机，再评估产物质量",
        }],
        f"trial 状态不可信: {status}",
    )


def source_snapshot_available(output: dict | None = None, source_url: str = "", source_data: dict | None = None,
                              source_attributes: dict | None = None,
                              source_images: list | None = None, **_) -> dict:
    """L0: grounding graders need a real source snapshot, not just a URL."""
    if not source_url:
        return _result("source_snapshot_available", "skipped", "warning",
                       critique="没有 source_url，跳过 source snapshot 检查",
                       confidence="low", skipped_reason="missing_source_url")

    source_data = source_data or {}
    attrs = source_data.get("attributes") or source_attributes or {}
    meaningful_attrs = _meaningful_attributes(attrs)
    images = source_data.get("images") or source_images or []
    raw_data = source_data.get("raw_data") or source_data.get("raw_attributes") or ""
    title = source_data.get("title") or ""

    missing = []
    if not title:
        missing.append("title")
    if not meaningful_attrs:
        missing.append("attributes")
    if not images:
        missing.append("images")
    if not raw_data:
        missing.append("raw_data")

    if missing:
        return _result(
            "source_snapshot_available",
            "fail",
            "warning",
            [{
                "field": "source_snapshot",
                "issue_type": "incomplete_source_snapshot",
                "evidence": {
                    "missing": missing,
                    "source_url": source_url,
                    "attributes_count": len(meaningful_attrs),
                    "raw_attributes_count": len(attrs) if isinstance(attrs, dict) else 0,
                    "images_count": len(images),
                },
                "evidence_quote": f"source snapshot 缺少 {', '.join(missing)}，grounding 评测会降级",
                "severity": "warning",
                "suggested_fix": "把 source title/attributes/images/raw_data 持久化为 case 输入",
            }],
            f"source snapshot 不完整: {', '.join(missing)}",
            confidence="high",
        )

    return _result("source_snapshot_available", "pass", "warning",
                   critique=f"source snapshot 可用：{len(meaningful_attrs)} 个属性，{len(images)} 张图片")


def artifact_readability(output: dict, **_) -> dict:
    """L0: image artifacts referenced by output must be readable."""
    output = output or {}
    images = list(_iter_images(output))
    if not images:
        return _result("artifact_readability", "skipped", "warning",
                       critique="没有可检查图片，发布完整性由 output_publishable 覆盖",
                       confidence="low", skipped_reason="no_images")

    failures = []
    for field, img in images:
        path = _local_path(img)
        if not path:
            failures.append({
                "field": field,
                "issue_type": "artifact_path_missing",
                "evidence": {"url": img.get("url", ""), "local_path": img.get("local_path", "")},
                "evidence_quote": f"{field} 无法解析到本地图片文件",
                "severity": "warning",
                "suggested_fix": "确保 Agent callback 返回 local_path/output_path，或提供可回溯的 /images URL",
            })
            continue
        try:
            with Image.open(path) as im:
                width, height = im.size
                if width <= 0 or height <= 0:
                    raise ValueError(f"invalid image size {width}x{height}")
        except Exception as exc:
            failures.append({
                "field": field,
                "issue_type": "artifact_unreadable",
                "evidence": {"path": path, "error": str(exc)[:160]},
                "evidence_quote": f"{field} 图片文件不可读取: {str(exc)[:80]}",
                "severity": "warning",
                "suggested_fix": "检查图片写入、路径映射和文件完整性",
            })

    verdict = "fail" if failures else "pass"
    return _result("artifact_readability", verdict, "warning", failures,
                   f"{len(failures)} 个 artifact 不可读" if failures else "所有图片 artifact 可读取")


def trace_completeness(output: dict | None = None, trace: Any = None, **_) -> dict:
    """L0/L4: trace should cover the main Agent lifecycle, not just final output."""
    steps = _trace_steps(trace)
    if not steps:
        return _result(
            "trace_completeness",
            "fail",
            "warning",
            [{
                "field": "trace",
                "issue_type": "missing_trace",
                "evidence": {"steps": 0},
                "evidence_quote": "缺少 trace.steps，无法诊断 Agent 过程",
                "severity": "warning",
                "suggested_fix": "Agent callback 必须回传关键阶段 trace",
            }],
            "缺少 trace，过程诊断不可用",
            confidence="high",
        )

    phase_patterns = {
        "source_fetch": r"source|browse|fetch|crawl|货源",
        "fact_extraction": r"visual|vlm|diagnosis|extract|事实|识别",
        "strategy": r"strategy|decision|plan|策略|规划",
        "copy": r"copy|title|selling|body|文案|标题|卖点",
        "image_or_render": r"image|render|compose|pillow|main_image|图片|渲染",
        "persistence_or_qa": r"save|write|db|persist|callback|judge|check|validate|合规|自检",
    }
    seen = set()
    for step in steps:
        text = _step_text(step)
        for phase, pattern in phase_patterns.items():
            if re.search(pattern, text):
                seen.add(phase)

    missing = [p for p in phase_patterns if p not in seen]
    if len(seen) < 4:
        return _result(
            "trace_completeness",
            "fail",
            "warning",
            [{
                "field": "trace.steps",
                "issue_type": "incomplete_trace",
                "evidence": {
                    "steps_count": len(steps),
                    "seen_phases": sorted(seen),
                    "missing_phases": missing,
                },
                "evidence_quote": f"trace 只覆盖 {len(seen)}/6 个关键阶段",
                "severity": "warning",
                "suggested_fix": "记录 source/fact/strategy/copy/image/persistence/qa 等关键阶段",
            }],
            f"trace 阶段覆盖不足: {len(seen)}/6",
            confidence="medium",
        )

    return _result("trace_completeness", "pass", "warning",
                   critique=f"trace 覆盖 {len(seen)}/6 个关键阶段，steps={len(steps)}",
                   confidence="medium")


def tool_error_rate(output: dict | None = None, trace: Any = None, agent_error: str = "", **_) -> dict:
    """L4: failed trace steps reveal process health issues even when output exists."""
    steps = _trace_steps(trace)
    if not steps and not agent_error:
        return _result("tool_error_rate", "skipped", "warning",
                       critique="无 trace/agent_error，跳过工具错误率检查",
                       confidence="low", skipped_reason="missing_trace")

    failed_steps = []
    for idx, step in enumerate(steps):
        status = str(step.get("status", "")).lower()
        error = step.get("error")
        if status in {"failed", "fail", "error"} or error:
            failed_steps.append((idx, step))

    failures = []
    if agent_error:
        failures.append({
            "field": "agent_error",
            "issue_type": "agent_error_present",
            "evidence": {"agent_error": agent_error[:300]},
            "evidence_quote": f"Agent callback 带错误信息: {agent_error[:80]}",
            "severity": "warning",
            "suggested_fix": "检查 Agent 最终 error 与失败阶段是否一致",
        })
    for idx, step in failed_steps[:10]:
        failures.append({
            "field": f"trace.steps[{idx}]",
            "issue_type": "failed_trace_step",
            "evidence": {
                "name": step.get("name", ""),
                "status": step.get("status", ""),
                "error": str(step.get("error", ""))[:300],
            },
            "evidence_quote": f"trace step「{step.get('name', idx)}」失败",
            "severity": "warning",
            "suggested_fix": "优先排查该工具调用的输入参数、返回值和重试逻辑",
        })

    verdict = "fail" if failures else "pass"
    return _result("tool_error_rate", verdict, "warning", failures,
                   f"{len(failures)} 个过程错误" if failures else "trace 未记录工具错误")


def self_check_final_artifact_seen(output: dict | None = None, trace: Any = None, **_) -> dict:
    """L4: final QA should inspect final artifacts, not only intermediate plans."""
    steps = _trace_steps(trace)
    if not steps:
        return _result("self_check_final_artifact_seen", "skipped", "warning",
                       critique="无 trace，无法判断最终自检是否看过产物",
                       confidence="low", skipped_reason="missing_trace")

    qa_steps = []
    artifact_seen = False
    artifact_terms = ["main_images", "detail_image", "/images/", ".png", ".jpg", ".jpeg", "local_path", "output_path"]
    for idx, step in enumerate(steps):
        name = str(step.get("name", "")).lower()
        if re.search(r"judge|check|validate|qa|compliance|review|自检|合规|审核", name):
            qa_steps.append((idx, step))
            text = _step_text(step)
            if any(term.lower() in text for term in artifact_terms):
                artifact_seen = True

    if artifact_seen:
        return _result("self_check_final_artifact_seen", "pass", "warning",
                       critique="最终自检 trace 中包含最终图片/产物引用", confidence="medium")

    failures = [{
        "field": "trace.steps",
        "issue_type": "final_artifact_not_checked",
        "evidence": {"qa_steps": [s.get("name", "") for _, s in qa_steps]},
        "evidence_quote": "未发现自检阶段读取最终图片/产物的证据",
        "severity": "warning",
        "suggested_fix": "Judge/QA 阶段必须读取最终 main_images/detail_image，而不是只看规划文本",
    }]
    verdict = "fail" if qa_steps else "skipped"
    critique = "自检没有检查最终 artifact" if qa_steps else "trace 中没有自检/QA step"
    return _result("self_check_final_artifact_seen", verdict, "warning", failures if qa_steps else [],
                   critique, confidence="medium" if qa_steps else "low",
                   skipped_reason=None if qa_steps else "missing_qa_step")


def image_plan_diversity(output: dict | None = None, trace: Any = None, **_) -> dict:
    """L4: image planning should express multi-angle/multi-scene diversity."""
    output = output or {}
    images = output.get("main_images", []) or []

    labels = []
    for img in images:
        if not isinstance(img, dict):
            continue
        label = img.get("layout_type") or img.get("role") or img.get("scene") or img.get("angle")
        if label:
            labels.append(str(label))

    steps = _trace_steps(trace)
    planning_text = " ".join(
        _step_text(step) for step in steps
        if re.search(r"image|plan|planner|layout|主图|图片|规划", str(step.get("name", "")).lower())
    )
    diversity_words = re.findall(
        r"场景|细节|对比|白底|生活|多角度|正面|侧面|俯拍|detail|scene|angle|lifestyle|white[-_ ]?bg",
        planning_text,
        flags=re.IGNORECASE,
    )

    distinct_labels = len(set(labels))
    enough_trace_diversity = len(set(w.lower() for w in diversity_words)) >= 3

    if distinct_labels >= 3 or enough_trace_diversity:
        return _result("image_plan_diversity", "pass", "warning",
                       critique="图片规划包含多角度/多场景信号", confidence="medium")

    if not labels and not planning_text:
        return _result("image_plan_diversity", "skipped", "warning",
                       critique="缺少图片规划 metadata/trace，无法判断多样性",
                       confidence="low", skipped_reason="missing_image_plan")

    return _result(
        "image_plan_diversity",
        "fail",
        "warning",
        [{
            "field": "image_plan",
            "issue_type": "low_image_plan_diversity",
            "evidence": {
                "distinct_output_labels": distinct_labels,
                "diversity_terms": sorted(set(diversity_words))[:10],
            },
            "evidence_quote": "图片规划缺少多角度/多场景证据，容易生成重复主图",
            "severity": "warning",
            "suggested_fix": "ImagePlanner 应显式规划 5 张不同 layout_type/scene/angle",
        }],
        "图片规划多样性不足",
        confidence="medium",
    )
