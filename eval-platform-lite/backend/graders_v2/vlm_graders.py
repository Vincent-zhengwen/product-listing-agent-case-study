"""
VLM Graders v2 — G18
Uses qwen-vl-max via DashScope (OpenAI-compatible API).
Reads images from local paths directly (bypasses HTTP download issue).
"""
import os
import json
import re
import base64
from pathlib import Path
from typing import Optional

from openai import OpenAI
from project_paths import resolve_agent_image_path_from_url


# ── VLM client (singleton) ──────────────────────────────────────────────────

_vlm_client: Optional[OpenAI] = None


def _get_vlm_client() -> Optional[OpenAI]:
    global _vlm_client
    if _vlm_client:
        return _vlm_client
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    _vlm_client = OpenAI(api_key=api_key, base_url=base_url)
    return _vlm_client


# ── Standard output format ──────────────────────────────────────────────────

def _result(grader_id: str, verdict: str, severity: str,
            failures: list = None, critique: str = "", confidence: str = "high"):
    return {
        "grader_id": grader_id,
        "verdict": verdict,
        "severity": severity,
        "failures": failures or [],
        "critique": critique,
        "confidence": confidence,
    }


def _get_local_path(img_dict: dict) -> Optional[str]:
    """Extract local file path from image dict."""
    path = img_dict.get("local_path") or img_dict.get("output_path") or ""
    if path and Path(path).exists():
        return path
    url = img_dict.get("url", "")
    candidate = resolve_agent_image_path_from_url(url)
    if candidate:
        return str(candidate)
    return None


def _image_to_base64_url(path: str) -> str:
    """Convert local image to base64 data URL for VLM API."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    suffix = Path(path).suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp"}.get(suffix.lstrip("."), "image/png")
    return f"data:{mime};base64,{data}"


def _extract_json(text: str) -> Optional[dict]:
    """Extract first JSON object from VLM response."""
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── G18: image_text_layout_quality ──────────────────────────────────────────

_G18_PROMPT = """请检查这张商品图中的中文文字排版质量，判断是否可发布。

检查项：
1. 文字是否有词被生硬切断换行（如把"流苏渐变层边"断成"流苏渐变层/边"）
2. 文字是否超出画面边界被截断
3. 文字与产品图像是否相互严重遮挡
4. 文字是否模糊不可读

判断标准：
- PASS: 文字排版自然，无上述问题
- FAIL: 存在上述任一问题
- 如果图片中没有文字，直接 PASS

只输出 JSON：
{"verdict": "pass"|"fail", "issues": ["具体问题描述..."], "confidence": "high"|"medium"|"low"}"""


def image_text_layout_quality(output: dict, **_) -> dict:
    """G18: VLM judges text layout quality in product images."""
    client = _get_vlm_client()
    if not client:
        return _result("image_text_layout_quality", "skipped", "warning",
                       critique="VLM API key 未配置", confidence="low")

    # Check both main_images and detail_image
    images_to_check = []
    for i, img in enumerate(output.get("main_images", [])):
        path = _get_local_path(img)
        if path:
            images_to_check.append((f"main_images[{i}]", path))

    detail = output.get("detail_image")
    if detail:
        detail_path = None
        if isinstance(detail, dict):
            detail_path = _get_local_path(detail)
        elif isinstance(detail, str) and Path(detail).exists():
            detail_path = detail
        if detail_path:
            images_to_check.append(("detail_image", detail_path))

    if not images_to_check:
        return _result("image_text_layout_quality", "pass", "warning",
                       critique="无可检测图片")

    model = os.getenv("GRADER_VLM_MODEL", "qwen-vl-max")
    failures = []

    for field, path in images_to_check:
        try:
            img_url = _image_to_base64_url(path)
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": img_url}},
                        {"type": "text", "text": _G18_PROMPT},
                    ],
                }],
                temperature=0.1,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            parsed = _extract_json(raw)

            if parsed and parsed.get("verdict") == "fail":
                issues = parsed.get("issues", [])
                failures.append({
                    "field": field,
                    "issue_type": "text_layout_problem",
                    "evidence": {"issues": issues,
                                 "vlm_confidence": parsed.get("confidence", "medium")},
                    "evidence_quote": f"{field} 文字排版问题: {'; '.join(issues[:2]) if issues else '见 VLM 判断'}",
                    "severity": "warning",
                    "suggested_fix": "调整 Pillow 文字渲染参数（字体大小/行宽/位置）",
                })
        except Exception as e:
            # Don't fail the whole grader on individual image errors
            failures.append({
                "field": field,
                "issue_type": "vlm_error",
                "evidence": {"error": str(e)[:80]},
                "evidence_quote": f"{field} VLM 调用失败: {str(e)[:60]}",
                "severity": "info",
                "suggested_fix": "检查 VLM API 连通性",
            })

    layout_failures = [f for f in failures if f["issue_type"] == "text_layout_problem"]
    verdict = "fail" if layout_failures else "pass"
    return _result("image_text_layout_quality", verdict, "warning", failures,
                   f"{len(layout_failures)} 张图片文字排版有问题" if layout_failures else "文字排版正常",
                   confidence="medium")
