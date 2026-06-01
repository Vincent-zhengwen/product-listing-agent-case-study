"""
Grader Registry v2/v3 — maps grader_id → (function, type, severity, scope, label).

scope semantics:
- "universal":   applies to any listing (Agent output or real marketplace listing).
                  Safe to run on baseline validation.
- "agent_only":  assumes Agent output schema (requires selling_points / body_copy /
                  detail_image / Agent-specific attribute conventions). Don't run
                  on real marketplace baselines — will false-positive.
- "source_based": requires source page ground truth (source_attributes / source_images).
                  Skipped automatically when source data is absent.
- "trace_based": requires Agent trace steps. Not meaningful for marketplace baselines.
"""
from graders_v2 import schema_graders as sg, image_graders as ig
from graders_v2 import llm_graders as lg, vlm_graders as vg
from graders_v2 import process_graders as pg
from graders_v2 import quality_graders as qg

# Each entry: (grader_id, function, type, severity, scope, label)
GRADERS_V2 = [
    # ── L0. Run Validity / Harness Trust (4) ─────────────────────────────
    ("run_result_terminal_state",    pg.run_result_terminal_state,    "code", "blocker", "agent_only",  "Trial 终态可信度"),
    ("source_snapshot_available",    pg.source_snapshot_available,    "code", "warning", "agent_only",  "源页快照完整性"),
    ("artifact_readability",         pg.artifact_readability,         "code", "warning", "agent_only",  "产物文件可读取"),
    ("trace_completeness",           pg.trace_completeness,           "code", "warning", "trace_based", "Trace 完整性"),

    # ── A. Output Schema (5) ──────────────────────────────────────────────
    ("output_publishable",           sg.output_publishable,           "code", "blocker", "agent_only", "发布门槛检查"),
    ("output_schema_isolation",      sg.output_schema_isolation,      "code", "blocker", "universal",  "属性 schema 隔离"),
    ("attribute_key_chinese",        sg.attribute_key_chinese,        "code", "blocker", "universal",  "属性 key 全中文"),
    ("attribute_value_quality",      sg.attribute_value_quality,      "code", "blocker", "agent_only", "属性值质量"),
    ("image_resolution",             sg.image_resolution,             "code", "blocker", "universal",  "主图分辨率"),

    # ── B. Title (4) ──────────────────────────────────────────────────────
    ("title_publishable",            sg.title_publishable,            "code", "blocker", "universal", "标题合规"),
    ("title_no_template",            sg.title_no_template,            "code", "blocker", "universal", "标题非复用"),
    ("title_no_pollution",           sg.title_no_pollution,           "code", "warning", "universal", "标题无污染"),
    ("title_category_keyword",       sg.title_category_keyword,       "code", "warning", "universal", "标题含品类词"),

    # ── C. Copy/Text (1 code + 2 LLM) ──────────────────────────────────
    ("copy_no_template",             sg.copy_no_template,             "code", "blocker", "universal",    "文案非模板"),
    ("copy_factual_grounding",       lg.copy_factual_grounding,       "llm",  "blocker", "source_based", "文案虚构事实"),
    ("selling_point_evidence",       lg.selling_point_evidence,       "llm",  "warning", "agent_only",   "卖点证据检测"),
    ("body_copy_quality",            lg.body_copy_quality,            "llm",  "warning", "agent_only",   "正文质量检测"),

    # ── D. Image Basic (5) + VLM (1) ──────────────────────────────────────
    ("image_blank_detection",        ig.image_blank_detection,        "code", "blocker", "universal",    "空白主图检测"),
    ("image_dark_detection",         ig.image_dark_detection,         "code", "warning", "universal",    "极暗主图检测"),
    ("image_duplicate_main",         ig.image_duplicate_main,         "code", "blocker", "universal",    "主图重复检测"),
    ("image_fragmented_subject",     ig.image_fragmented_subject,     "code", "blocker", "universal",    "主图残缺检测"),
    ("image_source_reuse",           ig.image_source_reuse,           "code", "blocker", "source_based", "源图直接复用"),
    ("image_text_layout_quality",    vg.image_text_layout_quality,    "vlm",  "warning", "universal",    "文字排版质量"),

    # ── E. Image-Text (OCR) (3) ───────────────────────────────────────────
    ("image_foreign_text_residual",  ig.image_foreign_text_residual,  "code", "blocker", "universal", "供应商英文残留"),
    ("image_platform_ui_overlay",    ig.image_platform_ui_overlay,    "code", "blocker", "universal", "平台 UI 烙印"),
    ("image_internal_text_leak",     ig.image_internal_text_leak,     "code", "blocker", "agent_only", "Agent 指令泄漏"),

    # ── F. Cross-field (1) ────────────────────────────────────────────────
    ("cross_case_pollution",         ig.cross_case_pollution,         "code", "blocker", "universal", "跨 case 污染"),

    # ── L4. Process Quality (3) ───────────────────────────────────────────
    ("tool_error_rate",              pg.tool_error_rate,              "code", "warning", "trace_based", "工具错误率"),
    ("self_check_final_artifact_seen", pg.self_check_final_artifact_seen, "code", "warning", "trace_based", "最终产物自检"),
    ("image_plan_diversity",         pg.image_plan_diversity,         "code", "warning", "trace_based", "图片规划多样性"),

    # ── G. Buyer-visible Listing Quality (4) ─────────────────────────────
    ("copy_conversion_quality",      qg.copy_conversion_quality,      "llm", "warning", "agent_only",   "文案转化质量"),
    ("category_fit_quality",         qg.category_fit_quality,         "llm", "warning", "agent_only",   "品类适配质量"),
    ("main_image_quality",           qg.main_image_quality,           "vlm", "warning", "agent_only",   "主图商业质量"),
    ("detail_page_quality",          qg.detail_page_quality,          "vlm", "warning", "agent_only",   "详情页说服质量"),
]


_DEFAULT_META = {
    "harness_layer": "outcome_verification",
    "target": "output",
    "stage": "final_artifact",
    "calibration": "trusted",
    "score_bucket": "publishability",
    "requires_human_review": False,
}


GRADER_V3_META = {
    # L0 Run Validity
    "run_result_terminal_state": {
        "harness_layer": "run_validity",
        "target": "run",
        "stage": "executor",
        "calibration": "trusted",
        "score_bucket": "process_health",
        "requires_human_review": False,
    },
    "source_snapshot_available": {
        "harness_layer": "run_validity",
        "target": "source",
        "stage": "source_fetch",
        "calibration": "trusted",
        "score_bucket": "process_health",
        "requires_human_review": False,
    },
    "artifact_readability": {
        "harness_layer": "run_validity",
        "target": "artifact",
        "stage": "persistence",
        "calibration": "trusted",
        "score_bucket": "process_health",
        "requires_human_review": False,
    },
    "trace_completeness": {
        "harness_layer": "run_validity",
        "target": "trace",
        "stage": "executor",
        "calibration": "provisional",
        "score_bucket": "process_health",
        "requires_human_review": False,
    },

    # Outcome Verification
    "output_publishable": {"stage": "final_artifact"},
    "output_schema_isolation": {"stage": "persistence"},
    "attribute_key_chinese": {"stage": "persistence"},
    "attribute_value_quality": {"stage": "fact_extraction"},
    "image_resolution": {
        "target": "artifact",
        "stage": "render",
        "calibration": "provisional",
        "requires_human_review": True,
    },
    "title_publishable": {"stage": "copy"},
    "copy_no_template": {"stage": "copy"},
    "image_blank_detection": {"target": "artifact", "stage": "render"},
    "image_dark_detection": {
        "target": "artifact",
        "stage": "render",
        "score_bucket": "conversion",
    },
    "image_duplicate_main": {"target": "artifact", "stage": "image_plan"},
    "image_fragmented_subject": {
        "target": "artifact",
        "stage": "render",
        "calibration": "provisional",
        "requires_human_review": True,
    },
    "image_foreign_text_residual": {
        "target": "artifact",
        "stage": "render",
        "calibration": "provisional",
        "requires_human_review": True,
    },
    "image_platform_ui_overlay": {"target": "artifact", "stage": "render"},
    "image_internal_text_leak": {"target": "artifact", "stage": "image_plan"},

    # Grounding
    "title_no_template": {
        "harness_layer": "grounding",
        "target": "source",
        "stage": "copy",
        "calibration": "provisional",
        "score_bucket": "grounding",
        "requires_human_review": True,
    },
    "copy_factual_grounding": {
        "harness_layer": "grounding",
        "target": "source",
        "stage": "copy",
        "calibration": "provisional",
        "score_bucket": "grounding",
        "requires_human_review": True,
    },
    "image_source_reuse": {
        "harness_layer": "grounding",
        "target": "source",
        "stage": "render",
        "calibration": "provisional",
        "score_bucket": "grounding",
        "requires_human_review": True,
    },

    # Conversion Quality
    "title_no_pollution": {
        "harness_layer": "conversion_quality",
        "target": "output",
        "stage": "copy",
        "score_bucket": "conversion",
    },
    "title_category_keyword": {
        "harness_layer": "conversion_quality",
        "target": "output",
        "stage": "copy",
        "score_bucket": "conversion",
    },
    "selling_point_evidence": {
        "harness_layer": "conversion_quality",
        "target": "output",
        "stage": "strategy",
        "calibration": "provisional",
        "score_bucket": "conversion",
        "requires_human_review": True,
    },
    "body_copy_quality": {
        "harness_layer": "conversion_quality",
        "target": "output",
        "stage": "copy",
        "calibration": "provisional",
        "score_bucket": "conversion",
        "requires_human_review": True,
    },
    "image_text_layout_quality": {
        "harness_layer": "conversion_quality",
        "target": "artifact",
        "stage": "render",
        "calibration": "provisional",
        "score_bucket": "conversion",
        "requires_human_review": True,
    },
    "cross_case_pollution": {
        "harness_layer": "process_quality",
        "target": "output",
        "stage": "executor",
        "calibration": "experimental",
        "score_bucket": "process_health",
        "requires_human_review": True,
    },

    # L4 Process Quality
    "tool_error_rate": {
        "harness_layer": "process_quality",
        "target": "trace",
        "stage": "tool_execution",
        "calibration": "trusted",
        "score_bucket": "process_health",
        "requires_human_review": False,
    },
    "self_check_final_artifact_seen": {
        "harness_layer": "process_quality",
        "target": "trace",
        "stage": "qa",
        "calibration": "provisional",
        "score_bucket": "process_health",
        "requires_human_review": True,
    },
    "image_plan_diversity": {
        "harness_layer": "process_quality",
        "target": "trace",
        "stage": "image_plan",
        "calibration": "experimental",
        "score_bucket": "process_health",
        "requires_human_review": True,
    },

    # Listing Quality
    "copy_conversion_quality": {
        "harness_layer": "listing_quality",
        "target": "output",
        "stage": "copy",
        "calibration": "provisional",
        "score_bucket": "listing_quality",
        "requires_human_review": True,
    },
    "category_fit_quality": {
        "harness_layer": "listing_quality",
        "target": "output",
        "stage": "strategy",
        "calibration": "provisional",
        "score_bucket": "listing_quality",
        "requires_human_review": True,
    },
    "main_image_quality": {
        "harness_layer": "listing_quality",
        "target": "artifact",
        "stage": "image_plan",
        "calibration": "provisional",
        "score_bucket": "listing_quality",
        "requires_human_review": True,
    },
    "detail_page_quality": {
        "harness_layer": "listing_quality",
        "target": "artifact",
        "stage": "detail_page",
        "calibration": "provisional",
        "score_bucket": "listing_quality",
        "requires_human_review": True,
    },
}


def get_grader_v3_meta(grader_id: str) -> dict:
    meta = dict(_DEFAULT_META)
    meta.update(GRADER_V3_META.get(grader_id, {}))
    return meta


def get_grader_meta_v2():
    return [
        {
            "id": g[0],
            "type": g[2],
            "severity": g[3],
            "scope": g[4],
            "label": g[5],
            **get_grader_v3_meta(g[0]),
        }
        for g in GRADERS_V2
    ]
