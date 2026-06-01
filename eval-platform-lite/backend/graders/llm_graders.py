"""
LLM-based Graders — call qwen-plus via OpenAI-compatible API.
All return binary pass/fail with confidence + reason.
If API key is not configured, returns {"verdict": None, "skipped": True}.
"""
import os, json, re
from typing import Optional
from openai import OpenAI

_client: Optional[OpenAI] = None


def _get_client() -> Optional[OpenAI]:
    global _client
    if _client:
        return _client
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    _client = OpenAI(api_key=api_key, base_url=base_url)
    return _client


def _call_llm(system_prompt: str, user_content: str) -> dict:
    client = _get_client()
    if not client:
        return {"verdict": None, "confidence": "low",
                "reason": "LLM API key 未配置，跳过评分", "skipped": True}
    model = os.getenv("GRADER_MODEL", "qwen-plus")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        # extract JSON from response
        match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"verdict": "fail", "confidence": "low",
                "reason": f"无法解析 LLM 输出: {text[:100]}"}
    except Exception as e:
        return {"verdict": None, "confidence": "low",
                "reason": f"LLM 调用失败: {str(e)}", "skipped": True}


SYSTEM = """你是一名资深电商运营专家，专注家居好物类目。
请严格按照要求进行评估，只输出 JSON，不要有任何其他内容。
JSON 格式: {"verdict": "pass" 或 "fail", "confidence": "high"/"medium"/"low", "reason": "一句话说明，不超过60字"}"""


def b2c_transform(output: dict, source_attributes: dict = None, **_) -> dict:
    selling_points = output.get("selling_points", [])
    sp_text = "\n".join(f"- {s}" for s in selling_points) if selling_points else "（无卖点）"
    src_text = json.dumps(source_attributes or {}, ensure_ascii=False) if source_attributes else "（无货源属性）"
    user_content = f"""## 评测任务
判断以下卖点文案是否已从B2B供应商话术转化为面向消费者的购买动机。

## 货源页原始属性
{src_text}

## Agent 生成的卖点
{sp_text}

## 判断标准
- FAIL: 卖点仍是参数堆砌（如"PP材质/承重5kg/经纬密度380"）
- PASS: 卖点体现了使用场景、解决的问题或情感价值（如"轻松整理杂物，一目了然"）

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


def factual_accuracy(output: dict, source_attributes: dict = None, body_copy: str = "", **_) -> dict:
    title = output.get("title", "")
    selling_points = output.get("selling_points", [])
    sp_text = "\n".join(f"- {s}" for s in selling_points)
    src_text = json.dumps(source_attributes or {}, ensure_ascii=False)
    body_section = f"\n正文:\n{body_copy[:500]}" if body_copy else ""
    user_content = f"""## 评测任务
判断文案中是否包含货源页找不到依据的商品参数或功能描述。

## 货源页原始属性
{src_text}

## Agent 生成内容
标题: {title}
卖点:
{sp_text}{body_section}

## 判断标准
- FAIL: 出现了货源页中没有依据的具体数值（次数/天数/温度/克重/厘米等具体参数）
- PASS: 所有具体参数可在货源页找到来源，或只使用了感官/场景/情感表达

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


PLATFORM_STYLE = {
    "taobao": "专业、详细、突出性价比和功能参数，适合理性购物决策",
    "douyin": "简短有力、情绪化、有爆款词、适合快速刷屏消费",
    "xiaohongshu": "生活化、种草风格、有画面感、像真实用户分享",
}


def platform_tone(output: dict, platform: str = "", **_) -> dict:
    title = output.get("title", "")
    selling_points = output.get("selling_points", [])
    sp_text = "\n".join(f"- {s}" for s in selling_points)
    style_desc = PLATFORM_STYLE.get(platform, "通用电商风格")
    user_content = f"""## 评测任务
判断文案风格是否符合 {platform} 平台用户的期望表达方式。

## 平台风格要求
{platform}: {style_desc}

## Agent 生成内容
标题: {title}
卖点:
{sp_text}

## 判断标准
- FAIL: 风格明显不符合平台调性（如小红书文案用了很多参数堆砌，或抖音文案太平淡）
- PASS: 整体风格与平台期望一致

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


def title_appeal(output: dict, category: str = "", platform: str = "", **_) -> dict:
    title = output.get("title", "")
    user_content = f"""## 评测任务
判断这个{platform}平台的{category}商品标题是否具有吸引目标用户点击的潜力。

## 标题
{title}

## 判断标准
- FAIL: 标题平淡无特色，无法触发用户好奇心或购买欲（如纯参数罗列）
- PASS: 标题包含吸引点（痛点词、场景词、数字或爆款词），有点击诱惑力

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


def image_copy_coherence(output: dict, **_) -> dict:
    selling_points = output.get("selling_points", [])
    main_images = output.get("main_images", [])
    roles = [img.get("role", "unknown") for img in main_images]
    sp_text = "\n".join(f"- {s}" for s in selling_points)
    user_content = f"""## 评测任务
判断主图的图片角色安排是否与卖点文案传达的核心信息一致。

## 主图角色序列
{', '.join(roles) if roles else '（无主图）'}

## 卖点文案
{sp_text if sp_text else '（无卖点）'}

## 判断标准
- FAIL: 图片角色与卖点核心信息明显错位（如卖点强调使用场景，但无 scene_lifestyle 图）
- PASS: 图片角色组合与卖点主题大体一致

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


def detail_image_narrative(output: dict, **_) -> dict:
    detail = output.get("detail_image") or {}
    url = detail.get("url", "")
    if not url:
        return {"verdict": "fail", "confidence": "high",
                "reason": "无详情图，无法评估叙事结构"}
    # Without vision, we evaluate based on selling_points structure
    selling_points = output.get("selling_points", [])
    sp_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(selling_points))
    user_content = f"""## 评测任务
根据卖点结构判断详情图叙事逻辑是否合理。

## 卖点列表（代表详情图内容逻辑）
{sp_text if sp_text else '（无卖点）'}

## 理想详情图叙事结构
1. 痛点/场景引入 → 2. 产品解决方案 → 3. 产品功能展示 → 4. 信任背书 → 5. 促销促单

## 判断标准
- FAIL: 卖点结构缺少明显的叙事层次，纯参数堆砌
- PASS: 卖点能体现递进的叙事逻辑

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


# ── New v2 LLM graders ────────────────────────────────────────────────────────

def selling_point_credibility(output: dict, **_) -> dict:
    """每个卖点是否提供了「凭什么」的可信证据（而非空洞口号）。"""
    selling_points = output.get("selling_points", [])
    if not selling_points:
        return {"verdict": "fail", "confidence": "high", "reason": "无卖点内容"}
    sp_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(selling_points))
    user_content = f"""## 评测任务
判断以下卖点是否具备「凭什么」的可信证据，而非空洞口号。

## 卖点列表
{sp_text}

## 判断标准
- FAIL: 超过一半的卖点只有口号式描述（如"超级好用""极致体验"），无场景、无对比、无具体感知
- PASS: 大部分卖点给出了可感知的场景证据（如"放入冰箱后味道不串""玻璃瓶口宽，手伸进去能擦到底部"）

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


def body_copy_quality(body_copy: str = "", platform: str = "", **_) -> dict:
    """正文文案是否具备结构性和实质内容（而非重复卖点堆砌）。"""
    if not body_copy or len(body_copy.strip()) < 30:
        return {"verdict": "fail", "confidence": "high",
                "reason": f"正文过短（{len(body_copy.strip())}字），内容缺失"}
    user_content = f"""## 评测任务
判断以下{platform}平台商品正文文案的内容质量。

## 正文内容
{body_copy[:800]}

## 判断标准
- FAIL: 正文是卖点的简单重复、纯参数堆砌，或内容空洞无法帮助消费者做决策
- PASS: 正文有叙事层次（如场景引入→产品功能→使用方法→信任背书），内容对消费决策有实质帮助

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


def detail_narrative_completeness(output: dict, body_copy: str = "", **_) -> dict:
    """详情图叙事是否覆盖5个核心阶段：痛点→解决方案→功能→信任→促单。"""
    detail = output.get("detail_image") or {}
    if not detail.get("url"):
        return {"verdict": "fail", "confidence": "high", "reason": "无详情图"}
    selling_points = output.get("selling_points", [])
    sp_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(selling_points))
    body_section = f"\n正文摘要:\n{body_copy[:400]}" if body_copy else ""
    user_content = f"""## 评测任务
根据卖点和正文内容，判断详情图叙事是否覆盖5个电商核心阶段。

## 卖点（代表详情图内容规划）
{sp_text if sp_text else '（无卖点）'}{body_section}

## 5个叙事阶段
1. 痛点/场景引入（用户遇到了什么问题）
2. 产品解决方案（本品如何解决）
3. 核心功能展示（卖点逐一呈现）
4. 信任背书（材质/工艺/品质/使用体验）
5. 促单引导（使用场景全景/行动号召）

## 判断标准
- FAIL: 明显缺少≥2个叙事阶段（如只有功能罗列，没有痛点和促单）
- PASS: 5个阶段基本覆盖，叙事有递进逻辑

只输出 JSON: {{"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "..."}}"""
    return _call_llm(SYSTEM, user_content)


# ── VLM graders (qwen-vl-max) ─────────────────────────────────────────────────

def _encode_image_url(url: str) -> Optional[str]:
    """下载图片并返回 base64 编码，失败返回 None。"""
    try:
        import io, base64, requests as req
        resp = req.get(url, timeout=15)
        return base64.b64encode(resp.content).decode()
    except Exception:
        return None


def _call_vlm(prompt: str, image_urls: list[str], max_images: int = 3) -> dict:
    """调用 qwen-vl-max 评估图片质量。"""
    client = _get_client()
    if not client:
        return {"verdict": None, "confidence": "low",
                "reason": "LLM API key 未配置，跳过VLM评分", "skipped": True}
    # 下载并编码图片（最多 max_images 张）
    content = []
    for url in image_urls[:max_images]:
        b64 = _encode_image_url(url)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
    if not content:
        return {"verdict": None, "confidence": "low",
                "reason": "无法下载图片，跳过VLM评分", "skipped": True}
    content.append({"type": "text", "text": prompt})
    try:
        resp = client.chat.completions.create(
            model="qwen-vl-max",
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"verdict": "fail", "confidence": "low",
                "reason": f"无法解析VLM输出: {text[:100]}"}
    except Exception as e:
        return {"verdict": None, "confidence": "low",
                "reason": f"VLM调用失败: {str(e)[:80]}", "skipped": True}


def main_image_no_supplier_text(output: dict, **_) -> dict:
    """主图中不应出现供应商水印、英文字母或B2B平台标识。"""
    images = output.get("main_images", [])
    urls = [img.get("url", "") for img in images if img.get("url")]
    if not urls:
        return {"verdict": None, "score": None, "reason": "无主图URL，跳过VLM检查"}
    prompt = """请检查以上商品主图，判断是否存在以下问题：
1. 供应商/工厂水印（如品牌LOGO、联系方式）
2. 1688/义乌购等B2B平台标识
3. 大量英文字母叠加在图片上（非英文品牌名）

判断标准：
- FAIL: 任意一张图存在上述问题
- PASS: 所有图片干净，无上述杂质

只输出 JSON: {"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "一句话说明"}"""
    return _call_vlm(prompt, urls, max_images=5)


def main_image_composition(output: dict, **_) -> dict:
    """主图构图：产品清晰可见、主体居中、背景干净不杂乱。"""
    images = output.get("main_images", [])
    urls = [img.get("url", "") for img in images if img.get("url")]
    if not urls:
        return {"verdict": None, "score": None, "reason": "无主图URL，跳过VLM检查"}
    prompt = """请评估以上商品主图的构图质量，重点检查：
1. 产品主体是否清晰可见（不模糊、不被遮挡）
2. 主体是否居中或处于视觉重心（不偏角）
3. 背景是否干净（无杂乱物品、无强烈干扰色）
4. 是否存在纯白或空白图（只有文字、无产品）

判断标准：
- FAIL: 有图片存在严重构图问题（主体不清/背景杂乱/纯文字无产品）
- PASS: 整体构图专业，产品展示清晰

只输出 JSON: {"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "一句话说明"}"""
    return _call_vlm(prompt, urls, max_images=5)


def main_image_visual_consistency(output: dict, **_) -> dict:
    """5张主图视觉风格是否统一（色调/打光/背景质感一致）。"""
    images = output.get("main_images", [])
    urls = [img.get("url", "") for img in images if img.get("url")]
    if len(urls) < 2:
        return {"verdict": None, "score": None, "reason": "主图不足2张，无法检测一致性"}
    prompt = """请观察以上多张商品主图，评估它们的视觉风格一致性：
1. 色调/白平衡是否统一（不同图片色温差异明显算失败）
2. 打光风格是否一致（有的强光有的暗调算失败）
3. 背景质感是否统一（有白底有场景图混搭算轻微失败）
4. 整体视觉感受是否像来自同一次拍摄/同一品牌

判断标准：
- FAIL: 风格明显混乱，像不同来源素材拼凑，品牌感弱
- PASS: 整体视觉统一，有品牌调性

只输出 JSON: {"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "一句话说明"}"""
    return _call_vlm(prompt, urls, max_images=5)


def detail_image_text_legibility(output: dict, **_) -> dict:
    """详情图文字是否清晰可读（字号足够、对比度高、不模糊）。"""
    detail = output.get("detail_image") or {}
    url = detail.get("url", "")
    if not url:
        return {"verdict": None, "score": None, "reason": "无详情图URL，跳过VLM检查"}
    prompt = """请检查以上详情图中的文字可读性：
1. 文字字号是否足够大（移动端小屏可读）
2. 文字与背景对比度是否足够（浅字浅底/深字深底算失败）
3. 文字是否清晰不模糊（渲染时缩放导致的模糊算失败）
4. 关键卖点文字是否突出（不被图片元素遮挡）

判断标准：
- FAIL: 存在明显的文字可读性问题
- PASS: 文字清晰，移动端体验良好

只输出 JSON: {"verdict": "pass"或"fail", "confidence": "high"/"medium"/"low", "reason": "一句话说明"}"""
    return _call_vlm(prompt, [url], max_images=1)
