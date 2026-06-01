"""
Deterministic Code Graders — fast, no external calls.
Each grader returns: {"verdict": "pass"|"fail"|None, "score": float|None, "reason": str}
"""
import re
from typing import Optional

# ── Platform limits ────────────────────────────────────────────────────────
TITLE_LIMITS = {"taobao": 60, "douyin": 60, "xiaohongshu": 100}

BANNED_WORDS = [
    "最好", "第一", "最大", "最高", "最强", "最优", "顶级",
    "极品", "完美", "无与伦比", "史上最", "绝对",
]

REQUIRED_ATTRIBUTE_KEYS_BY_CATEGORY = {
    "收纳": ["颜色", "材质", "尺寸"],
    "家纺": ["颜色", "材质", "尺寸", "适用床型"],
    "厨具": ["颜色", "材质", "容量"],
    "装饰": ["颜色", "材质", "尺寸"],
    "清洁": ["颜色", "材质"],
}
DEFAULT_REQUIRED_KEYS = ["颜色", "材质"]


def _required_keys(category: str):
    return REQUIRED_ATTRIBUTE_KEYS_BY_CATEGORY.get(category, DEFAULT_REQUIRED_KEYS)


# ── Individual graders ─────────────────────────────────────────────────────

def title_length_check(output: dict, platform: str, **_) -> dict:
    title = output.get("title", "")
    limit = TITLE_LIMITS.get(platform, 60)
    length = len(title)
    if not title:
        return {"verdict": "fail", "score": None, "reason": "标题为空"}
    if length > limit:
        return {"verdict": "fail", "score": None,
                "reason": f"标题长度 {length} 超过 {platform} 限制 {limit} 字"}
    return {"verdict": "pass", "score": None,
            "reason": f"标题长度 {length}/{limit} 字，符合要求"}


def title_length_metric(output: dict, platform: str, **_) -> dict:
    title = output.get("title", "")
    return {"verdict": None, "score": len(title), "reason": f"标题字数: {len(title)}"}


def title_no_banned_words(output: dict, **_) -> dict:
    title = output.get("title", "")
    found = [w for w in BANNED_WORDS if w in title]
    if found:
        return {"verdict": "fail", "score": None,
                "reason": f"包含违禁词: {', '.join(found)}"}
    return {"verdict": "pass", "score": None, "reason": "无违禁词"}


def attributes_required_fields(output: dict, category: str = "", **_) -> dict:
    attrs = output.get("attributes", {})
    required = _required_keys(category)
    missing = [k for k in required if k not in attrs or not attrs[k]]
    if missing:
        coverage = (len(required) - len(missing)) / len(required)
        return {"verdict": "fail", "score": coverage,
                "reason": f"缺少必填属性: {', '.join(missing)}"}
    return {"verdict": "pass", "score": 1.0, "reason": f"必填属性完整 ({len(required)}个)"}


def main_image_count(output: dict, **_) -> dict:
    images = output.get("main_images", [])
    count = len(images)
    if count == 5:
        return {"verdict": "pass", "score": None, "reason": f"主图数量正确: 5张"}
    if count == 0:
        return {"verdict": "fail", "score": None, "reason": "无主图"}
    return {"verdict": "fail", "score": None,
            "reason": f"主图数量为 {count}，应为 5 张"}


def main_image_resolution(output: dict, **_) -> dict:
    images = output.get("main_images", [])
    if not images:
        return {"verdict": "fail", "score": None, "reason": "无主图"}
    issues = []
    for i, img in enumerate(images):
        w = img.get("width", 0)
        h = img.get("height", 0)
        if w < 800 or h < 800:
            issues.append(f"主图{i+1}: {w}×{h}")
    if issues:
        return {"verdict": "fail", "score": None,
                "reason": f"以下主图尺寸不足800px: {'; '.join(issues)}"}
    return {"verdict": "pass", "score": None, "reason": "所有主图尺寸 ≥800px"}


def detail_image_exists(output: dict, **_) -> dict:
    detail = output.get("detail_image")
    if not detail or not detail.get("url"):
        return {"verdict": "fail", "score": None, "reason": "缺少详情图"}
    return {"verdict": "pass", "score": None, "reason": "详情图存在"}


def detail_image_width(output: dict, **_) -> dict:
    detail = output.get("detail_image") or {}
    w = detail.get("width", 0)
    if w == 0:
        return {"verdict": None, "score": None, "reason": "详情图宽度未知"}
    if w < 750:
        return {"verdict": "fail", "score": None,
                "reason": f"详情图宽度 {w}px，应 ≥750px"}
    return {"verdict": "pass", "score": None, "reason": f"详情图宽度 {w}px"}


def output_schema_valid(output: dict, **_) -> dict:
    required_top = ["title", "attributes", "selling_points", "main_images"]
    missing = [k for k in required_top if k not in output]
    if missing:
        return {"verdict": "fail", "score": None,
                "reason": f"输出缺少字段: {', '.join(missing)}"}
    return {"verdict": "pass", "score": None, "reason": "输出结构符合接口契约"}


def compliance_check(output: dict, **_) -> dict:
    compliance = output.get("compliance", {})
    if not compliance:
        return {"verdict": None, "score": None, "reason": "未包含合规检查结果"}
    if compliance.get("passed"):
        return {"verdict": "pass", "score": None, "reason": "合规检查通过"}
    issues = compliance.get("issues", [])
    issue_msgs = []
    for issue in issues:
        if isinstance(issue, dict):
            issue_msgs.append(issue.get("message", str(issue)))
        else:
            issue_msgs.append(str(issue))
    return {"verdict": "fail", "score": None,
            "reason": f"合规问题: {', '.join(issue_msgs) if issue_msgs else '未知'}"}


def steps_completed(trace: Optional[dict], **_) -> dict:
    if not trace:
        return {"verdict": None, "score": None, "reason": "无 trace 数据"}
    steps = trace.get("steps", [])
    failed = [s["name"] for s in steps if s.get("status") == "failed"]
    if failed:
        return {"verdict": "fail", "score": None,
                "reason": f"以下步骤失败: {', '.join(failed)}"}
    return {"verdict": "pass", "score": None,
            "reason": f"所有 {len(steps)} 个步骤成功完成"}


def total_tokens_metric(trace: Optional[dict], **_) -> dict:
    if not trace:
        return {"verdict": None, "score": 0, "reason": "无 trace"}
    tokens = trace.get("total_tokens", 0)
    return {"verdict": None, "score": tokens, "reason": f"总 Token: {tokens}"}


def total_duration_metric(duration_ms: int = 0, **_) -> dict:
    return {"verdict": None, "score": duration_ms,
            "reason": f"总耗时: {duration_ms/1000:.1f}s"}


def total_cost_metric(cost_rmb: float = 0, **_) -> dict:
    return {"verdict": None, "score": round(cost_rmb, 4),
            "reason": f"费用: ¥{cost_rmb:.4f}"}


# ── New v2 graders ────────────────────────────────────────────────────────────

def main_image_first_white_bg(output: dict, **_) -> dict:
    """第一张主图应为白底/浅色背景（四角亮度均值≥230）。"""
    images = output.get("main_images", [])
    if not images:
        return {"verdict": "fail", "score": None, "reason": "无主图"}
    first = images[0]
    url = first.get("url", "")
    if not url:
        return {"verdict": None, "score": None, "reason": "主图无 URL，跳过检查"}
    try:
        import io, requests
        from PIL import Image
        resp = requests.get(url, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        if w < 10 or h < 10:
            return {"verdict": None, "score": None, "reason": "图片尺寸过小，无法检测"}
        sample_pts = [(5, 5), (w - 6, 5), (5, h - 6), (w - 6, h - 6)]
        avg_brightness = sum(sum(img.getpixel(p)) / 3 for p in sample_pts) / 4
        if avg_brightness >= 230:
            return {"verdict": "pass", "score": None,
                    "reason": f"第一主图四角亮度 {avg_brightness:.0f}≥230，判定为白底"}
        return {"verdict": "fail", "score": None,
                "reason": f"第一主图四角亮度 {avg_brightness:.0f}<230，不符合白底要求"}
    except Exception as e:
        return {"verdict": None, "score": None, "reason": f"图片检测失败: {str(e)[:80]}"}


_CATEGORY_KEYWORDS = {
    "收纳": ["收纳"],
    "家纺": ["家纺", "被", "枕", "床单", "毛毯"],
    "厨具": ["锅", "碗", "厨", "炊", "勺", "刀"],
    "装饰": ["装饰", "花瓶", "摆件", "挂画", "灯"],
    "清洁": ["清洁", "拖把", "扫", "刷", "擦"],
}


def title_has_core_keyword(output: dict, category: str = "", **_) -> dict:
    """标题前25字内应包含品类核心关键词（帮助搜索召回）。"""
    title = output.get("title", "")
    if not title:
        return {"verdict": "fail", "score": None, "reason": "标题为空"}
    lead = title[:25]
    keywords = _CATEGORY_KEYWORDS.get(category, [category] if category else [])
    if not keywords:
        return {"verdict": None, "score": None, "reason": f"品类 '{category}' 无预设关键词，跳过"}
    hit = next((kw for kw in keywords if kw in lead), None)
    if hit:
        return {"verdict": "pass", "score": None,
                "reason": f"标题前25字含品类词「{hit}」，利于搜索召回"}
    return {"verdict": "fail", "score": None,
            "reason": f"标题前25字未见品类词（{'/'.join(keywords)}），可能影响搜索召回"}


def attribute_value_quality(output: dict, **_) -> dict:
    """属性值不应为空、十六进制色号或纯占位词。"""
    attrs = output.get("attributes", {})
    if not attrs:
        return {"verdict": None, "score": None, "reason": "属性为空，跳过质量检查"}
    bad = []
    hex_pat = re.compile(r'^#[0-9A-Fa-f]{3,6}$')
    placeholder_vals = {"无", "N/A", "n/a", "未知", "其他", "—", "-", ""}
    for k, v in attrs.items():
        sv = str(v).strip() if v is not None else ""
        if not sv or sv in placeholder_vals:
            bad.append(f"{k}=空")
        elif hex_pat.match(sv):
            bad.append(f"{k}={sv}（色号）")
    if bad:
        coverage = (len(attrs) - len(bad)) / len(attrs)
        return {"verdict": "fail", "score": coverage,
                "reason": f"属性值质量差: {'; '.join(bad[:5])}"}
    return {"verdict": "pass", "score": 1.0, "reason": f"全部 {len(attrs)} 个属性值有效"}


def selling_point_count(output: dict, **_) -> dict:
    """卖点数量（信息指标）。"""
    count = len(output.get("selling_points", []))
    return {"verdict": None, "score": count, "reason": f"卖点数: {count}"}


def main_image_bg_diversity(output: dict, **_) -> dict:
    """主图背景类型多样性（信息指标）。"""
    images = output.get("main_images", [])
    roles = [img.get("role") or img.get("purpose") or "" for img in images]
    unique_roles = len(set(r for r in roles if r))
    return {"verdict": None, "score": unique_roles,
            "reason": f"主图共 {unique_roles} 种背景角色: {', '.join(set(roles)) or '未知'}"}


def body_copy_length(body_copy: str = "", **_) -> dict:
    """正文(body_copy)字符数应≥100字，否则内容单薄。"""
    length = len(body_copy.strip())
    if length == 0:
        return {"verdict": "fail", "score": 0, "reason": "正文(body_copy)为空"}
    if length < 100:
        return {"verdict": "fail", "score": length,
                "reason": f"正文仅 {length} 字，内容偏单薄（应≥100字）"}
    return {"verdict": "pass", "score": length,
            "reason": f"正文 {length} 字，内容充实"}
