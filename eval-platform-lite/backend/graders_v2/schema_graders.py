"""
Schema & Text Graders v2 — G01 through G10
All code-only, no LLM calls. Each returns standard verdict dict.
"""
import re
from typing import List, Optional


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


# ── G01: output_publishable ───────────────────────────────────────────────────

def output_publishable(output: dict, **_) -> dict:
    """Hard publishability gate: all required fields must be present and non-empty."""
    checks = {
        "title": bool(output.get("title")),
        "attributes": bool(output.get("attributes")) and len(output.get("attributes", {})) > 0,
        "selling_points": bool(output.get("selling_points")) and len(output.get("selling_points", [])) >= 3,
        "body_copy": bool(output.get("body_copy")) and len(output.get("body_copy", "").strip()) > 0,
        "main_images": bool(output.get("main_images")) and len(output.get("main_images", [])) >= 5,
        "detail_image": output.get("detail_image") is not None,
    }
    failures = []
    for field, ok in checks.items():
        if not ok:
            val = output.get(field)
            if isinstance(val, (list, dict)):
                desc = f"count={len(val)}" if val else "empty"
            elif isinstance(val, str):
                desc = f"length={len(val)}"
            else:
                desc = str(type(val).__name__)
            failures.append({
                "field": field,
                "issue_type": "missing_or_insufficient",
                "evidence": {"current": desc},
                "evidence_quote": f"{field} 字段缺失或不足",
                "severity": "blocker",
                "suggested_fix": f"确保 {field} 字段完整（selling_points≥3, main_images≥5, body_copy非空）",
            })
    verdict = "fail" if failures else "pass"
    return _result("output_publishable", verdict, "blocker", failures,
                    f"{len(failures)} 个必填字段不满足发布要求" if failures else "所有必填字段齐全")


# ── G02: output_schema_isolation ──────────────────────────────────────────────

_INTERNAL_META_KEYS = {
    "missing_required", "missing_recommended", "warnings", "sku_suggestion",
    "platform_rules", "title_max_chars", "main_images_count",
}


def output_schema_isolation(output: dict, **_) -> dict:
    """Detect Agent internal metadata leaking into attributes field.
    Uses _raw_top_keys (injected by inject script) to check original attribute structure."""
    attrs = output.get("attributes", {})
    if not attrs:
        return _result("output_schema_isolation", "pass", "blocker",
                        critique="属性字段为空，无 metadata 污染")

    # Check via _raw_top_keys if available (injection script preserves original top-level keys)
    raw_top_keys = attrs.get("_raw_top_keys", [])

    leaked = []
    # Method 1: check preserved raw top keys
    if raw_top_keys:
        for k in raw_top_keys:
            if k in _INTERNAL_META_KEYS:
                leaked.append({
                    "field": f"attributes(raw).{k}",
                    "issue_type": "internal_metadata_leak",
                    "evidence": {"key": k},
                    "evidence_quote": f"原始属性包含内部元数据 key '{k}'",
                    "severity": "blocker",
                    "suggested_fix": "AttributeAgent 输出 schema 必须隔离内部 metadata 和对外属性",
                })
    else:
        # Method 2: fallback - check current attributes keys directly
        for k in attrs.keys():
            if k in _INTERNAL_META_KEYS:
                leaked.append({
                    "field": f"attributes.{k}",
                    "issue_type": "internal_metadata_leak",
                    "evidence": {"key": k, "value_preview": str(attrs[k])[:100]},
                    "evidence_quote": f"属性字段包含内部元数据 key '{k}'",
                    "severity": "blocker",
                    "suggested_fix": "AttributeAgent 输出 schema 必须隔离内部 metadata 和对外属性",
                })
    verdict = "fail" if leaked else "pass"
    return _result("output_schema_isolation", verdict, "blocker", leaked,
                    f"属性字段泄漏 {len(leaked)} 个内部 metadata key" if leaked else "属性 schema 干净")


# ── G03: attribute_key_chinese ────────────────────────────────────────────────

def attribute_key_chinese(output: dict, **_) -> dict:
    """All attribute keys must be Chinese (no ASCII letters)."""
    attrs = output.get("attributes", {})
    if not attrs:
        return _result("attribute_key_chinese", "pass", "blocker",
                        critique="属性为空，跳过 key 语言检查")

    # Keys starting with _ are internal metadata from injection, not real attribute keys
    IGNORE_KEYS = {"_raw_top_keys"}

    failures = []
    for k in attrs.keys():
        if k in IGNORE_KEYS:
            continue
        if re.search(r'[a-zA-Z]', str(k)):
            failures.append({
                "field": f"attributes.{k}",
                "issue_type": "english_key",
                "evidence": {"key": k},
                "evidence_quote": f"属性 key '{k}' 包含英文字母",
                "severity": "blocker",
                "suggested_fix": f"将 key '{k}' 翻译为中文（如 material→材质, brand→品牌）",
            })
    verdict = "fail" if failures else "pass"
    return _result("attribute_key_chinese", verdict, "blocker", failures,
                    f"{len(failures)} 个属性 key 包含英文" if failures else "所有属性 key 均为中文")


# ── G04: attribute_value_quality ──────────────────────────────────────────────

_HEX_PAT = re.compile(r'^#[0-9A-Fa-f]{3,6}$')
_PLACEHOLDER_BLACKLIST = {'待定', '无', 'N/A', 'n/a', '未知', '暂无', '默认', '—', '-', ''}

# 字段级合规白名单：某些字段允许特定占位词作为平台合规填法
# - 品牌="无品牌" 是淘宝平台标准合规填法
# - 认证="其他" / 分类="其他" 也是平台允许的兜底
_FIELD_ALLOWED_PLACEHOLDERS = {
    "品牌": {"无品牌"},
    "brand": {"无品牌", "no brand"},
    "认证": {"其他"},
    "分类": {"其他"},
    "类型": {"其他"},
    "适用人群": {"其他"},
    "适用场景": {"其他"},
}

WEIGHT_RANGES = {
    '装饰': (50, 5000),
    '家纺': (100, 3000),
    '灯具': (100, 5000),
    '厨具': (100, 3000),
    '收纳': (100, 5000),
}


def attribute_value_quality(output: dict, category: str = "", **_) -> dict:
    """Check attribute values for: hex colors, placeholders, SKU pollution, brand issues, weight sanity."""
    attrs = output.get("attributes", {})
    if not attrs:
        return _result("attribute_value_quality", "pass", "warning",
                        critique="属性为空，跳过值质量检查")

    IGNORE_KEYS = {"_raw_top_keys"}
    failures = []

    for k, v in attrs.items():
        if k in IGNORE_KEYS:
            continue
        sv = str(v).strip() if v is not None else ""
        k_lower = k.lower()

        # Sub-rule 1: hex color
        if _HEX_PAT.match(sv):
            failures.append({
                "field": f"attributes.{k}",
                "issue_type": "hex_color",
                "evidence": {"value": sv},
                "evidence_quote": f"属性 '{k}' 值为十六进制色号 {sv}，应转为中文颜色名",
                "severity": "blocker",
                "suggested_fix": "hex → 中文颜色名映射（如 #FFFFFF → 白色）",
            })

        # Sub-rule 2: placeholder（字段级合规白名单豁免）
        field_allowlist = _FIELD_ALLOWED_PLACEHOLDERS.get(k, set())
        if sv in _PLACEHOLDER_BLACKLIST and sv not in field_allowlist:
            failures.append({
                "field": f"attributes.{k}",
                "issue_type": "placeholder_value",
                "evidence": {"value": sv},
                "evidence_quote": f"属性 '{k}' 值为占位词 '{sv}'",
                "severity": "warning",
                "suggested_fix": f"从源页提取真实值，或标记为可选字段不填",
            })

        # Sub-rule 3: SKU pollution in color field
        if k_lower in ('颜色', '颜色分类', 'color'):
            if re.search(r'[\d*⚑]', sv) or len(sv) > 30:
                failures.append({
                    "field": f"attributes.{k}",
                    "issue_type": "sku_pollution",
                    "evidence": {"value": sv[:80]},
                    "evidence_quote": f"颜色字段被 SKU 规格字符串污染",
                    "severity": "blocker",
                    "suggested_fix": "解析 SKU 列表提取颜色名，不要存原始字符串",
                })

        # Sub-rule 4: brand too short
        if k_lower in ('品牌', 'brand') and 0 < len(sv) < 2:
            failures.append({
                "field": f"attributes.{k}",
                "issue_type": "brand_too_short",
                "evidence": {"value": sv},
                "evidence_quote": f"品牌字段只有 '{sv}'（{len(sv)}字），明显是解析残骸",
                "severity": "blocker",
                "suggested_fix": "品牌解析 fallback 应返回完整品牌名或 '无品牌'",
            })

        # Sub-rule 5: weight range check
        if k_lower in ('重量', 'weight'):
            m = re.match(r'^([\d.]+)\s*(g|kg|G|KG)?$', sv)
            if m:
                num = float(m.group(1))
                unit = (m.group(2) or 'g').lower()
                grams = num * 1000 if unit == 'kg' else num
                lo, hi = WEIGHT_RANGES.get(category, (10, 50000))
                if grams < lo or grams > hi:
                    failures.append({
                        "field": f"attributes.{k}",
                        "issue_type": "weight_out_of_range",
                        "evidence": {"value": sv, "grams": grams, "expected_range": f"{lo}-{hi}g"},
                        "evidence_quote": f"重量 {sv} 换算 {grams}g，不在 {category} 品类合理范围 {lo}-{hi}g",
                        "severity": "warning",
                        "suggested_fix": "检查重量单位是否正确，或来源数据是否有误",
                    })

    has_blocker = any(f["severity"] == "blocker" for f in failures)
    verdict = "fail" if failures else "pass"
    severity = "blocker" if has_blocker else "warning"
    return _result("attribute_value_quality", verdict, severity, failures,
                    f"{len(failures)} 个属性值质量问题" if failures else "属性值质量合格")


# ── G05: image_resolution ────────────────────────────────────────────────────

def image_resolution(output: dict, **_) -> dict:
    """All main images must be ≥ 800×800."""
    images = output.get("main_images", [])
    if not images:
        return _result("image_resolution", "fail", "blocker",
                        [{"field": "main_images", "issue_type": "no_images",
                          "evidence_quote": "无主图", "severity": "blocker",
                          "suggested_fix": "确保 Agent 输出至少 5 张主图"}],
                        "无主图")

    failures = []
    for i, img in enumerate(images):
        w = img.get("width", 0) or 0
        h = img.get("height", 0) or 0
        # Fallback: read actual dimensions from file if not provided
        if (w < 800 or h < 800):
            local = img.get("local_path") or img.get("output_path") or ""
            if local:
                try:
                    from PIL import Image as _PIL
                    from pathlib import Path as _P
                    if _P(local).exists():
                        with _PIL.open(local) as im:
                            w, h = im.size
                except Exception:
                    pass
        if w < 800 or h < 800:
            failures.append({
                "field": f"main_images[{i}]",
                "issue_type": "low_resolution",
                "evidence": {"width": w, "height": h},
                "evidence_quote": f"主图{i+1} 尺寸 {w}×{h}，不足 800×800",
                "severity": "blocker",
                "suggested_fix": f"主图{i+1} 需要上采样或重新渲染到 ≥800×800",
            })
    verdict = "fail" if failures else "pass"
    return _result("image_resolution", verdict, "blocker", failures,
                    f"{len(failures)} 张主图分辨率不足" if failures else "所有主图分辨率达标")


# ── G06: title_publishable ───────────────────────────────────────────────────

TITLE_LIMITS = {"taobao": 60, "douyin": 30, "xiaohongshu": 100}
BANNED_WORDS = [
    "最好", "第一", "最大", "最高", "最强", "最优", "顶级",
    "极品", "完美", "无与伦比", "史上最", "绝对",
]


def title_publishable(output: dict, platform: str = "taobao", **_) -> dict:
    """Title length and banned word check."""
    title = output.get("title", "")
    failures = []

    if not title:
        failures.append({
            "field": "title", "issue_type": "empty_title",
            "evidence_quote": "标题为空", "severity": "blocker",
            "suggested_fix": "CopyAgent 必须生成非空标题",
        })
    else:
        limit = TITLE_LIMITS.get(platform, 60)
        if len(title) > limit:
            failures.append({
                "field": "title", "issue_type": "title_too_long",
                "evidence": {"length": len(title), "limit": limit},
                "evidence_quote": f"标题 {len(title)} 字超过 {platform} 限制 {limit} 字",
                "severity": "blocker",
                "suggested_fix": f"标题需要缩减到 {limit} 字以内",
            })

        found_banned = [w for w in BANNED_WORDS if w in title]
        if found_banned:
            failures.append({
                "field": "title", "issue_type": "banned_words",
                "evidence": {"words": found_banned},
                "evidence_quote": f"标题包含违禁词: {', '.join(found_banned)}",
                "severity": "blocker",
                "suggested_fix": f"删除违禁词: {', '.join(found_banned)}",
            })

    verdict = "fail" if failures else "pass"
    return _result("title_publishable", verdict, "blocker", failures,
                    "; ".join(f["evidence_quote"] for f in failures) if failures else "标题合规")


# ── G07: title_no_template ───────────────────────────────────────────────────

B2B_KEYWORDS = [
    '批发', '工厂直销', '源头厂家', '订做', '一件代发', '现货供应',
    '厂家直销', '生产厂', '门口摆放', '加工定制', '来图定制',
    '起订', '混批', '代发', '外贸', '库存',
]


def title_no_template(output: dict, **_) -> dict:
    """Detect if title is a raw B2B source title without B2C transformation.
    Note: full detection (similarity with source title) requires F-DATA-1 fix.
    This is the fallback version using B2B keyword detection."""
    title = output.get("title", "")
    if not title:
        return _result("title_no_template", "pass", "blocker",
                        critique="标题为空，跳过模板检测（G01 已覆盖）")

    failures = []
    found = [kw for kw in B2B_KEYWORDS if kw in title]
    if found:
        failures.append({
            "field": "title", "issue_type": "b2b_title_reuse",
            "evidence": {"b2b_keywords": found},
            "evidence_quote": f"标题含 B2B 关键词 '{', '.join(found)}'，疑似复用源页标题",
            "severity": "blocker",
            "suggested_fix": "CopyAgent 必须将 B2B 标题转化为面向消费者的 B2C 标题",
        })

    verdict = "fail" if failures else "pass"
    return _result("title_no_template", verdict, "blocker", failures,
                    f"标题含 B2B 关键词" if failures else "标题已 B2C 转化")


# ── G08: title_no_pollution ──────────────────────────────────────────────────

ALLOWED_ABBRS = {
    'ins', 'INS', 'LED', 'led', 'USB', 'usb', 'PP', 'pp', 'PVC', 'pvc',
    'ABS', 'abs', 'IP', 'ip', 'VR', 'vr', 'AI', 'ai', 'DIY', 'diy',
}

TAIL_LOCATION_PATTERNS = [
    r'(浙江|广东|福建|江苏|山东|河北|河南|湖南|湖北|四川|安徽)(义乌|深圳|广州|苏州|青岛|东莞|佛山|温州|杭州|景德镇)',
]
TAIL_COLOR_ENUM_PATTERN = r'[\u4e00-\u9fa5]+色\s*[,，]\s*[\u4e00-\u9fa5]+色'


def title_no_pollution(output: dict, **_) -> dict:
    """Detect attribute field splicing into title tail, or foreign brand names."""
    title = output.get("title", "")
    if not title:
        return _result("title_no_pollution", "pass", "warning",
                        critique="标题为空，跳过污染检测")

    failures = []

    # Sub-rule 1: tail pollution (location + color enum)
    tail_30 = title[-30:]
    for pat in TAIL_LOCATION_PATTERNS:
        m = re.search(pat, tail_30)
        if m:
            failures.append({
                "field": "title", "issue_type": "attribute_tail_pollution",
                "evidence": {"matched": m.group(), "position": "tail"},
                "evidence_quote": f"标题末尾出现产地 '{m.group()}'，疑似拼接了 attributes 字段",
                "severity": "warning",
                "suggested_fix": "标题生成不应机械拼接 attributes.产地",
            })
    if re.search(TAIL_COLOR_ENUM_PATTERN, tail_30):
        failures.append({
            "field": "title", "issue_type": "color_enum_in_tail",
            "evidence": {"tail": tail_30},
            "evidence_quote": "标题末尾出现颜色枚举（如'粉色,白色'），疑似拼接了颜色属性",
            "severity": "warning",
            "suggested_fix": "标题不应包含 SKU 颜色列表",
        })

    # Sub-rule 2: foreign brand (consecutive ≥4 ASCII letters, excluding allowed abbreviations)
    ascii_runs = re.findall(r'[a-zA-Z]{4,}', title)
    foreign = [s for s in ascii_runs if s not in ALLOWED_ABBRS]
    if foreign:
        failures.append({
            "field": "title", "issue_type": "foreign_brand_in_title",
            "evidence": {"tokens": foreign},
            "evidence_quote": f"中文标题含英文 '{', '.join(foreign)}'，不利于搜索匹配",
            "severity": "warning",
            "suggested_fix": "英文品牌名需中文化或删除",
        })

    verdict = "fail" if failures else "pass"
    return _result("title_no_pollution", verdict, "warning", failures,
                    f"标题有 {len(failures)} 处污染" if failures else "标题无污染")


# ── G09: title_category_keyword ──────────────────────────────────────────────

CATEGORY_SYNONYMS = {
    '装饰': ['装饰', '摆件', '花瓶', '挂画', '雕塑', '工艺品', '摆设'],
    '家纺': ['家纺', '桌布', '被', '枕', '床单', '毛毯', '盖布', '台布', '抱枕', '床品'],
    '灯具': ['灯', '灯具', '台灯', '夜灯', '氛围灯', '小夜灯', '吊灯', '壁灯', '射灯', '灯饰'],
    '厨具': ['锅', '碗', '杯', '盘', '勺', '刀', '厨', '炊', '马克杯', '陶瓷杯', '餐具'],
    '收纳': ['收纳', '储物', '整理', '盒', '篮', '架', '箱'],
    '清洁': ['清洁', '拖把', '扫', '刷', '擦'],
    '香薰': ['香薰', '蜡烛', '香氛', '熏香'],
}


def title_category_keyword(output: dict, category: str = "", **_) -> dict:
    """Title first 25 chars should contain a category keyword for search recall."""
    title = output.get("title", "")
    if not title:
        return _result("title_category_keyword", "pass", "warning",
                        critique="标题为空，跳过品类词检测")
    if not category:
        return _result("title_category_keyword", "pass", "warning",
                        critique="品类未指定，跳过品类词检测", confidence="low")

    lead = title[:25]
    synonyms = CATEGORY_SYNONYMS.get(category, [category] if category else [])
    hit = next((kw for kw in synonyms if kw in lead), None)

    if hit:
        return _result("title_category_keyword", "pass", "warning",
                        critique=f"标题前25字含品类词「{hit}」")
    else:
        return _result("title_category_keyword", "fail", "warning",
                        [{
                            "field": "title",
                            "issue_type": "missing_category_keyword",
                            "evidence": {"first_25": lead, "expected_keywords": synonyms[:5]},
                            "evidence_quote": f"标题前25字「{lead}」未含品类词（{'/'.join(synonyms[:3])}...）",
                            "severity": "warning",
                            "suggested_fix": f"在标题前 20 字内嵌入品类词（{'/'.join(synonyms[:3])}）",
                        }],
                        f"标题前25字缺品类词")


# ── G10: copy_no_template ────────────────────────────────────────────────────

BODY_TEMPLATE_PATTERNS = [
    r'这款.*真的太好用了',
    r'颜值高又实用',
    r'闭眼入不踩雷',
    r'放在家里瞬间提升幸福感',
    r'性价比超高.*闭眼',
]

SELLING_POINT_BLACKLIST = {
    '高颜值设计', '实用百搭', '性价比超高', '一物多用', '品质保证',
    '匠心制作', '人气爆款', '送礼首选', '居家必备',
}


def copy_no_template(output: dict, **_) -> dict:
    """Detect if body copy or selling points use template boilerplate."""
    body = output.get("body_copy", "")
    selling_points = output.get("selling_points", [])

    failures = []

    # Sub-rule 1: body template
    for pat in BODY_TEMPLATE_PATTERNS:
        if re.search(pat, body):
            failures.append({
                "field": "body_copy",
                "issue_type": "template_body",
                "evidence": {"pattern": pat, "match": re.search(pat, body).group()[:50]},
                "evidence_quote": f"正文含模板短语「{re.search(pat, body).group()[:30]}」",
                "severity": "blocker",
                "suggested_fix": "CopyAgent 必须真实生成正文，不能用模板兜底",
            })
            break  # one template match is enough

    # Sub-rule 2: selling point blacklist
    template_sp_indices = []
    for i, sp in enumerate(selling_points):
        sp_str = sp if isinstance(sp, str) else ""
        # Handle "headline：desc" format
        if "：" in sp_str:
            sp_str = sp_str.split("：")[0].strip()
        if sp_str in SELLING_POINT_BLACKLIST:
            template_sp_indices.append(i)

    if template_sp_indices:
        failures.append({
            "field": "selling_points",
            "issue_type": "template_selling_points",
            "evidence": {"template_indices": template_sp_indices,
                         "template_texts": [selling_points[i] for i in template_sp_indices]},
            "evidence_quote": f"卖点含模板占位词: {[selling_points[i] for i in template_sp_indices[:3]]}",
            "severity": "blocker",
            "suggested_fix": "StrategyAgent 必须生成产品相关的卖点，不能用通用短语",
        })

    verdict = "fail" if failures else "pass"
    return _result("copy_no_template", verdict, "blocker", failures,
                    f"{len(failures)} 处模板检测命中" if failures else "文案非模板化")
