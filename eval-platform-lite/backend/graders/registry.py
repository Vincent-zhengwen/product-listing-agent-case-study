"""
Grader registry: maps grader_id → (function, type, severity, label)
"""
from graders import code_graders as cg, llm_graders as lg

GRADERS = [
    # ── fatal: 达不到就不可发布 ───────────────────────────────────────────────
    # id                              fn                                  type    severity  label
    ("output_schema_valid",           cg.output_schema_valid,             "code", "fatal",   "输出结构完整"),
    ("title_length_check",            cg.title_length_check,              "code", "fatal",   "标题长度"),
    ("title_no_banned_words",         cg.title_no_banned_words,           "code", "fatal",   "无违禁词"),
    ("attributes_required",           cg.attributes_required_fields,      "code", "fatal",   "属性必填项"),
    ("main_image_count",              cg.main_image_count,                "code", "fatal",   "主图数量"),
    ("main_image_resolution",         cg.main_image_resolution,           "code", "fatal",   "主图分辨率"),
    ("detail_image_exists",           cg.detail_image_exists,             "code", "fatal",   "详情图存在"),
    ("detail_image_width",            cg.detail_image_width,              "code", "fatal",   "详情图宽度≥750px"),
    ("main_image_first_white_bg",     cg.main_image_first_white_bg,       "code", "fatal",   "第一主图白底"),
    ("b2c_transform",                 lg.b2c_transform,                   "llm",  "fatal",   "B2C文案转化"),
    ("factual_accuracy",              lg.factual_accuracy,                "llm",  "fatal",   "内容准确性"),
    ("main_image_no_supplier_text",   lg.main_image_no_supplier_text,     "llm",  "fatal",   "主图无供应商水印"),

    # ── warning: 影响转化率，应尽快修复 ──────────────────────────────────────
    ("steps_completed",               cg.steps_completed,                 "code", "warning", "步骤全部完成"),
    ("compliance_check",              cg.compliance_check,                "code", "warning", "合规检查"),
    ("title_has_core_keyword",        cg.title_has_core_keyword,          "code", "warning", "标题含品类词"),
    ("attribute_value_quality",       cg.attribute_value_quality,         "code", "warning", "属性值质量"),
    ("body_copy_length",              cg.body_copy_length,                "code", "warning", "正文长度≥100字"),
    ("platform_tone",                 lg.platform_tone,                   "llm",  "warning", "平台风格匹配"),
    ("title_appeal",                  lg.title_appeal,                    "llm",  "warning", "标题吸引力"),
    ("selling_point_credibility",     lg.selling_point_credibility,       "llm",  "warning", "卖点可信度"),
    ("body_copy_quality",             lg.body_copy_quality,               "llm",  "warning", "正文内容质量"),
    ("detail_narrative_completeness", lg.detail_narrative_completeness,   "llm",  "warning", "详情图叙事完整性"),
    ("main_image_composition",        lg.main_image_composition,          "llm",  "warning", "主图构图质量"),
    ("main_image_visual_consistency", lg.main_image_visual_consistency,   "llm",  "warning", "主图风格一致性"),
    ("detail_image_text_legibility",  lg.detail_image_text_legibility,    "llm",  "warning", "详情图文字可读性"),

    # ── info: 量化指标，无 pass/fail ──────────────────────────────────────────
    ("selling_point_count",           cg.selling_point_count,             "code", "info",    "卖点数量"),
    ("main_image_bg_diversity",       cg.main_image_bg_diversity,         "code", "info",    "主图背景多样性"),
    ("title_length_metric",           cg.title_length_metric,             "code", "info",    "标题字数"),
    ("total_tokens_metric",           cg.total_tokens_metric,             "code", "info",    "Token消耗"),
    ("total_duration_metric",         cg.total_duration_metric,           "code", "info",    "执行耗时"),
    ("total_cost_metric",             cg.total_cost_metric,               "code", "info",    "费用(RMB)"),
]


def get_grader_meta():
    return [
        {"id": g[0], "type": g[2], "severity": g[3], "label": g[4]}
        for g in GRADERS
    ]
