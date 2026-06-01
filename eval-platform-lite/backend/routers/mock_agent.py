"""
Mock Agent — simulates realistic Listing Agent responses for testing.
Injects random variance to produce pass/fail patterns.
"""
import random, time, asyncio, httpx
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class AgentRequest(BaseModel):
    task_id: str
    source_url: str
    platform: str
    callback_url: str


CATEGORIES = ["收纳", "家纺", "厨具", "装饰", "清洁"]
IMAGE_ROLES = ["hero_shot", "detail_feature", "scene_lifestyle", "size_chart", "sku_variants"]

SELLING_POINTS_POOL = {
    "taobao": [
        "大容量分格设计，收纳效率提升3倍",
        "PP食品级材质，安全无异味",
        "可叠加设计，最高叠放5层",
        "哑光质感，高级感十足，不易留指纹",
        "尺寸精准适配标准抽屉，拿出即用",
    ],
    "douyin": [
        "宝藏收纳神器！整理党必入✨",
        "抽屉乱了就靠它，2分钟搞定",
        "买了真的回不去了，家里瞬间整洁",
        "颜值超高，放在桌上就是装饰品",
        "上班族救星，早上再也不找东西了",
    ],
    "xiaohongshu": [
        "分享一个让家里立刻变整洁的小物",
        "北欧ins风，和家里整体风格超搭",
        "用了半年，每天看了都心情好",
        "男朋友看了也说终于不乱了哈哈",
        "囤了3个，书房厨房卫生间各一个",
    ],
}

B2B_SELLING_POINTS = [
    "PP材质，环保无毒",
    "承重5KG，经纬密度380根",
    "出口品质，工厂直销",
    "MOQ 100件起，支持OEM",
]

TITLES = {
    "taobao": [
        "北欧简约ins风桌面收纳盒家用抽屉整理神器杂物储物盒大容量",
        "【爆款】多功能收纳盒家用客厅茶几零食杂物整理盒桌面置物架",
    ],
    "douyin": [
        "太好用了！整理控必买的收纳神器，抽屉再也不乱了",
        "家里变整洁就靠这个！宝藏收纳盒开箱",
    ],
    "xiaohongshu": [
        "种草｜让家里瞬间整洁的ins风收纳盒，用了真的回不去",
        "分享｜北欧风桌面收纳，小物件也要有仪式感",
    ],
}


def _make_mock_output(platform: str, quality: str = "good") -> dict:
    """quality: good | bad | partial"""
    is_bad = quality == "bad"
    is_b2b = is_bad and random.random() > 0.5

    title = random.choice(TITLES.get(platform, TITLES["taobao"]))
    if is_bad:
        title = title[:20]  # truncate to simulate bad output

    selling_points = B2B_SELLING_POINTS if is_b2b else random.sample(
        SELLING_POINTS_POOL.get(platform, SELLING_POINTS_POOL["taobao"]), 4
    )

    image_count = 5 if quality != "bad" else random.choice([3, 4, 5])

    return {
        "title": title,
        "attributes": {
            "颜色": "白色/灰色/粉色",
            "材质": "PP塑料",
            "尺寸": "30×20×15cm",
            "重量": "280g",
            "适用场景": "桌面/抽屉/书架",
        } if not is_bad else {"颜色": "白色"},
        "selling_points": selling_points,
        "main_images": [
            {
                "role": IMAGE_ROLES[i],
                "url": f"https://mock-cdn.eval.local/main_{i+1}.jpg",
                "width": 800,
                "height": 800,
            }
            for i in range(image_count)
        ],
        "detail_image": {
            "url": "https://mock-cdn.eval.local/detail_long.jpg",
            "width": 750,
            "height": 4200,
        },
        "compliance": {
            "passed": not (is_bad and random.random() > 0.7),
            "issues": ["包含违禁词'最好'"] if (is_bad and random.random() > 0.7) else [],
        },
    }


def _make_mock_trace(duration_ms: int) -> dict:
    steps = [
        {"step_id": 1, "name": "browse_source_page", "status": "success",
         "duration_ms": 1200,
         "input": {"url": "https://1688.com/mock"},
         "output": {"images_found": 8, "main_images": 3, "detail_images": 5,
                    "attributes": {"颜色": "白色", "材质": "PP塑料", "尺寸": "30×20×15cm"}},
         "error": None},
        {"step_id": 2, "name": "visual_diagnosis", "status": "success",
         "duration_ms": 3400, "model": "qwen-vl-max", "tokens": 820,
         "input": {"images": ["img1.jpg", "img2.jpg"]},
         "output": {"quality_scores": {"main": 0.85, "detail": 0.72}, "issues": []},
         "error": None},
        {"step_id": 2.5, "name": "strategy_decision", "status": "success",
         "duration_ms": 150,
         "input": {}, "output": {"decision": "pillow_plus_crop", "reason": "主图有白底，适合裁剪优化"},
         "error": None},
        {"step_id": 3, "name": "creative_planning", "status": "success",
         "duration_ms": 4200, "model": "qwen-plus", "tokens": 1580,
         "input": {"platform": "taobao"},
         "output": {"design_plan": {"style": "北欧简约", "color_scheme": "#FFFFFF/#E8E8E8"}},
         "error": None},
        {"step_id": 4, "name": "render", "status": "success",
         "duration_ms": 6800,
         "input": {}, "output": {"rendered": 5, "skipped": 1, "skip_reason": "blank_image"},
         "error": None},
        {"step_id": 5, "name": "compliance_check", "status": "success",
         "duration_ms": 350,
         "input": {}, "output": {"banned_words_found": 0, "title_length": 42},
         "error": None},
    ]
    total_tokens = sum(s.get("tokens", 0) for s in steps if s.get("tokens"))
    return {
        "steps": steps,
        "total_tokens": total_tokens,
        "total_model_calls": 3,
    }


async def _delayed_callback(callback_url: str, task_id: str, platform: str, source_url: str):
    # simulate agent processing time: 5~15 seconds
    delay = random.uniform(1.5, 4.0)
    await asyncio.sleep(delay)

    # 80% good, 15% bad, 5% failed
    roll = random.random()
    if roll < 0.75:
        quality = "good"
        status = "success"
    elif roll < 0.92:
        quality = "bad"
        status = "partial"
    else:
        status = "failed"
        quality = "failed"

    duration_ms = int(delay * 1000 + random.randint(8000, 18000))
    cost_rmb = round(random.uniform(0.20, 0.45), 4)

    if status == "failed":
        payload = {
            "task_id": task_id,
            "status": "failed",
            "platform": platform,
            "duration_ms": duration_ms,
            "cost_rmb": 0,
            "output": None,
            "trace": None,
            "error": "货源页无法访问 (mock 模拟失败)",
        }
    else:
        output = _make_mock_output(platform, quality)
        trace = _make_mock_trace(duration_ms)
        payload = {
            "task_id": task_id,
            "status": status,
            "platform": platform,
            "duration_ms": duration_ms,
            "cost_rmb": cost_rmb,
            "output": output,
            "trace": trace,
            "error": None,
        }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(callback_url, json=payload)
    except Exception:
        pass


@router.post("/run")
async def mock_run(body: AgentRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        _delayed_callback,
        body.callback_url, body.task_id, body.platform, body.source_url
    )
    return {"accepted": True, "task_id": body.task_id}
