"""Public runner example for the product listing Agent.

This file intentionally avoids production credentials, database writes, browser
profiles, and platform crawling. It shows the engineering shape of the Agent SDK
stage: read source facts, apply a playbook, verify the plan, check artifacts, and
return a delivery report.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.contracts import ArtifactManifest, ImageJob, ListingPlan, SourceInput
from src.tools.artifact_checker import check_artifacts
from src.tools.fact_verifier_example import verify_plan
from src.tools.source_fetcher_contract import fetch_source_facts


SDK_ASSET_DIR = PROJECT_ROOT / "evolution" / "assets" / "sdk"


def run_listing_case(source: SourceInput) -> dict:
    facts = fetch_source_facts(source)
    plan = build_tablecloth_plan()
    plan_report = verify_plan(plan, facts)
    manifest = build_tablecloth_manifest()
    artifact_report = check_artifacts(manifest)

    return {
        "source": asdict(source),
        "facts": asdict(facts),
        "plan": asdict(plan),
        "quality": {
            "plan_passed": plan_report.passed,
            "artifact_passed": artifact_report.passed,
            "issues": [asdict(issue) for issue in [*plan_report.issues, *artifact_report.issues]],
        },
    }


def build_tablecloth_plan() -> ListingPlan:
    return ListingPlan(
        title="棉麻花朵桌布地中海风长方形餐桌台布",
        attributes={
            "材质": "棉麻",
            "类别": "桌布",
            "风格": "地中海风",
            "形状": "长方形",
            "规格尺寸": "60*60cm 至 140*360cm 多规格",
        },
        main_image_jobs=[
            ImageJob("铺桌首图", "source:image:scene", "铺出餐桌氛围"),
            ImageJob("尺寸规格", "source:attr:sizes", "多规格可选"),
            ImageJob("面料纹理", "source:image:detail", "棉麻纹理清晰"),
            ImageJob("边缘垂坠", "source:image:edge", "桌沿自然垂落"),
            ImageJob("浅底确认", "source:image:whitebg", "花朵图案确认"),
        ],
        detail_image_jobs=[
            ImageJob("场景效果", "source:image:scene", "换一块桌布, 餐桌更有层次"),
            ImageJob("卖点总览", "source:facts", "材质、花型、规格集中确认"),
            ImageJob("面料细节", "source:image:detail", "棉麻肌理适合日常餐桌"),
            ImageJob("尺寸选择", "source:attr:sizes", "按餐桌大小选择规格"),
            ImageJob("款式展示", "source:image:sku", "不同花型适配不同空间"),
            ImageJob("规格确认", "source:attr:sizes", "购买前确认尺寸"),
            ImageJob("服务说明", "source:merchant_context", "服务信息低权重展示"),
            ImageJob("收口长图", "source:generated_assets", "形成完整详情页"),
        ],
    )


def build_tablecloth_manifest() -> ArtifactManifest:
    return ArtifactManifest(
        main_images=[SDK_ASSET_DIR / f"main_{idx}.jpg" for idx in range(1, 6)],
        detail_images=[SDK_ASSET_DIR / f"detail_{idx:02d}.jpg" for idx in range(1, 9)],
        detail_full=SDK_ASSET_DIR / "detail_full.jpg",
    )


if __name__ == "__main__":
    report = run_listing_case(
        SourceInput(
            source_url="https://www.yiwugo.com/product/detail/982191293.html",
            target_platform="taobao",
            category_hint="桌布 / 家纺软装",
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
