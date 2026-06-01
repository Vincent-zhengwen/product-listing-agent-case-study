"""
Image Graders v2 — G14 through G22
Code-based image analysis. Each returns standard verdict dict.
G19/G20/G21 require OCR (paddleocr). G16 requires imagehash. G17 requires scipy.
"""
import re
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter
from project_paths import resolve_agent_image_path_from_url


# ── Standard output format ────────────────────────────────────────────────────

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


# ── Image loading helpers ────────────────────────────────────────────────────

def _get_local_path(img_dict: dict) -> Optional[str]:
    """Extract local file path from image dict."""
    path = img_dict.get("local_path") or img_dict.get("output_path") or ""
    if path and Path(path).exists():
        return path
    # Try deriving from URL
    url = img_dict.get("url", "")
    candidate = resolve_agent_image_path_from_url(url)
    if candidate:
        return str(candidate)
    return None


def _load_image(path: str) -> Optional[np.ndarray]:
    """Load image as RGB numpy array."""
    try:
        return np.array(Image.open(path).convert("RGB"))
    except Exception:
        return None


# ── G14: image_blank_detection (verified 8/8) ────────────────────────────────

def image_blank_detection(output: dict, **_) -> dict:
    """Detect text-only blank main images (no product subject).
    Rule: edge_density < 0.08 AND unique_colors < 1500 AND foreground < 5% → blank."""
    images = output.get("main_images", [])
    if not images:
        return _result("image_blank_detection", "pass", "blocker",
                        critique="无主图，跳过空白检测（G01 已覆盖）")

    failures = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        try:
            pil_img = Image.open(path).convert("RGB")
            # Edge density
            edges = pil_img.convert("L").filter(ImageFilter.FIND_EDGES)
            edge_ratio = float((np.array(edges) > 30).mean())
            # Unique colors (downsampled)
            small = pil_img.resize((100, 100))
            unique_colors = len(np.unique(np.array(small).reshape(-1, 3), axis=0))
            # Sparse foreground: keeps white-background white products from being
            # mistaken for blank cards when their subject is visible.
            gray = np.array(pil_img.convert("L"))
            foreground_ratio = float((gray < 240).mean())

            if edge_ratio < 0.08 and unique_colors < 1500 and foreground_ratio < 0.05:
                failures.append({
                    "field": f"main_images[{i}]",
                    "issue_type": "blank_image",
                    "evidence": {"edge_density": round(edge_ratio, 3),
                                 "unique_colors": unique_colors,
                                 "foreground_ratio": round(foreground_ratio, 3)},
                    "evidence_quote": f"主图{i+1} 边缘密度={edge_ratio:.3f}, 颜色数={unique_colors}, 前景占比={foreground_ratio:.1%}，判定为空白图",
                    "severity": "blocker",
                    "suggested_fix": f"重新生成主图{i+1}，确保产品主体可见",
                })
        except Exception as e:
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "image_read_error",
                "evidence": {"error": str(e)[:80]},
                "evidence_quote": f"主图{i+1} 读取失败: {str(e)[:60]}",
                "severity": "warning",
                "suggested_fix": "检查图片文件完整性",
            })

    verdict = "fail" if any(f["issue_type"] == "blank_image" for f in failures) else "pass"
    return _result("image_blank_detection", verdict, "blocker", failures,
                    f"{sum(1 for f in failures if f['issue_type']=='blank_image')} 张空白主图" if verdict == "fail" else "无空白主图")


# ── G15: image_dark_detection (verified 6/6) ─────────────────────────────────

def image_dark_detection(output: dict, **_) -> dict:
    """Detect severely underexposed main images.
    Rule: brightness_mean < 80 AND brightness_std < 50 → dark."""
    images = output.get("main_images", [])
    if not images:
        return _result("image_dark_detection", "pass", "warning",
                        critique="无主图")

    failures = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        try:
            gray = np.array(Image.open(path).convert("L"))
            mean_val = float(gray.mean())
            std_val = float(gray.std())
            if mean_val < 80 and std_val < 50:
                failures.append({
                    "field": f"main_images[{i}]",
                    "issue_type": "severely_dark",
                    "evidence": {"brightness_mean": round(mean_val, 1),
                                 "brightness_std": round(std_val, 1)},
                    "evidence_quote": f"主图{i+1} 亮度={mean_val:.0f}, σ={std_val:.0f}，曝光严重不足",
                    "severity": "warning",
                    "suggested_fix": f"主图{i+1} 需要重新渲染或调整亮度",
                })
        except Exception:
            pass

    verdict = "fail" if failures else "pass"
    return _result("image_dark_detection", verdict, "warning", failures,
                    f"{len(failures)} 张极暗主图" if failures else "所有主图亮度正常")


# ── G16: image_duplicate_main ────────────────────────────────────────────────

def image_duplicate_main(output: dict, **_) -> dict:
    """Detect duplicate main images (violates multi-angle requirement).
    Uses perceptual hash; hamming distance < 5 = duplicate."""
    images = output.get("main_images", [])
    if len(images) < 2:
        return _result("image_duplicate_main", "pass", "blocker",
                        critique="主图少于 2 张，无法做重复检测")

    try:
        import imagehash
    except ImportError:
        return _result("image_duplicate_main", "skipped", "blocker",
                        critique="imagehash 未安装", confidence="low")

    hashes = []
    valid_indices = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        try:
            h = imagehash.phash(Image.open(path))
            hashes.append(h)
            valid_indices.append(i)
        except Exception:
            pass

    failures = []
    seen_pairs = set()
    for a in range(len(hashes)):
        for b in range(a + 1, len(hashes)):
            dist = hashes[a] - hashes[b]
            if dist < 5:
                pair = (valid_indices[a], valid_indices[b])
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    failures.append({
                        "field": f"main_images[{pair[0]}] vs [{pair[1]}]",
                        "issue_type": "duplicate_images",
                        "evidence": {"hamming_distance": dist,
                                     "indices": list(pair)},
                        "evidence_quote": f"主图{pair[0]+1} 和主图{pair[1]+1} 几乎相同 (hamming={dist})",
                        "severity": "blocker",
                        "suggested_fix": "确保 5 张主图展示不同角度/场景",
                    })

    verdict = "fail" if failures else "pass"
    return _result("image_duplicate_main", verdict, "blocker", failures,
                    f"{len(failures)} 对重复主图" if failures else "5 张主图互不重复")


# ── G17: image_fragmented_subject ────────────────────────────────────────────

def image_fragmented_subject(output: dict, **_) -> dict:
    """Detect SAM segmentation failures causing fragmented/clipped product subjects.
    SAM failure pattern: low non-white ratio (5-30%) + high component count (>50).
    This distinguishes from G14 blank (which catches <5% non-white) and normal
    product-on-white-bg images (which have a dominant connected subject)."""
    images = output.get("main_images", [])
    if not images:
        return _result("image_fragmented_subject", "pass", "blocker",
                        critique="无主图")

    try:
        from scipy.ndimage import label
    except ImportError:
        return _result("image_fragmented_subject", "skipped", "blocker",
                        critique="scipy 未安装", confidence="low")

    failures = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        try:
            gray = np.array(Image.open(path).convert("L"))
            H, W = gray.shape
            total_pixels = H * W
            mask = (gray < 240).astype(np.uint8)
            nonwhite_ratio = mask.sum() / total_pixels

            # Skip if very high non-white (normal product image) or very low (blank → G14)
            if nonwhite_ratio > 0.40 or nonwhite_ratio < 0.03:
                continue

            # In the "SAM fragment zone" (3-40% non-white): check component count
            labeled, n_components = label(mask)
            component_sizes = np.bincount(labeled.ravel())[1:]
            largest_component_ratio = (
                float(component_sizes.max() / total_pixels)
                if len(component_sizes)
                else 0.0
            )

            # SAM fragment: moderate non-white + lots of tiny scattered components
            # without a dominant subject. Text, hollow patterns, and marble veins can
            # create many components, so component count alone is too noisy.
            if n_components > 50 and largest_component_ratio < 0.10:
                failures.append({
                    "field": f"main_images[{i}]",
                    "issue_type": "fragmented_subject",
                    "evidence": {"nonwhite_ratio": round(nonwhite_ratio, 3),
                                 "n_components": n_components,
                                 "largest_component_ratio": round(largest_component_ratio, 3)},
                    "evidence_quote": f"主图{i+1} 非白区域 {nonwhite_ratio:.0%} + {n_components} 个碎片，最大主体 {largest_component_ratio:.0%}，疑似 SAM 分割失败",
                    "severity": "blocker",
                    "suggested_fix": f"主图{i+1} SAM 分割失败，需要重新分割或使用完整源图",
                })

        except Exception:
            pass

    verdict = "fail" if failures else "pass"
    return _result("image_fragmented_subject", verdict, "blocker", failures,
                    f"{len(failures)} 张主图疑似 SAM 分割失败" if failures else "主图主体完整")


# ── G19/G20/G21: OCR-based graders ──────────────────────────────────────────

_ocr_engine = None


def _get_ocr():
    """Lazy-load PaddleOCR or fallback to pytesseract."""
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine

    try:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch')
        return _ocr_engine
    except ImportError:
        pass

    # Mark as unavailable
    _ocr_engine = False
    return False


# Module-level OCR result cache (path → text). Persists across graders within one process.
_OCR_TEXT_CACHE: dict = {}


_OCR_MAX_DIM = 1200  # Downscale images larger than this before OCR (speed + hang prevention)


def _prepare_ocr_input(path: str) -> str:
    """Resize oversized images to avoid PaddleOCR slow/hang issues.

    Some large images (observed: 1500×1500 with complex layouts) cause PaddleOCR
    to hang indefinitely. Downscaling to ≤1200 px is safe for text detection and
    dramatically reduces OCR runtime.

    Returns path to use for OCR (either original or a temp resized copy).
    """
    try:
        with Image.open(path) as im:
            w, h = im.size
            if max(w, h) <= _OCR_MAX_DIM:
                return path
            # Resize keeping aspect ratio
            scale = _OCR_MAX_DIM / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            # Save to sibling path with _ocr suffix (cached across calls)
            p = Path(path)
            resized = p.with_name(p.stem + f"_ocr{_OCR_MAX_DIM}" + p.suffix)
            if resized.exists() and resized.stat().st_size > 500:
                return str(resized)
            im_rgb = im.convert("RGB") if im.mode != "RGB" else im
            im_rgb.resize(new_size, Image.LANCZOS).save(str(resized), quality=90)
            return str(resized)
    except Exception:
        return path


def _ocr_text(path: str) -> str:
    """Run OCR on an image, return all detected text. Cached by path."""
    if path in _OCR_TEXT_CACHE:
        return _OCR_TEXT_CACHE[path]
    ocr = _get_ocr()
    if ocr is False:
        return ""
    # Preprocess: downscale large images to avoid PaddleOCR hang
    ocr_path = _prepare_ocr_input(path)
    try:
        result = ocr.ocr(ocr_path)
        if not result:
            _OCR_TEXT_CACHE[path] = ""
            return ""
        # PaddleOCR v3 returns list of dicts with 'rec_texts' key
        # PaddleOCR v2 returns list of [box, (text, score)] tuples
        texts = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    # v3 format: {'rec_texts': [...], ...}
                    texts.extend(item.get('rec_texts', []))
                elif isinstance(item, list):
                    # v2 format: list of [box, (text, score)]
                    for line in item:
                        if line and len(line) > 1 and isinstance(line[1], (tuple, list)):
                            texts.append(line[1][0])
        out = " ".join(texts)
        _OCR_TEXT_CACHE[path] = out
        return out
    except Exception:
        _OCR_TEXT_CACHE[path] = ""
        return ""


# Supplier residual blacklist — hard-fail keywords.
# Substring keys match anywhere (URLs, domains, multi-word phrases).
# Word keys match only as whole words (avoid OCR noise like "eoem" hitting "oem").
_BLACKLIST_SUBSTRING = [
    "www.", "http", ".com", ".cn",
    "made in china", "factory direct",
    "click to order", "buy now", "add to cart",
]
_BLACKLIST_WORDS = [
    "wechat", "whatsapp", "wholesale", "alibaba", "1688", "yiwugo", "yiwu",
    "moq", "fob", "oem", "odm", "supplier",
]
# Pre-compile word-boundary regex
_BLACKLIST_WORD_RE = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _BLACKLIST_WORDS) + r')\b',
    re.IGNORECASE
)

_ALLOWED_ACRONYMS = {'ins', 'INS', 'LED', 'led', 'USB', 'usb',
                     'PP', 'PVC', 'ABS', 'DIY', 'PU', 'EVA'}


def _classify_english_with_vlm(path: str, ocr_text: str,
                                 merchant_brand: str = "") -> Optional[dict]:
    """Ask qwen-vl-max whether English in the image is supplier residual or decorative.

    If merchant_brand is provided, VLM is told to treat that brand as merchant-owned
    (not residual) — distinguishes "店铺自有品牌水印" from "陌生供应商水印".
    """
    try:
        from graders_v2.vlm_graders import _get_vlm_client, _image_to_base64_url, _extract_json
    except Exception:
        return None
    client = _get_vlm_client()
    if not client:
        return None

    brand_note = ""
    if merchant_brand:
        brand_note = f"""

**重要上下文**：这张图来自店铺「{merchant_brand}」的商品 listing。
- 如果图中英文是这家店铺自身的品牌名/logo（包括拼音变体，如 "{merchant_brand}" → "ZHIFOUJIAJU" 之类），那是**商家自有品牌水印**，属于 merchant_brand 类别（合法）。
- 只有当英文是**陌生上游供应商**的品牌/水印（不是这家店）时，才算 supplier_residual。
"""

    prompt = f"""这是一张电商商品图。OCR 从图中识别出了英文文本：

"{ocr_text[:300]}"
{brand_note}
请判断这段英文属于以下哪一类：

A. **supplier_residual** — 上游供应商/模板残留，需要清理：
   - 陌生供应商水印、URL、联系方式（如 www.xxx.com, WeChat, 电话）
   - 上游 B2B 平台 logo / 烙印（1688, Alibaba, wholesale）
   - 上游厂家信息（Made in China, 陌生厂名）

B. **merchant_brand** — 商家自有品牌标识（合法）：
   - 当前店铺自己的品牌名/logo/拼音
   - 当前店铺自己的店招

C. **decorative** — 场景装饰元素（合法）：
   - 产品本身印的英文品牌型号
   - 场景道具上的英文（信件、书本、招牌、海报、徽章等）
   - 产品包装上的正式英文品牌
   - 装饰艺术字、Lorem Ipsum 风的纸片道具

判断依据：
- 英文是当前店铺品牌 → merchant_brand
- 英文是陌生第三方水印/链接/联系方式 → supplier_residual
- 英文嵌入场景道具 → decorative

只输出 JSON：
{{"verdict": "supplier_residual" | "merchant_brand" | "decorative", "reason": "一句话说明"}}"""

    try:
        img_url = _image_to_base64_url(path)
        model = os.getenv("GRADER_VLM_MODEL", "qwen-vl-max")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": prompt},
            ]}],
            temperature=0.1,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        return _extract_json(raw)
    except Exception:
        return None


def image_foreign_text_residual(output: dict, **_) -> dict:
    """G19: Detect supplier foreign text in main images.

    Three-stage pipeline:
    1. OCR extracts text
    2. Blacklist keywords → hard fail (supplier URLs/contact/platform words)
    3. Ambiguous English → VLM classifies as merchant_brand / decorative / residual

    Reads `output.merchant_brand` to whitelist the store's own brand name.
    """
    ocr = _get_ocr()
    if ocr is False:
        return _result("image_foreign_text_residual", "skipped", "blocker",
                        critique="OCR 引擎未安装（需要 paddleocr）", confidence="low")

    images = output.get("main_images", [])
    if not images:
        return _result("image_foreign_text_residual", "pass", "blocker", critique="无主图")

    merchant_brand = (output.get("merchant_brand") or "").strip()

    failures = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        text = _ocr_text(path)
        if not text:
            continue

        # Stage 1: blacklist check — definite supplier residual
        text_lower = text.lower()
        blacklist_hits = [kw for kw in _BLACKLIST_SUBSTRING if kw in text_lower]
        blacklist_hits += [m.group(1) for m in _BLACKLIST_WORD_RE.finditer(text)]
        if blacklist_hits:
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "foreign_text_residual",
                "evidence": {"ocr_text": text[:200], "blacklist_hits": blacklist_hits,
                             "stage": "blacklist"},
                "evidence_quote": f"主图{i+1} 含供应商关键词: {', '.join(blacklist_hits[:3])}",
                "severity": "blocker",
                "suggested_fix": f"主图{i+1} 需要清除供应商水印/联系方式",
            })
            continue

        # Stage 2: any meaningful English at all?
        ascii_runs = re.findall(r'[a-zA-Z]{4,}', text)
        foreign = [s for s in ascii_runs if s not in _ALLOWED_ACRONYMS]
        if not foreign:
            continue  # no English → pass

        # Stage 3: VLM classification (merchant_brand / decorative / residual)
        vlm_result = _classify_english_with_vlm(path, text, merchant_brand=merchant_brand)
        if vlm_result is None:
            # VLM unavailable — conservative fallback: treat as residual
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "foreign_text_residual",
                "evidence": {"ocr_text": text[:200], "foreign_tokens": foreign,
                             "stage": "vlm_unavailable"},
                "evidence_quote": f"主图{i+1} 含未分类英文 (VLM 不可用): {', '.join(foreign[:3])}",
                "severity": "blocker",
                "suggested_fix": "人工核查；或配置 DASHSCOPE_API_KEY 启用 VLM 分类",
            })
            continue

        verdict_cls = vlm_result.get("verdict", "")
        reason = vlm_result.get("reason", "")
        if verdict_cls == "supplier_residual":
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "foreign_text_residual",
                "evidence": {"ocr_text": text[:200], "foreign_tokens": foreign,
                             "stage": "vlm", "vlm_reason": reason},
                "evidence_quote": f"主图{i+1} VLM 判定为供应商残留: {reason[:80]}",
                "severity": "blocker",
                "suggested_fix": f"主图{i+1} 需要清除供应商英文文字",
            })
        # else decorative → pass, no failure recorded

    verdict = "fail" if failures else "pass"
    return _result("image_foreign_text_residual", verdict, "blocker", failures,
                    f"{len(failures)} 张主图含供应商英文" if failures else "主图无供应商英文")


# ── Platform UI pattern keywords (Chinese)
PLATFORM_UI_KEYWORDS = ['热卖', '包邮', '促销', '限时', '新品', '特价', '爆款',
                         '1688', 'yiwugo', '义乌购', '义乌', '淘工厂', '源头']
PRICE_PATTERN = re.compile(r'[¥￥]\s*\d+')


def image_platform_ui_overlay(output: dict, **_) -> dict:
    """G20: Detect source platform UI elements (badges, price labels) in images."""
    ocr = _get_ocr()
    if ocr is False:
        return _result("image_platform_ui_overlay", "skipped", "blocker",
                        critique="OCR 引擎未安装", confidence="low")

    images = output.get("main_images", [])
    if not images:
        return _result("image_platform_ui_overlay", "pass", "blocker", critique="无主图")

    failures = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        text = _ocr_text(path)
        if not text:
            continue

        found = [kw for kw in PLATFORM_UI_KEYWORDS if kw in text]
        if PRICE_PATTERN.search(text):
            found.append("price_label")

        if found:
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "platform_ui_overlay",
                "evidence": {"ocr_text": text[:200], "ui_keywords": found},
                "evidence_quote": f"主图{i+1} 含平台 UI 元素: {', '.join(found[:4])}",
                "severity": "blocker",
                "suggested_fix": f"主图{i+1} 需要清除货源平台水印/标签",
            })

    verdict = "fail" if failures else "pass"
    return _result("image_platform_ui_overlay", verdict, "blocker", failures,
                    f"{len(failures)} 张主图含平台 UI" if failures else "主图无平台 UI 烙印")


# ── Internal text leak patterns
INTERNAL_LEAK_PATTERNS = [
    r'纯白底.*正脸',
    r'算法友好',
    r'SEO',
    r'一波带走.*确认',
    r'合规',
    r'prompt',
    r'instruction',
    r'指令',
    r'规划',
]
QUESTION_PATTERN = re.compile(r'^好奇.*[?？]$')


def image_internal_text_leak(output: dict, **_) -> dict:
    """G21: Detect Agent internal prompt/instruction text leaking into images."""
    ocr = _get_ocr()
    if ocr is False:
        return _result("image_internal_text_leak", "skipped", "blocker",
                        critique="OCR 引擎未安装", confidence="low")

    images = output.get("main_images", [])
    if not images:
        return _result("image_internal_text_leak", "pass", "blocker", critique="无主图")

    failures = []
    for i, img in enumerate(images):
        path = _get_local_path(img)
        if not path:
            continue
        text = _ocr_text(path)
        if not text:
            continue

        matches = []
        for pat in INTERNAL_LEAK_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                matches.append(pat)

        # Question sentence in image text
        lines = text.split()
        for line in lines:
            if QUESTION_PATTERN.match(line.strip()):
                matches.append("question_sentence")

        if matches:
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "internal_text_leak",
                "evidence": {"ocr_text": text[:200], "matched_patterns": matches},
                "evidence_quote": f"主图{i+1} 含 Agent 内部指令文字: {matches[:3]}",
                "severity": "blocker",
                "suggested_fix": "ImagePlannerAgent 必须区分 display_text 和 internal_notes",
            })

    verdict = "fail" if failures else "pass"
    return _result("image_internal_text_leak", verdict, "blocker", failures,
                    f"{len(failures)} 张主图含 Agent 指令文字" if failures else "主图无指令文字泄漏")


# ── G23: image_source_reuse ──────────────────────────────────────────────────

import hashlib
import urllib.request

_SOURCE_IMG_CACHE_DIR = Path("/tmp/eval_source_images")


def _download_source_image(url: str) -> Optional[str]:
    """Download a source image to local cache, return local path. None on failure."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    _SOURCE_IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(url.encode()).hexdigest()
    suffix = ".jpg"
    if "." in url.rsplit("/", 1)[-1]:
        ext = url.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext in ("jpg", "jpeg", "png", "webp"):
            suffix = "." + ext
    local = _SOURCE_IMG_CACHE_DIR / f"{h}{suffix}"
    if local.exists() and local.stat().st_size > 0:
        return str(local)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        if len(data) < 100:
            return None
        local.write_bytes(data)
        return str(local)
    except Exception:
        return None


def image_source_reuse(output: dict, source_data: dict = None,
                       source_images: list = None, **_) -> dict:
    """G23: Detect main images that are essentially source images with text overlay.
    Uses pHash similarity (hamming distance < 10 = likely reuse)."""
    policy = os.getenv("SOURCE_REUSE_POLICY", "allowed").strip().lower()
    src_imgs = source_images or (source_data or {}).get("images") or []
    if not src_imgs:
        return _result("image_source_reuse", "skipped", "blocker",
                       critique="源页 images 为空（源页失效或未爬取）",
                       confidence="low")

    agent_imgs = output.get("main_images", [])
    if not agent_imgs:
        return _result("image_source_reuse", "skipped", "blocker",
                       critique="Agent 无主图")

    try:
        import imagehash
    except ImportError:
        return _result("image_source_reuse", "skipped", "blocker",
                       critique="imagehash 未安装", confidence="low")

    # Hash all source images (cache downloads)
    src_hashes = []  # list of (url, hash)
    for item in src_imgs[:20]:  # cap at 20 to limit downloads
        url = item.get("url", "") if isinstance(item, dict) else str(item)
        local = _download_source_image(url)
        if not local:
            continue
        try:
            h = imagehash.phash(Image.open(local))
            src_hashes.append((url, h))
        except Exception:
            continue

    if not src_hashes:
        return _result("image_source_reuse", "skipped", "blocker",
                       critique=f"源图全部下载失败（尝试 {len(src_imgs)} 张）",
                       confidence="low")

    # Hash agent main images and compare
    failures = []
    for i, img in enumerate(agent_imgs):
        path = _get_local_path(img)
        if not path:
            continue
        try:
            agent_hash = imagehash.phash(Image.open(path))
        except Exception:
            continue

        # Find closest source image
        best_dist = 100
        best_url = ""
        for src_url, src_h in src_hashes:
            dist = agent_hash - src_h
            if dist < best_dist:
                best_dist = dist
                best_url = src_url

        if best_dist < 10:
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "source_image_reuse",
                "evidence": {
                    "hamming_distance": best_dist,
                    "matched_source_url": best_url[:120],
                },
                "evidence_quote": f"主图{i+1} 与源图相似 (pHash 距离={best_dist})，疑似源图直接复用+文字叠加",
                "severity": "blocker",
                "suggested_fix": "万相生图失败时不要直接复用源图，应重新生成或用 SAM 抠产品图+白底",
            })

    if failures and policy in {"block", "blocking"}:
        verdict = "fail"
        critique = f"{len(failures)} 张主图疑似源图复用 (策略=block, 源图库={len(src_hashes)}张)"
        return _result("image_source_reuse", verdict, "blocker", failures, critique, confidence="medium")
    if failures and policy in {"warn", "warning"}:
        verdict = "fail"
        critique = f"{len(failures)} 张主图疑似源图复用 (策略=warn, 源图库={len(src_hashes)}张)"
        return _result("image_source_reuse", verdict, "warning", failures, critique, confidence="medium")

    critique = (
        f"{len(failures)} 张主图与源图相似，但当前策略允许复用源图，不作为质量失败"
        if failures else f"无源图复用信号 (源图库={len(src_hashes)}张)"
    )
    return _result("image_source_reuse", "pass", "info", [], critique, confidence="medium")


# ── G22: cross_case_pollution ────────────────────────────────────────────────

# Cross-case pollution: only flag keywords that are STRONGLY exclusive to other categories.
# Use longer, more specific phrases to reduce false positives.
# E.g., "床头灯" in a lamp listing is fine, but "选灯不踩雷" in a vase listing is pollution.
CATEGORY_EXCLUSIVE_KEYWORDS = {
    '装饰': ['选灯不踩雷', '收纳盒', '马克杯', '被子', '床单'],
    '灯具': ['花瓶摆件', '收纳盒', '马克杯', '桌布', '被子'],
    '家纺': ['花瓶摆件', '选灯不踩雷', '马克杯', '收纳盒'],
    '厨具': ['花瓶摆件', '选灯不踩雷', '桌布', '被子', '收纳盒'],
    '收纳': ['花瓶摆件', '选灯不踩雷', '马克杯', '桌布', '被子'],
    '香薰': ['花瓶摆件', '选灯不踩雷', '马克杯', '桌布', '被子', '收纳盒'],
}


def cross_case_pollution(output: dict, category: str = "", **_) -> dict:
    """G22: Detect keywords from other product categories in this listing's text/image OCR."""
    if not category:
        return _result("cross_case_pollution", "pass", "warning",
                        critique="品类未指定，跳过交叉污染检测", confidence="low")

    exclusives = CATEGORY_EXCLUSIVE_KEYWORDS.get(category, [])
    if not exclusives:
        return _result("cross_case_pollution", "pass", "warning",
                        critique=f"品类 '{category}' 无互斥关键词表")

    # Collect all text
    all_text = output.get("title", "")
    all_text += " " + output.get("body_copy", "")
    for sp in output.get("selling_points", []):
        all_text += " " + (sp if isinstance(sp, str) else "")

    # Also check image OCR if available
    images = output.get("main_images", [])
    ocr = _get_ocr()
    if ocr is not False:
        for img in images[:3]:  # Only OCR first 3 to save time
            path = _get_local_path(img)
            if path:
                all_text += " " + _ocr_text(path)

    found = [kw for kw in exclusives if kw in all_text]

    if found:
        failures = [{
            "field": "cross_field",
            "issue_type": "cross_case_pollution",
            "evidence": {"category": category, "foreign_keywords": found},
            "evidence_quote": f"{category} 类 listing 出现了其他品类关键词: {', '.join(found)}",
            "severity": "blocker",
            "suggested_fix": "检查 Agent 是否有状态泄漏（模块级缓存/全局变量）",
        }]
        return _result("cross_case_pollution", "fail", "blocker", failures,
                        f"检测到跨 case 关键词污染: {found}")
    return _result("cross_case_pollution", "pass", "blocker",
                    critique="无跨品类关键词污染")
