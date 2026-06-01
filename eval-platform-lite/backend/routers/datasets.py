import uuid, json, csv, io, re
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database import get_db
from models import DatasetCreate, DatasetUpdate

router = APIRouter()

# ── keyword maps for category inference ────────────────────────────────────
CATEGORY_KEYWORDS = {
    "收纳": ["收纳", "整理", "储物", "置物", "分格", "抽屉", "收纳盒", "收纳箱", "收纳柜", "置物架"],
    "家纺": ["床上用品", "被子", "被套", "枕头", "枕套", "床单", "毛毯", "毛巾", "浴巾", "床笠", "家纺"],
    "厨具": ["厨房", "锅", "碗", "刀", "砧板", "炊具", "餐具", "筷子", "勺子", "铲子", "烹饪", "厨具"],
    "装饰": ["摆件", "装饰", "挂画", "花瓶", "壁挂", "摆设", "艺术品", "diy", "ins风", "北欧风"],
    "清洁": ["清洁", "拖把", "扫帚", "刷子", "抹布", "洗碗", "清洗", "打扫", "卫生", "消毒"],
}

def _infer_category(text: str) -> str:
    text_lower = text.lower()
    scores = {cat: sum(1 for kw in kws if kw in text_lower) for cat, kws in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "其他"

def _infer_quality(html: str) -> str:
    img_count = len(re.findall(r'<img\b', html, re.I))
    attr_count = len(re.findall(r'<td|<tr', html, re.I))
    if img_count >= 8 and attr_count >= 20:
        return "rich"
    if img_count <= 2 or attr_count <= 6:
        return "sparse"
    return "medium"

class AnalyzeUrlRequest(BaseModel):
    source_url: str

@router.post("/analyze-url")
async def analyze_url(body: AnalyzeUrlRequest):
    """Fetch the source URL and infer category / source_quality."""
    import httpx
    result = {
        "category": "其他",
        "source_quality": "medium",
        "difficulty": "medium",
        "title": "",
    }
    try:
        async with httpx.AsyncClient(
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(body.source_url)
            html = resp.text

        # extract title
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ""
        result["title"] = title[:80]

        # infer fields
        combined = title + " " + body.source_url
        result["category"] = _infer_category(combined)
        result["source_quality"] = _infer_quality(html)
        result["difficulty"] = "hard" if result["source_quality"] == "sparse" else \
                                "easy" if result["source_quality"] == "rich" else "medium"
    except Exception:
        # graceful fallback: try URL-only inference
        result["category"] = _infer_category(body.source_url)

    return result

# ── CSV template ────────────────────────────────────────────────────────────
CSV_TEMPLATE = """\
source_url,category,difficulty,source_quality,taobao_url,douyin_url,xiaohongshu_url,notes
https://detail.1688.com/offer/示例1.html,收纳,medium,medium,https://item.taobao.com/示例,,，参考竞品留一条即可
https://detail.1688.com/offer/示例2.html,家纺,easy,rich,,https://v.douyin.com/示例,，
https://detail.1688.com/offer/示例3.html,厨具,hard,sparse,,,，货源页图片很少
"""

@router.get("/csv-template")
def csv_template():
    return StreamingResponse(
        io.BytesIO(CSV_TEMPLATE.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=eval_cases_template.csv"},
    )


def row_to_dict(row):
    return dict(row) if row else None


@router.get("")
def list_datasets():
    db = get_db()
    rows = db.execute(
        "SELECT d.*, COUNT(tc.id) as case_count FROM datasets d "
        "LEFT JOIN test_cases tc ON tc.dataset_id = d.id "
        "WHERE d.status != 'deleted' "
        "GROUP BY d.id ORDER BY d.created_at DESC"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
def create_dataset(body: DatasetCreate):
    db = get_db()
    did = str(uuid.uuid4())
    db.execute(
        "INSERT INTO datasets (id, name, description, version) VALUES (?,?,?,?)",
        (did, body.name, body.description, body.version)
    )
    db.commit()
    row = db.execute("SELECT * FROM datasets WHERE id=?", (did,)).fetchone()
    db.close()
    return row_to_dict(row)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Dataset not found")
    return row_to_dict(row)


@router.patch("/{dataset_id}")
def update_dataset(dataset_id: str, body: DatasetUpdate):
    db = get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    sets = ", ".join(f"{k}=?" for k in updates)
    db.execute(f"UPDATE datasets SET {sets} WHERE id=?", (*updates.values(), dataset_id))
    db.commit()
    row = db.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    db.close()
    return row_to_dict(row)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str):
    db = get_db()
    db.execute("UPDATE datasets SET status='deleted' WHERE id=?", (dataset_id,))
    db.commit()
    db.close()
    return {"ok": True}


@router.post("/{dataset_id}/import-csv")
async def import_csv(dataset_id: str, file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    db = get_db()
    inserted = 0
    errors = []
    for i, row in enumerate(reader):
        source_url = row.get("source_url", "").strip()
        if not source_url:
            errors.append(f"Row {i+2}: missing source_url")
            continue
        cid = str(uuid.uuid4())
        tags = json.dumps([t.strip() for t in row.get("tags", "").split(",") if t.strip()])
        db.execute(
            "INSERT INTO test_cases (id, dataset_id, source_url, category, difficulty, "
            "source_quality, taobao_ref_url, douyin_ref_url, xiaohongshu_ref_url, tags) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cid, dataset_id, source_url,
             row.get("category", "").strip(),
             row.get("difficulty", "medium").strip(),
             row.get("source_quality", "medium").strip(),
             row.get("taobao_url", "").strip(),
             row.get("douyin_url", "").strip(),
             row.get("xiaohongshu_url", "").strip(),
             tags)
        )
        inserted += 1
    db.commit()
    db.close()
    return {"inserted": inserted, "errors": errors}
