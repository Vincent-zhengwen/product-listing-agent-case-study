"""
APScheduler — daily automated eval runs at 02:00 Asia/Shanghai.
"""
import os, uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _run_daily_eval():
    from database import get_db
    from routers.task_runs import dispatch_all
    import asyncio

    db = get_db()
    # find all active datasets
    datasets = db.execute(
        "SELECT id FROM datasets WHERE status='active'"
    ).fetchall()

    for ds in datasets:
        cases = db.execute(
            "SELECT * FROM test_cases WHERE dataset_id=?", (ds["id"],)
        ).fetchall()
        if not cases:
            continue

        run_id = str(uuid.uuid4())
        platforms = ["taobao", "douyin", "xiaohongshu"]
        total = len(cases) * len(platforms)

        db.execute(
            "INSERT INTO task_runs (id, name, dataset_id, platform, trigger, "
            "agent_version, status, progress_total, started_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, f"每日自动评测 {datetime.now().strftime('%Y-%m-%d')}",
             ds["id"], "all", "auto_daily", "auto",
             "running", total, datetime.now().isoformat())
        )

        result_ids = {}
        for case in cases:
            for plat in platforms:
                rid = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO run_results (id, task_run_id, test_case_id, "
                    "platform, status) VALUES (?,?,?,?,?)",
                    (rid, run_id, case["id"], plat, "pending")
                )
                result_ids[(case["id"], plat, 1)] = rid

        db.commit()

        # run async dispatch in a new event loop
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                dispatch_all(run_id, cases, platforms, 1, result_ids)
            )
            loop.close()
        except Exception as e:
            db.execute(
                "UPDATE task_runs SET status='failed' WHERE id=?", (run_id,)
            )
            db.commit()

    db.close()


def start_scheduler():
    hour = int(os.getenv("DAILY_REPORT_HOUR", "2"))
    minute = int(os.getenv("DAILY_REPORT_MINUTE", "0"))
    _scheduler.add_job(
        _run_daily_eval,
        CronTrigger(hour=hour, minute=minute),
        id="daily_eval",
        replace_existing=True,
    )
    _scheduler.start()


def stop_scheduler():
    _scheduler.shutdown(wait=False)
