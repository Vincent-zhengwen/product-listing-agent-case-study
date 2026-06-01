import uuid, json
from fastapi import APIRouter, HTTPException
from database import get_db
from models import TestCaseCreate, TestCaseUpdate
from source_snapshots import load_json, upsert_case_snapshot

router = APIRouter()


def enrich(row):
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    if "snapshot_completeness" in d:
        d["snapshot_completeness"] = load_json(d.get("snapshot_completeness"), {})
        d["snapshot"] = {
            "quality_score": d.pop("snapshot_quality_score", None),
            "status": d["snapshot_completeness"].get("status"),
            "attributes_count": d.pop("snapshot_attributes_count", 0),
            "images_count": d.pop("snapshot_images_count", 0),
            "updated_at": d.pop("snapshot_updated_at", None),
            "missing": d["snapshot_completeness"].get("missing", []),
        }
    return d


@router.get("/{dataset_id}/cases")
def list_cases(dataset_id: str, category: str = "", difficulty: str = ""):
    db = get_db()
    sql = (
        "SELECT tc.*, cs.quality_score AS snapshot_quality_score, "
        "cs.attributes_count AS snapshot_attributes_count, "
        "cs.images_count AS snapshot_images_count, "
        "cs.completeness_json AS snapshot_completeness, "
        "cs.updated_at AS snapshot_updated_at "
        "FROM test_cases tc "
        "LEFT JOIN case_snapshots cs ON cs.test_case_id = tc.id "
        "WHERE tc.dataset_id=?"
    )
    params = [dataset_id]
    if category:
        sql += " AND tc.category=?"; params.append(category)
    if difficulty:
        sql += " AND tc.difficulty=?"; params.append(difficulty)
    sql += " ORDER BY tc.created_at DESC"
    rows = db.execute(sql, params).fetchall()
    db.close()
    return [enrich(r) for r in rows]


@router.post("/{dataset_id}/cases")
def create_case(dataset_id: str, body: TestCaseCreate):
    db = get_db()
    cid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO test_cases (id, dataset_id, source_url, category, difficulty, "
        "source_quality, taobao_ref_url, douyin_ref_url, xiaohongshu_ref_url, tags, notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (cid, dataset_id, body.source_url, body.category, body.difficulty,
         body.source_quality, body.taobao_ref_url, body.douyin_ref_url,
         body.xiaohongshu_ref_url, json.dumps(body.tags), body.notes)
    )
    db.commit()
    row = db.execute("SELECT * FROM test_cases WHERE id=?", (cid,)).fetchone()
    db.close()
    return enrich(row)


@router.get("/{dataset_id}/cases/{case_id}")
def get_case(dataset_id: str, case_id: str):
    db = get_db()
    row = db.execute(
        "SELECT * FROM test_cases WHERE id=? AND dataset_id=?", (case_id, dataset_id)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Test case not found")
    return enrich(row)


@router.patch("/{dataset_id}/cases/{case_id}")
def update_case(dataset_id: str, case_id: str, body: TestCaseUpdate):
    db = get_db()
    data = body.model_dump(exclude_none=True)
    if "tags" in data:
        data["tags"] = json.dumps(data["tags"])
    if not data:
        raise HTTPException(400, "No fields")
    sets = ", ".join(f"{k}=?" for k in data)
    db.execute(f"UPDATE test_cases SET {sets} WHERE id=? AND dataset_id=?",
               (*data.values(), case_id, dataset_id))
    db.commit()
    row = db.execute("SELECT * FROM test_cases WHERE id=?", (case_id,)).fetchone()
    db.close()
    return enrich(row)


@router.delete("/{dataset_id}/cases/{case_id}")
def delete_case(dataset_id: str, case_id: str):
    db = get_db()
    db.execute("DELETE FROM test_cases WHERE id=? AND dataset_id=?", (case_id, dataset_id))
    db.commit()
    db.close()
    return {"ok": True}


@router.post("/{dataset_id}/cases/{case_id}/snapshot")
def build_snapshot(dataset_id: str, case_id: str):
    db = get_db()
    exists = db.execute(
        "SELECT id FROM test_cases WHERE id=? AND dataset_id=?",
        (case_id, dataset_id),
    ).fetchone()
    if not exists:
        db.close()
        raise HTTPException(404, "Test case not found")
    try:
        snapshot = upsert_case_snapshot(db, case_id)
        db.commit()
    except ValueError:
        db.close()
        raise HTTPException(404, "Test case not found")
    db.close()
    return {
        "ok": True,
        "quality_score": snapshot.get("completeness", {}).get("score", 0),
        "status": snapshot.get("completeness", {}).get("status", "missing"),
        "missing": snapshot.get("completeness", {}).get("missing", []),
    }


@router.post("/{dataset_id}/snapshots/backfill")
def backfill_snapshots(dataset_id: str):
    db = get_db()
    rows = db.execute("SELECT id FROM test_cases WHERE dataset_id=?", (dataset_id,)).fetchall()
    if not rows:
        db.close()
        raise HTTPException(404, "No cases found")
    result = {"ready": 0, "partial": 0, "missing": 0, "total": len(rows)}
    for row in rows:
        snapshot = upsert_case_snapshot(db, row["id"])
        status = snapshot.get("completeness", {}).get("status", "missing")
        result[status] = result.get(status, 0) + 1
    db.commit()
    db.close()
    return result
