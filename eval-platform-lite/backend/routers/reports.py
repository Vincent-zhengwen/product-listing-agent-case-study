import json
from fastapi import APIRouter, HTTPException
from database import get_db
from report_generator import generate_report_for_run

router = APIRouter()


@router.get("")
def list_reports():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM duty_reports ORDER BY created_at DESC LIMIT 90"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.get("/trend/weekly")
def weekly_trend():
    db = get_db()
    rows = db.execute(
        "SELECT report_date, health_score, pass_rate, quality_score, "
        "fatal_failures, total_cases "
        "FROM duty_reports ORDER BY report_date DESC LIMIT 14"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.get("/{report_id}")
def get_report(report_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM duty_reports WHERE id=?", (report_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404)
    d = dict(row)
    d["report_json"] = json.loads(d["report_json"] or "{}")
    return d


@router.post("/generate/{run_id}")
def generate_report(run_id: str):
    """Manually trigger report generation for a completed run."""
    db = get_db()
    row = db.execute("SELECT * FROM task_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Task run not found")
    if dict(row)["status"] != "completed":
        db.close()
        raise HTTPException(400, "Task run not completed yet")
    db.close()
    report = generate_report_for_run(run_id)
    return report
