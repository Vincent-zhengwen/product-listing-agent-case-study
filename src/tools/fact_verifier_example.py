"""Rule-based fact verifier example.

The production project used a larger verifier. This public version demonstrates
the important boundary: buyer-visible copy must stay grounded in source facts and
must not leak B2B or internal production language.
"""

from __future__ import annotations

from src.contracts import ListingPlan, QualityIssue, QualityReport, SourceFacts


B2B_TERMS = ("批发", "代理", "一件代发", "跨境专供", "厂家直销", "MOQ", "OEM", "FBA")
INTERNAL_TERMS = ("生成", "模型", "提示词", "主图 1", "详情 01", "demo", "preview")
UNSUPPORTED_CLAIMS = ("食品级", "防水", "防油", "零甲醛", "认证", "全网最低")


def verify_plan(plan: ListingPlan, facts: SourceFacts) -> QualityReport:
    issues: list[QualityIssue] = []

    visible_texts = [plan.title]
    visible_texts.extend(plan.attributes.values())
    visible_texts.extend(job.buyer_visible_text for job in plan.main_image_jobs)
    visible_texts.extend(job.buyer_visible_text for job in plan.detail_image_jobs)

    for index, text in enumerate(visible_texts):
        if not text:
            continue
        where = f"buyer_visible_text[{index}]"
        for term in B2B_TERMS:
            if term in text:
                issues.append(QualityIssue(where, f"包含供货语境词: {term}"))
        for term in INTERNAL_TERMS:
            if term in text:
                issues.append(QualityIssue(where, f"包含内部过程词: {term}"))
        for term in UNSUPPORTED_CLAIMS:
            if term in text and term not in _fact_corpus(facts):
                issues.append(QualityIssue(where, f"缺少事实依据: {term}"))

    material = plan.attributes.get("材质", "")
    if material and facts.material and material != facts.material:
        issues.append(QualityIssue("attributes.材质", "材质必须来自货源事实"))

    size_text = plan.attributes.get("规格尺寸", "")
    if size_text and not any(size in size_text for size in facts.sizes):
        issues.append(QualityIssue("attributes.规格尺寸", "规格尺寸必须引用货源中的真实规格"))

    return QualityReport(passed=len(issues) == 0, issues=issues)


def _fact_corpus(facts: SourceFacts) -> str:
    return " ".join(
        [
            facts.product_subject,
            facts.category,
            facts.material,
            facts.shape,
            facts.style,
            *facts.sizes,
        ]
    )
