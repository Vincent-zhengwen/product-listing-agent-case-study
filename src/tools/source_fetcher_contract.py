"""Source fetcher contract example.

This is not the production crawler. It shows the shape returned by the source
reading tool after the Agent has a source URL to work with.
"""

from __future__ import annotations

from src.contracts import SourceFacts, SourceInput


def fetch_source_facts(source: SourceInput) -> SourceFacts:
    """Return publishable facts extracted from the tablecloth source page."""
    if "yiwugo.com/product/detail/982191293.html" not in source.source_url:
        raise ValueError("This public example only includes the tablecloth case.")

    return SourceFacts(
        product_subject="棉麻彩色桌布",
        category=source.category_hint,
        material="棉麻",
        shape="长方形",
        style="地中海风",
        sizes=[
            "60*60cm",
            "90*90cm",
            "140*140cm",
            "140*180cm",
            "140*220cm",
            "140*360cm",
        ],
        b2b_context_terms=[
            "工厂诚招代理",
            "支持一件代发",
            "专供跨境和亚马逊",
            "欢迎 FBA 采购",
            "开票另加税点",
        ],
    )
