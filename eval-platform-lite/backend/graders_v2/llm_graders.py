"""
LLM Graders v2 — G12, G13
Uses deepseek-v3 via DashScope (OpenAI-compatible API).
NOT using qwen to avoid self-enhancement bias (Agent uses qwen).
"""
import os
import json
import re
from typing import Optional

from openai import OpenAI


# ── LLM client (singleton) ──────────────────────────────────────────────────

_client: Optional[OpenAI] = None


def _get_client() -> Optional[OpenAI]:
    global _client
    if _client:
        return _client
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    _client = OpenAI(api_key=api_key, base_url=base_url)
    return _client


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


def _call_llm(system_prompt: str, user_content: str, model: str = None,
              max_tokens: int = 800) -> Optional[str]:
    """Call LLM and return raw text response. Returns None on failure."""
    client = _get_client()
    if not client:
        return None
    model = model or os.getenv("GRADER_LLM_MODEL", "deepseek-v3")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def _extract_json(text: str) -> Optional[dict]:
    """Extract first JSON object from LLM response."""
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── G12: selling_point_evidence ─────────────────────────────────────────────

_G12_SYSTEM = """你是一名资深电商运营专家。你的任务是逐条判断商品卖点是否提供了具体的、可感知的证据。

判断标准：
- PASS: 卖点包含以下至少一种：(a) 具体使用场景 (b) 具体参数/数值 (c) 可观察的物理特征 (d) 与竞品的明确对比
- FAIL: 卖点是抽象结论、情绪修辞或空洞口号，缺乏上述四种证据

示例：
- "玻璃杯口径8cm，手能伸进去擦底部" → PASS (具体参数+场景)
- "底部硅胶垫，单手拿不烫手" → PASS (物理特征+场景)
- "高颜值设计" → FAIL (抽象结论)
- "一燃即静" → FAIL (情绪修辞)
- "品质保证" → FAIL (空洞口号)

只输出 JSON，不要有其他内容。"""


def selling_point_evidence(output: dict, **_) -> dict:
    """G12: Judge whether each selling point has perceivable evidence."""
    selling_points = output.get("selling_points", [])
    if not selling_points:
        return _result("selling_point_evidence", "pass", "warning",
                       critique="无卖点，跳过证据检测（G01 已覆盖）")

    client = _get_client()
    if not client:
        return _result("selling_point_evidence", "skipped", "warning",
                       critique="LLM API key 未配置", confidence="low")

    sp_list = "\n".join(f"{i+1}. {sp}" for i, sp in enumerate(selling_points))
    user_content = f"""请逐条判断以下 {len(selling_points)} 个卖点是否有可感知证据。

## 卖点列表
{sp_list}

## 输出格式
```json
{{
  "per_sp": [
    {{"index": 0, "text": "卖点原文", "verdict": "pass"|"fail", "reason": "一句话说明"}},
    ...
  ]
}}
```"""

    try:
        raw = _call_llm(_G12_SYSTEM, user_content)
        if not raw:
            return _result("selling_point_evidence", "skipped", "warning",
                           critique="LLM 调用失败", confidence="low")

        parsed = _extract_json(raw)
        if not parsed or "per_sp" not in parsed:
            return _result("selling_point_evidence", "skipped", "warning",
                           critique=f"LLM 输出解析失败: {raw[:100]}", confidence="low")

        per_sp = parsed["per_sp"]
        failures = []
        for item in per_sp:
            if item.get("verdict") == "fail":
                idx = item.get("index", "?")
                failures.append({
                    "field": f"selling_points[{idx}]",
                    "issue_type": "no_evidence",
                    "evidence": {"text": item.get("text", "")[:80],
                                 "reason": item.get("reason", "")},
                    "evidence_quote": f"卖点{idx+1 if isinstance(idx, int) else idx}「{item.get('text', '')[:30]}」无可感知证据: {item.get('reason', '')}",
                    "severity": "warning",
                    "suggested_fix": "补充具体场景/参数/物理特征，不要用空洞修辞",
                })

        fail_count = len(failures)
        total = len(selling_points)
        # fail if more than half of selling points lack evidence
        verdict = "fail" if fail_count > total / 2 else "pass"

        return _result("selling_point_evidence", verdict, "warning", failures,
                       f"{fail_count}/{total} 个卖点缺乏可感知证据",
                       confidence="medium")

    except Exception as e:
        return _result("selling_point_evidence", "skipped", "warning",
                       critique=f"G12 异常: {str(e)[:80]}", confidence="low")


# ── G13: body_copy_quality ──────────────────────────────────────────────────

_G13_SYSTEM = """你是一名资深电商运营专家。你的任务是判断商品正文文案的内容质量。

判断标准：
- PASS 条件（必须同时满足）:
  1. 正文 ≥ 100 字
  2. 包含以下叙事维度中的至少 2 个：(a) 痛点/场景引入 (b) 产品功能描述 (c) 信任背书（材质/工艺/品牌）
  3. 不是模板填空

- FAIL 条件（满足任一）:
  1. 正文 < 100 字或为空
  2. 纯参数堆砌，无叙事结构
  3. 纯情绪修辞，无实质内容
  4. 模板填空（如"这款XX真的太好用了"）

只输出 JSON，不要有其他内容。"""


def body_copy_quality(output: dict, platform: str = "taobao", **_) -> dict:
    """G13: Judge body copy content quality."""
    body = output.get("body_copy", "")

    # Quick code check first: empty or too short → fail without LLM
    if not body or len(body.strip()) < 10:
        return _result("body_copy_quality", "fail", "warning",
                       [{
                           "field": "body_copy",
                           "issue_type": "empty_or_too_short",
                           "evidence": {"length": len(body.strip()) if body else 0},
                           "evidence_quote": f"正文仅 {len(body.strip()) if body else 0} 字，远低于 100 字门槛",
                           "severity": "warning",
                           "suggested_fix": "CopyAgent 必须生成 ≥100 字的结构化正文",
                       }],
                       "正文过短或为空")

    client = _get_client()
    if not client:
        return _result("body_copy_quality", "skipped", "warning",
                       critique="LLM API key 未配置", confidence="low")

    user_content = f"""请判断以下商品正文文案的内容质量。

## 平台
{platform}

## 正文文案（{len(body)} 字）
{body[:2000]}

## 输出格式
```json
{{
  "verdict": "pass" | "fail",
  "char_count": {len(body)},
  "has_pain_point": true|false,
  "has_function_desc": true|false,
  "has_trust_signal": true|false,
  "is_template": true|false,
  "reason": "一句话总结"
}}
```"""

    try:
        raw = _call_llm(_G13_SYSTEM, user_content)
        if not raw:
            return _result("body_copy_quality", "skipped", "warning",
                           critique="LLM 调用失败", confidence="low")

        parsed = _extract_json(raw)
        if not parsed:
            return _result("body_copy_quality", "skipped", "warning",
                           critique=f"LLM 输出解析失败: {raw[:100]}", confidence="low")

        verdict = parsed.get("verdict", "fail")
        failures = []
        if verdict == "fail":
            failures.append({
                "field": "body_copy",
                "issue_type": "low_quality_body",
                "evidence": {
                    "char_count": parsed.get("char_count", len(body)),
                    "has_pain_point": parsed.get("has_pain_point"),
                    "has_function_desc": parsed.get("has_function_desc"),
                    "has_trust_signal": parsed.get("has_trust_signal"),
                    "is_template": parsed.get("is_template"),
                },
                "evidence_quote": parsed.get("reason", "正文质量不合格"),
                "severity": "warning",
                "suggested_fix": "正文需要包含痛点引入 + 功能描述 + 信任背书中的至少 2 个",
            })

        return _result("body_copy_quality", verdict, "warning", failures,
                       parsed.get("reason", ""),
                       confidence="medium")

    except Exception as e:
        return _result("body_copy_quality", "skipped", "warning",
                       critique=f"G13 异常: {str(e)[:80]}", confidence="low")


# ── G11: copy_factual_grounding ─────────────────────────────────────────────

_G11_SYSTEM = """你是一名严格的电商内容审核专家。你的任务是检测 Agent 生成的商品文案中，是否包含货源页 ground truth 里找不到任何依据的具体数值/参数。

判断标准：
- FAIL: 文案出现具体可验证的数值/参数（色温/尺寸/重量/克数/天数/次数/百分比/温度/材质规格等），但源页 attributes 里找不到对应依据
- PASS: 所有具体参数都能在源页找到来源；或者文案只是感官、场景、修辞描述（不含可验证数值）

注意：
- 感官词（"温润光感"、"轻盈手感"）不算虚构
- 场景词（"放在床头"、"卧室氛围"）不算虚构
- 只有具体可量化的参数才算 — 数字+单位、明确等级、明确属性值
- 如果源页 attributes 完全为空，应输出 verdict="skipped"

只输出 JSON，不要有其他内容。"""


def copy_factual_grounding(output: dict, source_attributes: dict = None,
                           source_data: dict = None, **_) -> dict:
    """G11: Detect fabricated facts in agent copy that have no source ground truth."""
    # Use source_data.attributes if provided, fall back to source_attributes
    src_attrs = (source_data or {}).get("attributes") or source_attributes or {}

    if not src_attrs:
        return _result("copy_factual_grounding", "skipped", "blocker",
                       critique="源页 attributes 为空，无法判断虚构（源页失效或未爬取）",
                       confidence="low")

    title = output.get("title", "")
    selling_points = output.get("selling_points", [])
    body = output.get("body_copy", "")

    if not title and not selling_points and not body:
        return _result("copy_factual_grounding", "skipped", "blocker",
                       critique="Agent 文案为空，无内容可判")

    client = _get_client()
    if not client:
        return _result("copy_factual_grounding", "skipped", "blocker",
                       critique="LLM API key 未配置", confidence="low")

    sp_text = "\n".join(f"  {i+1}. {sp}" for i, sp in enumerate(selling_points)) if selling_points else "  (无)"
    src_attrs_text = json.dumps(src_attrs, ensure_ascii=False, indent=2)

    user_content = f"""请检查以下商品文案是否含有源页找不到依据的具体数值/参数。

## 源页 ground truth attributes
{src_attrs_text}

## Agent 生成的文案
- 标题: {title}
- 卖点:
{sp_text}
- 正文: {body[:1500]}

## 输出格式
```json
{{
  "verdict": "pass" | "fail",
  "fabricated_facts": [
    {{"text": "虚构片段原文", "field": "title|selling_points[i]|body_copy", "reason": "源页无对应依据"}}
  ],
  "critique": "一句话总结"
}}
```"""

    try:
        raw = _call_llm(_G11_SYSTEM, user_content, max_tokens=1000)
        if not raw:
            return _result("copy_factual_grounding", "skipped", "blocker",
                           critique="LLM 调用失败", confidence="low")

        parsed = _extract_json(raw)
        if not parsed:
            return _result("copy_factual_grounding", "skipped", "blocker",
                           critique=f"LLM 输出解析失败: {raw[:100]}", confidence="low")

        verdict = parsed.get("verdict", "skipped")
        fabricated = parsed.get("fabricated_facts", [])
        failures = []
        for item in fabricated:
            failures.append({
                "field": item.get("field", "unknown"),
                "issue_type": "fabricated_fact",
                "evidence": {"text": item.get("text", ""),
                             "reason": item.get("reason", "")},
                "evidence_quote": f"虚构「{item.get('text', '')[:40]}」: {item.get('reason', '')}",
                "severity": "blocker",
                "suggested_fix": "CopyAgent 必须基于源页属性生成具体数值，不能编造",
            })

        return _result("copy_factual_grounding", verdict, "blocker", failures,
                       parsed.get("critique", f"{len(failures)} 处虚构事实"),
                       confidence="medium")
    except Exception as e:
        return _result("copy_factual_grounding", "skipped", "blocker",
                       critique=f"G11 异常: {str(e)[:80]}", confidence="low")
