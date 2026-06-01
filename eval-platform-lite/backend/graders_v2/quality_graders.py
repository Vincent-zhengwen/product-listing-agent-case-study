"""
Listing Quality Graders.

These graders judge the buyer-visible quality of a generated listing. They are
intentionally separate from hard publishability gates: a listing can be safe to
publish while still being weak, flat, or poorly fitted to the category.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from project_paths import resolve_agent_image_path_from_url


QUALITY_RUBRIC_VERSION = "listing-quality-v2-image-depth"
_VLM_CACHE_DIR = Path("/tmp/eval_quality_vlm")

_text_client: Optional[OpenAI] = None
_vlm_client: Optional[OpenAI] = None


def _get_client() -> Optional[OpenAI]:
    global _text_client
    if _text_client:
        return _text_client
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    _text_client = OpenAI(api_key=api_key, base_url=base_url)
    return _text_client


def _get_vlm_client() -> Optional[OpenAI]:
    global _vlm_client
    if _vlm_client:
        return _vlm_client
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    _vlm_client = OpenAI(api_key=api_key, base_url=base_url)
    return _vlm_client


def _result(grader_id: str, verdict: str, score: float | None = None,
            issues: list | None = None, critique: str = "",
            confidence: str = "medium", dimension_scores: dict | None = None,
            positives: list | None = None, severity: str = "warning") -> dict:
    quality_verdict = _quality_verdict(score) if score is not None else verdict
    failures = []
    if verdict == "fail":
        for issue in issues or []:
            failures.append({
                "field": issue.get("field", "listing"),
                "issue_type": issue.get("code", "listing_quality_issue"),
                "evidence": {
                    "reason": issue.get("reason", ""),
                    "impact": issue.get("impact", ""),
                },
                "evidence_quote": issue.get("reason", issue.get("code", "质量问题")),
                "severity": severity,
                "suggested_fix": issue.get("suggested_fix", "围绕该质量维度重写/重排对应内容"),
            })

    return {
        "grader_id": grader_id,
        "verdict": verdict,
        "severity": severity,
        "score": score,
        "quality_verdict": quality_verdict,
        "dimension_scores": dimension_scores or {},
        "issues": issues or [],
        "positives": positives or [],
        "failures": failures,
        "critique": critique,
        "confidence": confidence,
        "rubric_version": QUALITY_RUBRIC_VERSION,
    }


def _skip(grader_id: str, reason: str) -> dict:
    return {
        "grader_id": grader_id,
        "verdict": "skipped",
        "severity": "warning",
        "score": None,
        "failures": [],
        "critique": reason,
        "confidence": "low",
        "skipped_reason": reason,
        "rubric_version": QUALITY_RUBRIC_VERSION,
    }


def _quality_verdict(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 86:
        return "strong"
    if score >= 75:
        return "ok"
    if score >= 60:
        return "weak"
    return "fail"


def _pass_fail(score: float | None) -> str:
    if score is None:
        return "skipped"
    return "pass" if score >= 75 else "fail"


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _call_llm(system_prompt: str, user_content: str, max_tokens: int = 2200) -> Optional[dict]:
    client = _get_client()
    if not client:
        return None
    model = os.getenv("QUALITY_TEXT_MODEL") or os.getenv("GRADER_LLM_MODEL") or os.getenv("GRADER_MODEL") or "qwen-plus"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=max_tokens,
            timeout=float(os.getenv("QUALITY_LLM_TIMEOUT", "45")),
        )
        text = resp.choices[0].message.content.strip()
        parsed = _extract_json(text)
        if parsed:
            return parsed
        repair = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是 JSON 修复器。只输出一个合法 JSON 对象，不要 Markdown，不要解释。"},
                {"role": "user", "content": f"把下面内容修复成合法 JSON。字段应保留 score、dimension_scores、summary、positives、issues、confidence。\n\n{text[:6000]}"},
            ],
            temperature=0,
            max_tokens=1400,
            timeout=float(os.getenv("QUALITY_LLM_TIMEOUT", "45")),
        )
        return _extract_json(repair.choices[0].message.content.strip())
    except Exception:
        return None


def _local_path(img: dict) -> Optional[str]:
    if not isinstance(img, dict):
        return None
    for key in ("local_path", "output_path", "path"):
        path = img.get(key) or ""
        if path and Path(path).exists():
            return path
    candidate = resolve_agent_image_path_from_url(img.get("url", ""))
    return str(candidate) if candidate else None


def _prepare_image_for_vlm(path: str, max_dim: int = 900) -> str:
    """Downscale image before VLM calls to keep quality eval fast and stable."""
    try:
        p = Path(path)
        stat_key = f"{p.resolve()}:{p.stat().st_mtime_ns}:{p.stat().st_size}:{max_dim}"
        digest = hashlib.md5(stat_key.encode()).hexdigest()
        _VLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        out = _VLM_CACHE_DIR / f"{digest}.jpg"
        if out.exists() and out.stat().st_size > 500:
            return str(out)
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = min(1.0, max_dim / max(w, h))
            if scale < 1.0:
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
            im.save(out, format="JPEG", quality=82, optimize=True)
        return str(out)
    except Exception:
        return path


def _image_to_base64_url(path: str) -> str:
    path = _prepare_image_for_vlm(path)
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    suffix = Path(path).suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/jpeg")
    return f"data:{mime};base64,{data}"


def _contact_sheet(image_items: list[tuple[str, str]], sheet_name: str,
                   thumb_size: tuple[int, int] = (260, 260),
                   columns: int = 3) -> str:
    """Create one labeled contact sheet so VLM sees the whole set in one image."""
    safe_items = []
    for label, path in image_items:
        if path and Path(path).exists():
            safe_items.append((label, path))
    if not safe_items:
        return ""

    digest_src = "|".join(
        f"{label}:{Path(path).resolve()}:{Path(path).stat().st_mtime_ns}:{Path(path).stat().st_size}"
        for label, path in safe_items
    )
    digest = hashlib.md5((sheet_name + digest_src).encode()).hexdigest()
    _VLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = _VLM_CACHE_DIR / f"sheet_{sheet_name}_{digest}.jpg"
    if out.exists() and out.stat().st_size > 500:
        return str(out)

    label_h = 28
    gap = 12
    cols = max(1, min(columns, len(safe_items)))
    rows = (len(safe_items) + cols - 1) // cols
    cell_w = thumb_size[0]
    cell_h = thumb_size[1] + label_h
    canvas = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * gap, rows * cell_h + (rows + 1) * gap),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("Arial.ttf", 15)
    except Exception:
        font = ImageFont.load_default()

    for idx, (label, path) in enumerate(safe_items):
        row = idx // cols
        col = idx % cols
        x = gap + col * (cell_w + gap)
        y = gap + row * (cell_h + gap)
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                im.thumbnail(thumb_size, Image.LANCZOS)
                px = x + (cell_w - im.width) // 2
                py = y + label_h + (thumb_size[1] - im.height) // 2
                canvas.paste(im, (px, py))
        except Exception:
            pass
        draw.rectangle([x, y, x + cell_w, y + label_h - 2], fill=(245, 245, 245))
        draw.text((x + 6, y + 6), label[:38], fill=(30, 30, 30), font=font)

    canvas.save(out, format="JPEG", quality=82, optimize=True)
    return str(out)


def _compact_listing(output: dict) -> dict:
    return {
        "title": output.get("title", ""),
        "attributes": output.get("attributes") or {},
        "selling_points": output.get("selling_points") or [],
        "body_copy": output.get("body_copy", "")[:1800],
        "main_image_roles": [
            {"index": idx + 1, "role": img.get("role") or img.get("purpose") or img.get("label", "")}
            for idx, img in enumerate(output.get("main_images", []) or [])
            if isinstance(img, dict)
        ],
        "detail_count": len(output.get("detail_images", []) or []),
    }


def _compact_source(source_data: dict) -> dict:
    attrs = source_data.get("attributes") or {}
    return {
        "title": source_data.get("title", ""),
        "keyword": source_data.get("keyword", ""),
        "attributes": attrs,
        "attributes_count": len([k for k in attrs if not str(k).startswith("_")]),
        "images_count": len(source_data.get("images") or []),
        "raw_attributes": str(source_data.get("raw_attributes") or "")[:800],
    }


def _normalize_parsed(parsed: dict) -> tuple[float, dict, list, list, str, str]:
    score = float(parsed.get("score", 0))
    score = max(0.0, min(100.0, score))
    dimensions = parsed.get("dimension_scores") if isinstance(parsed.get("dimension_scores"), dict) else {}
    issues = parsed.get("issues") if isinstance(parsed.get("issues"), list) else []
    positives = parsed.get("positives") if isinstance(parsed.get("positives"), list) else []
    critique = parsed.get("summary") or parsed.get("critique") or ""
    confidence = parsed.get("confidence") or "medium"
    return score, dimensions, issues[:8], positives[:6], critique, confidence


def _issue(code: str, field: str, reason: str, impact: str, suggested_fix: str) -> dict:
    return {
        "code": code,
        "field": field,
        "reason": reason,
        "impact": impact,
        "suggested_fix": suggested_fix,
    }


def _add_issue_once(issues: list, issue: dict) -> None:
    key = (issue.get("code"), issue.get("field"), issue.get("reason"))
    for existing in issues:
        if (
            isinstance(existing, dict)
            and (existing.get("code"), existing.get("field"), existing.get("reason")) == key
        ):
            return
    issues.append(issue)


def _image_metric(path: str) -> dict:
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            width, height = im.size
            small = im.resize((128, 128), Image.LANCZOS)
            pixels = list(small.getdata())
            total = max(1, len(pixels))
            light_ratio = sum(1 for r, g, b in pixels if r > 242 and g > 242 and b > 242) / total
            dark_ratio = sum(1 for r, g, b in pixels if r < 45 and g < 45 and b < 45) / total
            gray = small.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_density = sum(1 for p in edges.getdata() if p > 28) / total
            return {
                "width": width,
                "height": height,
                "light_ratio": round(light_ratio, 3),
                "dark_ratio": round(dark_ratio, 3),
                "edge_density": round(edge_density, 3),
            }
    except Exception:
        return {}


def _fingerprints(items: list[tuple[str, str]]) -> list[dict]:
    try:
        import imagehash
    except ImportError:
        return []

    fps = []
    for label, path in items:
        try:
            with Image.open(path) as im:
                fps.append({
                    "label": label,
                    "path": path,
                    "phash": imagehash.phash(im),
                    "ahash": imagehash.average_hash(im),
                    "dhash": imagehash.dhash(im),
                    "metric": _image_metric(path),
                })
        except Exception:
            continue
    return fps


def _visual_similarity_pairs(
    primary_items: list[tuple[str, str]],
    secondary_items: list[tuple[str, str]] | None = None,
    *,
    max_pairs: int = 8,
) -> list[dict]:
    primary = _fingerprints(primary_items)
    secondary = _fingerprints(secondary_items) if secondary_items is not None else primary
    pairs = []
    for i, a in enumerate(primary):
        start = i + 1 if secondary_items is None else 0
        for b in secondary[start:]:
            if a["path"] == b["path"]:
                continue
            phash_distance = int(a["phash"] - b["phash"])
            ahash_distance = int(a["ahash"] - b["ahash"])
            dhash_distance = int(a["dhash"] - b["dhash"])
            very_close = (
                phash_distance <= 18
                or ahash_distance <= 11
                or (phash_distance <= 24 and dhash_distance <= 24)
            )
            moderately_close = (
                phash_distance <= 24
                or ahash_distance <= 15
                or dhash_distance <= 22
            )
            if not (very_close or moderately_close):
                continue
            pairs.append({
                "a": a["label"],
                "b": b["label"],
                "phash": phash_distance,
                "ahash": ahash_distance,
                "dhash": dhash_distance,
                "strength": "very_close" if very_close else "close",
            })
    pairs.sort(key=lambda p: (p["strength"] != "very_close", p["phash"] + p["ahash"] + p["dhash"]))
    return pairs[:max_pairs]


def _visual_set_signals(
    main_items: list[tuple[str, str]],
    detail_items: list[tuple[str, str]] | None = None,
) -> dict:
    detail_items = detail_items or []
    main_metrics = [
        {"label": label, **_image_metric(path)}
        for label, path in main_items
    ]
    detail_metrics = [
        {"label": label, **_image_metric(path)}
        for label, path in detail_items
    ]
    sparse_details = [
        m["label"] for m in detail_metrics
        if m.get("light_ratio", 0) >= 0.72 and m.get("edge_density", 1) <= 0.13
    ]
    sparse_mains = [
        m["label"] for m in main_metrics
        if m.get("light_ratio", 0) >= 0.75 and m.get("edge_density", 1) <= 0.16
    ]
    return {
        "main_near_duplicates": _visual_similarity_pairs(main_items, max_pairs=6),
        "detail_near_duplicates": _visual_similarity_pairs(detail_items, max_pairs=8) if len(detail_items) >= 2 else [],
        "main_detail_reuse": _visual_similarity_pairs(main_items, detail_items, max_pairs=10) if detail_items else [],
        "sparse_main_images": sparse_mains,
        "sparse_detail_screens": sparse_details,
        "main_metrics": main_metrics,
        "detail_metrics": detail_metrics,
    }


def _cap_score(score: float, cap: float) -> float:
    return min(score, cap)


def _apply_main_image_signal_caps(score: float, issues: list, signals: dict) -> float:
    near_pairs = [p for p in signals.get("main_near_duplicates", []) if p.get("strength") == "very_close"]
    if near_pairs:
        pair_text = "、".join(f"{p['a']}≈{p['b']}" for p in near_pairs[:3])
        _add_issue_once(issues, _issue(
            "main_images_repetitive",
            "main_images",
            f"图像指纹显示主图组存在高相似画面：{pair_text}。这类问题不是源图复用本身，而是买家看到的 5 张主图没有贡献足够不同的信息。",
            "会让主图组像同一素材反复换版，削弱多角度/场景/细节确认价值。",
            "保留一张最强商品识别图，其余主图改成真实使用场景、局部结构、尺寸/SKU 对比或开关/功能证明。",
        ))
        if len(near_pairs) >= 5:
            score = _cap_score(score, 62)
        elif len(near_pairs) >= 3:
            score = _cap_score(score, 68)
        elif len(near_pairs) >= 2:
            score = _cap_score(score, 70)
        else:
            score = _cap_score(score, 74)

    sparse = signals.get("sparse_main_images", [])
    if sparse:
        _add_issue_once(issues, _issue(
            "main_image_low_information",
            "main_images",
            f"{'、'.join(sparse[:3])} 的画面留白过高且边缘信息少，疑似白底孤立图/低信息确认图。",
            "单图可能干净，但放在 5 张主图里会占掉一个本应用来解释卖点或场景的位置。",
            "将低信息白底图替换为带明确购买理由的细节、材质、尺寸或使用方式图。",
        ))
        score = _cap_score(score, 80)

    return score


def _apply_detail_signal_caps(score: float, issues: list, signals: dict) -> float:
    main_detail = [p for p in signals.get("main_detail_reuse", []) if p.get("strength") == "very_close"]
    detail_pairs = [p for p in signals.get("detail_near_duplicates", []) if p.get("strength") == "very_close"]
    if main_detail or detail_pairs:
        reuse_count = len(main_detail) + len(detail_pairs)
        examples = []
        examples.extend(f"{p['a']}≈{p['b']}" for p in main_detail[:3])
        examples.extend(f"{p['a']}≈{p['b']}" for p in detail_pairs[:3])
        _add_issue_once(issues, _issue(
            "detail_visual_repetition",
            "detail_images",
            f"详情页存在高相似/复用画面：{'、'.join(examples[:5])}。问题不是使用源图，而是详情屏之间没有形成新的解释价值。",
            "详情页会显得像把主图素材纵向堆叠，买家看完仍缺少功能、规格、使用步骤或差异确认。",
            "把重复画面替换为不同问题的证明屏：使用前后对比、结构拆解、尺寸参照、SKU 差异、清洗/收纳步骤。",
        ))
        if reuse_count >= 8:
            score = _cap_score(score, 62)
        elif reuse_count >= 5:
            score = _cap_score(score, 66)
        elif reuse_count >= 3:
            score = _cap_score(score, 68)
        elif reuse_count >= 2:
            score = _cap_score(score, 72)
        else:
            score = _cap_score(score, 76)

    sparse = signals.get("sparse_detail_screens", [])
    if len(sparse) >= 2:
        _add_issue_once(issues, _issue(
            "detail_low_information_screen",
            "detail_images",
            f"{'、'.join(sparse[:4])} 的视觉信息偏薄，存在参数表/售后/白底确认页占比过高的问题。",
            "详情页后半段会从说服转成填充，无法继续回答买家对功能、材质、尺寸和使用场景的疑问。",
            "压缩参数/售后页，补充一屏可视化证据，例如尺寸实拍、功能动线、材质近景或场景对比。",
        ))
        score = _cap_score(score, 70 if len(sparse) >= 3 else 76)

    return score


QUALITY_SYSTEM = """你是资深淘宝上架内容质量评审。

你只评价买家可见质量和 Agent 产物质量，不评价源图是否复用；源图能直接用时完全可以用。
必须严格按 rubric 打分，给出可行动问题。不要泛泛夸赞。

评分口径：
- 86-100：强，接近可直接作为优秀商品页使用
- 75-85：可用，质量基本达标
- 60-74：偏弱，可发布但明显普通或有转化短板
- 0-59：差，存在明显质量问题或像半成品

只输出 JSON，不要 Markdown。"""


def copy_conversion_quality(output: dict, category: str = "", source_data: dict = None, **_) -> dict:
    """Judge title, selling points, attributes, and body copy as a buyer-facing listing."""
    if not _get_client():
        return _skip("copy_conversion_quality", "LLM API key 未配置")

    source_data = source_data or {}
    prompt = f"""请评价这套淘宝上架文案的 C 端转化质量。

品类：{category}

源页摘要：
{json.dumps(_compact_source(source_data), ensure_ascii=False, indent=2)}

Agent 上架内容：
{json.dumps(_compact_listing(output or {}), ensure_ascii=False, indent=2)}

Rubric：
1. 标题质量 20 分：搜索词自然、核心类目清楚、不是批发标题堆砌。
2. 卖点质量 25 分：有场景/利益/可观察证据，不只是参数复述。
3. 正文质量 20 分：有购买理由和节奏，不像模板或后台说明。
4. 事实纪律 20 分：具体功能/尺寸/材质/容量等有依据；无法确认时不硬写。
5. 买家语言 15 分：像淘宝商品页，不含 B2B、内部流程、AI/生成/货源等话术。

返回 JSON：
{{
  "score": 0-100,
  "dimension_scores": {{"title":0-20,"selling_points":0-25,"body_copy":0-20,"fact_discipline":0-20,"buyer_language":0-15}},
  "summary": "一句话结论",
  "positives": ["最多3条"],
  "issues": [
    {{"code":"copy_fact_unsupported|copy_b2b_tone|selling_points_flat|title_keyword_stuffing|body_template_like|other", "field":"title/selling_points/body_copy/attributes", "reason":"具体证据", "impact":"对买家或发布质量的影响", "suggested_fix":"怎么改"}}
  ],
  "confidence": "high|medium|low"
}}"""
    parsed = _call_llm(QUALITY_SYSTEM, prompt)
    if not parsed:
        return _skip("copy_conversion_quality", "LLM 输出解析失败")
    score, dims, issues, positives, critique, confidence = _normalize_parsed(parsed)
    return _result("copy_conversion_quality", _pass_fail(score), score, issues, critique, confidence, dims, positives)


def category_fit_quality(output: dict, category: str = "", source_data: dict = None, **_) -> dict:
    """Judge whether the listing speaks to the right category purchase motivations."""
    if not _get_client():
        return _skip("category_fit_quality", "LLM API key 未配置")

    category_notes = {
        "灯具": "重点看亮灯效果、造型、开关/调节、规格、床头/书桌场景；避免护眼/助眠/儿童专用等无依据风险词。",
        "香薰": "重点看香型、瓶身、藤条/扩香形式、空间氛围、礼品感；避免治疗、安神、净化空气、健康安全等功效词。",
        "收纳": "重点看分类、容量、取放、开合、尺寸/桌面适配；不要把被收纳物当赠品，不要无依据夸大容量。",
        "花瓶": "重点看瓶型、材质、颜色、尺寸、摆放场景；不要把花材当商品卖点。",
    }
    note = category_notes.get(category, "按该品类真实购买动机判断：是否讲清商品本体、使用场景、关键选择理由和可信规格。")
    prompt = f"""请判断这套上架内容是否符合品类购买动机。

品类：{category}
品类质量标准：{note}

源页摘要：
{json.dumps(_compact_source(source_data or {}), ensure_ascii=False, indent=2)}

Agent 上架内容：
{json.dumps(_compact_listing(output or {}), ensure_ascii=False, indent=2)}

Rubric：
1. 品类核心动机覆盖 35 分
2. 商品本体聚焦 25 分
3. 场景/人群表达准确 20 分
4. 风险词和错位卖点控制 20 分

返回 JSON：
{{
  "score": 0-100,
  "dimension_scores": {{"category_motivation":0-35,"product_focus":0-25,"scene_fit":0-20,"risk_control":0-20}},
  "summary": "一句话结论",
  "positives": ["最多3条"],
  "issues": [
    {{"code":"category_motivation_missing|product_focus_drift|scene_mismatch|unsupported_risk_claim|category_generic|other", "field":"listing", "reason":"具体证据", "impact":"影响", "suggested_fix":"怎么改"}}
  ],
  "confidence": "high|medium|low"
}}"""
    parsed = _call_llm(QUALITY_SYSTEM, prompt)
    if not parsed:
        return _skip("category_fit_quality", "LLM 输出解析失败")
    score, dims, issues, positives, critique, confidence = _normalize_parsed(parsed)
    return _result("category_fit_quality", _pass_fail(score), score, issues, critique, confidence, dims, positives)


def _call_vlm(
    grader_id: str,
    output: dict,
    category: str,
    prompt: str,
    image_items: list[tuple[str, str]],
    max_tokens: int = 1200,
    *,
    visual_signals: dict | None = None,
    include_individual: bool = False,
) -> dict:
    client = _get_vlm_client()
    if not client:
        return _skip(grader_id, "VLM API key 未配置")
    if not image_items:
        return _skip(grader_id, "没有可读取图片")

    sheet = _contact_sheet(
        image_items,
        grader_id,
        thumb_size=(280, 280) if grader_id == "main_image_quality" else (280, 420),
        columns=3 if grader_id == "main_image_quality" else 2,
    )
    if not sheet:
        return _skip(grader_id, "图片转码失败")
    content = [
        {"type": "text", "text": "下面是一张带标签的联系表，请按标签定位每张图。"},
        {"type": "image_url", "image_url": {"url": _image_to_base64_url(sheet)}},
    ]
    if include_individual:
        for label, path in image_items[:9]:
            content.extend([
                {"type": "text", "text": f"单图复核：{label}"},
                {"type": "image_url", "image_url": {"url": _image_to_base64_url(path)}},
            ])

    signal_text = ""
    if visual_signals:
        signal_text = "\n\n图像集合的程序化信号（只能作为线索，最终请以视觉判断为准）：\n" + json.dumps(
            {
                "main_near_duplicates": visual_signals.get("main_near_duplicates", []),
                "detail_near_duplicates": visual_signals.get("detail_near_duplicates", []),
                "main_detail_reuse": visual_signals.get("main_detail_reuse", []),
                "sparse_main_images": visual_signals.get("sparse_main_images", []),
                "sparse_detail_screens": visual_signals.get("sparse_detail_screens", []),
            },
            ensure_ascii=False,
            indent=2,
        )
    content.append({"type": "text", "text": prompt + signal_text})

    model = os.getenv("QUALITY_VLM_MODEL") or os.getenv("GRADER_VLM_MODEL") or "qwen-vl-max"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=max_tokens,
            timeout=float(os.getenv("QUALITY_VLM_TIMEOUT", "75")),
        )
    except Exception as exc:
        return _skip(grader_id, f"VLM 调用失败: {str(exc)[:120]}")

    parsed = _extract_json(resp.choices[0].message.content.strip())
    if not parsed:
        return _skip(grader_id, "VLM 输出解析失败")
    score, dims, issues, positives, critique, confidence = _normalize_parsed(parsed)
    if visual_signals:
        before = score
        if grader_id == "main_image_quality":
            score = _apply_main_image_signal_caps(score, issues, visual_signals)
        elif grader_id == "detail_page_quality":
            score = _apply_detail_signal_caps(score, issues, visual_signals)
        if score < before:
            critique = f"{critique} 程序化图像集合信号将分数上限从 {before:.0f} 校准到 {score:.0f}。".strip()
    issues = issues[:10]
    return _result(grader_id, _pass_fail(score), score, issues, critique, confidence, dims, positives)


def main_image_quality(output: dict, category: str = "", source_data: dict = None, **_) -> dict:
    """Judge the five main images as a Taobao buyer would see them."""
    images = []
    for idx, img in enumerate((output or {}).get("main_images", []) or []):
        path = _local_path(img)
        if path:
            role = img.get("role") or img.get("purpose") or ""
            images.append((f"main_image_{idx + 1} {role}".strip(), path))
    signals = _visual_set_signals(images)
    prompt = f"""你是资深淘宝主图质量评审。请按“专业买家视角 + 真实淘宝上架转化”审这 5 张主图。

品类：{category}
商品标题：{(output or {}).get("title", "")}
源页摘要：
{json.dumps(_compact_source(source_data or {}), ensure_ascii=False, indent=2)}
上架文案摘要：
{json.dumps(_compact_listing(output or {}), ensure_ascii=False, indent=2)}

重要规则：源图复用不扣分。只看买家可见质量。
但如果最终主图组反复使用同一主体、同一场景、同一构图，只是换文字或轻微裁切，要扣分；这是“输出信息重复”，不是“源图复用”。

审查步骤：
1. 逐张检查 main_image_1 到 main_image_5：它在主图组里承担什么任务，是否真的给了新信息。
2. 再看整组：是否从点击、商品识别、功能证明、场景代入、尺寸/SKU确认形成购买路径。
3. 必须找深层问题：同素材重复、伪多样化、详情页文字塞进主图、规格图字太小、白底孤立图低价值、使用场景不可信、产品与卖点不一致。
4. 不能只说“整体不错”。如果不是接近专业商品页，请指出至少 3 个具体可修问题。

Rubric：
1. 首图点击欲 20 分：第一眼是否想点，商品主体是否清楚，有无购买触发。
2. 商品识别清晰度 15 分：主体、颜色、结构、比例是否清楚可信。
3. 五图任务分工 30 分：是否覆盖首图/细节/场景/规格或 SKU/确认图，而不是五张都重复。
4. 功能/场景证据 15 分：是否用图证明核心功能、尺寸、使用方式或搭配场景。
5. 视觉商业质感 10 分：光线、构图、留白、质感是否像正式商品页。
6. 图文干扰控制 10 分：文字是否遮挡商品、过密、低对比或像详情页缩略图。

分数上限：
- 有 2 张以上主图基本是同一主体/同一构图换版：总分最高 74。
- 有白底孤立图占坑且没有新增购买信息：总分最高 80。
- 主图主要靠大字卖点而非商品/场景/功能证明：总分最高 78。
- 5 张都能各自回答不同买家问题，且首图强，才可超过 85。

返回 JSON：
{{
  "score": 0-100,
  "dimension_scores": {{"first_image_clickability":0-20,"subject_clarity":0-15,"role_diversity":0-30,"functional_scene_proof":0-15,"commercial_polish":0-10,"text_interference":0-10}},
  "summary": "一句话结论",
  "positives": ["最多3条"],
  "issues": [
    {{"code":"first_image_weak|main_images_repetitive|subject_unclear|text_overcrowded|visual_polish_low|role_missing|functional_proof_missing|low_information_image|scene_unconvincing|other", "field":"main_images[n]", "reason":"具体证据", "impact":"影响", "suggested_fix":"怎么改"}}
  ],
  "confidence": "high|medium|low"
}}"""
    return _call_vlm(
        "main_image_quality",
        output or {},
        category,
        prompt,
        images[:5],
        max_tokens=1800,
        visual_signals=signals,
        include_individual=True,
    )


def detail_page_quality(output: dict, category: str = "", source_data: dict = None, **_) -> dict:
    """Judge detail page narrative, hierarchy, and persuasion from detail screens."""
    main_items = []
    for idx, img in enumerate((output or {}).get("main_images", []) or []):
        path = _local_path(img)
        if path:
            main_items.append((f"main_image_{idx + 1}", path))

    detail_images = []
    for idx, img in enumerate((output or {}).get("detail_images", []) or []):
        if img.get("purpose") == "stitched":
            continue
        path = _local_path(img)
        if path:
            detail_images.append((f"detail_screen_{idx + 1}", path))
    if not detail_images and (output or {}).get("detail_image"):
        path = _local_path(output.get("detail_image"))
        if path:
            detail_images.append(("stitched_detail", path))
    signals = _visual_set_signals(main_items, detail_images)

    prompt = f"""你是资深淘宝详情页质量评审。请按“买家连续下滑详情页”的真实体验审这些详情屏。

品类：{category}
商品标题：{(output or {}).get("title", "")}
源页摘要：
{json.dumps(_compact_source(source_data or {}), ensure_ascii=False, indent=2)}
上架文案摘要：
{json.dumps(_compact_listing(output or {}), ensure_ascii=False, indent=2)}

重要规则：
- 源图能直接用就可以，不因源图复用扣分。
- 但详情页如果只是把主图/源图换文案后纵向堆叠，缺少新证据、新角度、新信息，要扣分。
- 参数表、售后承诺、白底确认页不是不能有，但如果占据详情页关键屏且没有转化价值，要扣分。

审查步骤：
1. 逐屏检查 detail_screen_1...：每屏回答了买家的哪个疑问。
2. 检查详情页是否形成路径：场景痛点 → 核心功能 → 结构/材质/尺寸/SKU → 使用/清洗/售后。
3. 必须找深层问题：与主图重复、详情屏彼此重复、后半段 filler、信息很薄、文字过小/层级弱、功能没有视觉证明、产品场景不真实。
4. 不能只停留在“首屏不够吸引/文字层级弱”这类浅问题；请指出组合层面的缺陷。

Rubric：
1. 首屏吸引与场景代入 15 分
2. 详情说服顺序 20 分：是否从场景/核心卖点/细节/规格/服务自然推进。
3. 逐屏信息增量 25 分：每屏是否提供新证据，而不是重复主图/重复同一素材。
4. 图文层级和可读性 15 分
5. 品类关键信息覆盖 15 分
6. 模板感/填充感控制 10 分

分数上限：
- 详情屏与主图或详情屏之间有明显重复，且没有新增解释价值：总分最高 72。
- 详情页超过 2 屏像参数/售后/白底确认 filler：总分最高 76。
- 核心卖点没有视觉证据，只靠文案说：总分最高 78。
- 只有在每屏都有不同买家问题和清晰证据时，才可超过 85。

返回 JSON：
{{
  "score": 0-100,
  "dimension_scores": {{"opening_hook":0-15,"persuasion_flow":0-20,"information_gain":0-25,"visual_hierarchy":0-15,"category_info":0-15,"template_control":0-10}},
  "summary": "一句话结论",
  "positives": ["最多3条"],
  "issues": [
    {{"code":"detail_flow_flat|opening_weak|text_hierarchy_weak|category_info_missing|template_like|detail_visual_weak|detail_visual_repetition|low_information_screen|functional_proof_missing|filler_screen|other", "field":"detail_images[n]", "reason":"具体证据", "impact":"影响", "suggested_fix":"怎么改"}}
  ],
  "confidence": "high|medium|low"
}}"""
    return _call_vlm(
        "detail_page_quality",
        output or {},
        category,
        prompt,
        detail_images[:8],
        max_tokens=2200,
        visual_signals=signals,
        include_individual=True,
    )
