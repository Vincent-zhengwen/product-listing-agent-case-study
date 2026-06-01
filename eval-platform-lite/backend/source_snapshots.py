from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from project_paths import AGENT_DB


SNAPSHOT_VERSION = "source-package-v1"


def load_json(value: Any, default: Any):
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def normalize_images(images: Any, fallback_url: str = "") -> list[dict]:
    items = load_json(images, [])
    if isinstance(items, dict):
        items = items.get("images") or items.get("items") or []
    if not isinstance(items, list):
        items = []

    out: list[dict] = []
    for idx, item in enumerate(items):
        if isinstance(item, str):
            url = item
            out.append({"url": url, "label": "source_image", "index": idx + 1})
        elif isinstance(item, dict):
            url = item.get("url") or item.get("image_url") or item.get("image") or item.get("src") or ""
            if not url:
                continue
            img = dict(item)
            img["url"] = url
            img.setdefault("label", item.get("label") or item.get("name") or "source_image")
            img.setdefault("index", idx + 1)
            out.append(img)

    if not out and fallback_url:
        out.append({"url": fallback_url, "label": "source_cover", "index": 1})
    return out


def meaningful_attributes(attributes: dict | None) -> dict:
    """Keep product facts; drop collector metadata such as _keyword."""
    if not isinstance(attributes, dict):
        return {}
    out = {}
    for key, value in attributes.items():
        if not key or str(key).startswith("_"):
            continue
        if value is None or str(value).strip() == "":
            continue
        out[str(key)] = value
    return out


def snapshot_completeness(snapshot: dict) -> dict:
    attributes = snapshot.get("attributes") or {}
    meaningful_attrs = meaningful_attributes(attributes)
    images = snapshot.get("images") or []
    raw_data = snapshot.get("raw_data") or {}
    checks = {
        "source_url": bool(snapshot.get("url")),
        "title": bool(snapshot.get("title")),
        "attributes": bool(meaningful_attrs),
        "images": bool(images),
        "raw_data": bool(raw_data),
        "platform": bool(snapshot.get("platform")),
    }
    weights = {
        "source_url": 10,
        "title": 20,
        "attributes": 25,
        "images": 25,
        "raw_data": 15,
        "platform": 5,
    }
    score = sum(weights[key] for key, ok in checks.items() if ok)
    missing = [key for key, ok in checks.items() if not ok]
    status = "ready" if score >= 85 else "partial" if score >= 45 else "missing"
    return {
        "score": score,
        "status": status,
        "missing": missing,
        "checks": checks,
        "attributes_count": len(meaningful_attrs),
        "raw_attributes_count": len(attributes) if isinstance(attributes, dict) else 0,
        "images_count": len(images),
        "raw_data_available": bool(raw_data),
    }


def build_source_snapshot(source_url: str, test_case: dict | None = None) -> dict:
    if not source_url or not AGENT_DB.exists():
        return {}

    try:
        conn = sqlite3.connect(AGENT_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, platform, title, price, url, image_url, supplier, raw_data, "
            "detail_url, location, keyword, attributes, raw_attributes, images, "
            "estimated_selling_price, estimated_profit, profit_margin, supplier_tier, "
            "supports_dropshipping, shipping_promise, transactions_30d, verified "
            "FROM sources WHERE url=? ORDER BY id DESC LIMIT 1",
            (source_url,),
        ).fetchone()
        conn.close()
    except Exception:
        return {}

    if not row:
        return {}

    raw_data = load_json(row["raw_data"], {})
    attributes = load_json(row["attributes"], {})
    images = normalize_images(row["images"], row["image_url"] or raw_data.get("image_url", ""))
    refs = {}
    tags = []
    notes = ""
    if test_case:
        refs = {
            "taobao": test_case.get("taobao_ref_url") or "",
            "douyin": test_case.get("douyin_ref_url") or "",
            "xiaohongshu": test_case.get("xiaohongshu_ref_url") or "",
        }
        tags = load_json(test_case.get("tags"), [])
        notes = test_case.get("notes") or ""

    snapshot = {
        "snapshot_version": SNAPSHOT_VERSION,
        "source_id": str(row["id"]),
        "platform": row["platform"] or raw_data.get("platform", ""),
        "title": row["title"] or raw_data.get("title", ""),
        "price": row["price"] if row["price"] is not None else raw_data.get("price"),
        "url": row["url"] or source_url,
        "detail_url": row["detail_url"] or raw_data.get("detail_url", ""),
        "supplier": row["supplier"] or raw_data.get("supplier", ""),
        "location": row["location"] or raw_data.get("location", ""),
        "keyword": row["keyword"] or raw_data.get("keyword", ""),
        "attributes": attributes,
        "raw_attributes": row["raw_attributes"] or "",
        "images": images,
        "raw_data": raw_data,
        "business": {
            "estimated_selling_price": row["estimated_selling_price"] or raw_data.get("estimated_selling_price"),
            "estimated_profit": row["estimated_profit"] or raw_data.get("estimated_profit"),
            "profit_margin": row["profit_margin"] or raw_data.get("profit_margin"),
            "supplier_tier": row["supplier_tier"] or raw_data.get("supplier_tier"),
            "supports_dropshipping": bool(row["supports_dropshipping"] or raw_data.get("supports_dropshipping")),
            "shipping_promise": row["shipping_promise"] or raw_data.get("shipping_promise"),
            "transactions_30d": row["transactions_30d"] or raw_data.get("transactions_30d"),
            "verified": bool(row["verified"] or raw_data.get("verified")),
        },
        "references": refs,
        "platform_rules": {
            "target_platform": "taobao",
            "main_images_required": 5,
            "title_language": "zh-CN",
            "hard_rules": [
                "主图必须可读取且主体清晰",
                "5 张主图应承担不同展示角色",
                "标题、属性和卖点中的具体事实必须能回指源页",
            ],
        },
        "expected_observations": {
            "category": (test_case or {}).get("category", ""),
            "difficulty": (test_case or {}).get("difficulty", ""),
            "source_quality": (test_case or {}).get("source_quality", ""),
            "tags": tags,
            "notes": notes,
        },
    }
    snapshot["completeness"] = snapshot_completeness(snapshot)
    return snapshot


def get_case_snapshot(db, test_case_id: str) -> dict | None:
    if not test_case_id:
        return None
    row = db.execute(
        "SELECT * FROM case_snapshots WHERE test_case_id=?",
        (test_case_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    snapshot = load_json(d.get("snapshot_json"), {})
    completeness = load_json(d.get("completeness_json"), {})
    snapshot.setdefault("completeness", completeness)
    snapshot["_snapshot_meta"] = {
        "id": d.get("id"),
        "quality_score": d.get("quality_score"),
        "status": completeness.get("status"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }
    return snapshot


def upsert_case_snapshot(db, test_case_id: str) -> dict:
    case = db.execute("SELECT * FROM test_cases WHERE id=?", (test_case_id,)).fetchone()
    if not case:
        raise ValueError("test case not found")

    test_case = dict(case)
    snapshot = build_source_snapshot(test_case.get("source_url", ""), test_case)
    if not snapshot:
        snapshot = {
            "snapshot_version": SNAPSHOT_VERSION,
            "url": test_case.get("source_url", ""),
            "title": "",
            "attributes": {},
            "images": [],
            "raw_data": {},
            "references": {
                "taobao": test_case.get("taobao_ref_url") or "",
                "douyin": test_case.get("douyin_ref_url") or "",
                "xiaohongshu": test_case.get("xiaohongshu_ref_url") or "",
            },
            "expected_observations": {
                "category": test_case.get("category", ""),
                "difficulty": test_case.get("difficulty", ""),
                "source_quality": test_case.get("source_quality", ""),
                "tags": load_json(test_case.get("tags"), []),
                "notes": test_case.get("notes") or "",
            },
        }
        snapshot["completeness"] = snapshot_completeness(snapshot)

    completeness = snapshot.get("completeness") or snapshot_completeness(snapshot)
    now = datetime.now().isoformat(timespec="seconds")
    existing = db.execute("SELECT id FROM case_snapshots WHERE test_case_id=?", (test_case_id,)).fetchone()
    snapshot_id = existing["id"] if existing else str(uuid.uuid4())
    values = (
        snapshot_id,
        test_case_id,
        snapshot.get("url") or test_case.get("source_url", ""),
        snapshot.get("source_id", ""),
        snapshot.get("snapshot_version", SNAPSHOT_VERSION),
        snapshot.get("title", ""),
        completeness.get("attributes_count", 0),
        completeness.get("images_count", 0),
        1 if completeness.get("raw_data_available") else 0,
        completeness.get("score", 0),
        json.dumps(completeness, ensure_ascii=False),
        json.dumps(snapshot, ensure_ascii=False),
        now,
    )
    db.execute(
        "INSERT INTO case_snapshots (id, test_case_id, source_url, source_id, snapshot_version, "
        "source_title, attributes_count, images_count, raw_data_available, quality_score, "
        "completeness_json, snapshot_json, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(test_case_id) DO UPDATE SET "
        "source_url=excluded.source_url, source_id=excluded.source_id, "
        "snapshot_version=excluded.snapshot_version, source_title=excluded.source_title, "
        "attributes_count=excluded.attributes_count, images_count=excluded.images_count, "
        "raw_data_available=excluded.raw_data_available, quality_score=excluded.quality_score, "
        "completeness_json=excluded.completeness_json, snapshot_json=excluded.snapshot_json, "
        "updated_at=excluded.updated_at",
        values,
    )
    snapshot["_snapshot_meta"] = {
        "id": snapshot_id,
        "quality_score": completeness.get("score", 0),
        "status": completeness.get("status", "missing"),
        "updated_at": now,
    }
    return snapshot
