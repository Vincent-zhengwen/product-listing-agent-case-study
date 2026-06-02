"""Delivery artifact checker example."""

from __future__ import annotations

from src.contracts import ArtifactManifest, QualityIssue, QualityReport


def check_artifacts(manifest: ArtifactManifest) -> QualityReport:
    issues: list[QualityIssue] = []

    if len(manifest.main_images) != 5:
        issues.append(QualityIssue("main_images", "主图必须正好 5 张"))
    if len(manifest.detail_images) < 8:
        issues.append(QualityIssue("detail_images", "详情图至少需要 8 屏"))
    if not manifest.detail_full:
        issues.append(QualityIssue("detail_full", "必须生成详情长图"))

    for path in [*manifest.main_images, *manifest.detail_images, manifest.detail_full]:
        if not path.exists():
            issues.append(QualityIssue(str(path), "资产文件不存在"))

    return QualityReport(passed=len(issues) == 0, issues=issues)
