"""Public data contracts for the listing Agent case study.

The real project has more fields and platform-specific adapters. This public
slice keeps only the interfaces needed to explain the Agent loop: source facts,
planning, generated assets, and delivery checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SourceInput:
    source_url: str
    target_platform: str
    category_hint: str


@dataclass(frozen=True)
class SourceFacts:
    product_subject: str
    category: str
    material: str
    shape: str
    style: str
    sizes: list[str]
    b2b_context_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImageJob:
    role: str
    source_evidence: str
    buyer_visible_text: str = ""


@dataclass(frozen=True)
class ListingPlan:
    title: str
    attributes: dict[str, str]
    main_image_jobs: list[ImageJob]
    detail_image_jobs: list[ImageJob]


@dataclass(frozen=True)
class ArtifactManifest:
    main_images: list[Path]
    detail_images: list[Path]
    detail_full: Path


@dataclass(frozen=True)
class QualityIssue:
    where: str
    message: str


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    issues: list[QualityIssue]
