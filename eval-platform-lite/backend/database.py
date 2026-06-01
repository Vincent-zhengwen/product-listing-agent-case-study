import os
import sqlite3
from pathlib import Path

DB_PATH = Path(
    os.getenv("EVAL_CENTER_DB_PATH", str(Path(__file__).parent / "portfolio_eval_demo.sqlite"))
).expanduser()


def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS datasets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        version TEXT DEFAULT 'v1.0',
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS test_cases (
        id TEXT PRIMARY KEY,
        dataset_id TEXT REFERENCES datasets(id) ON DELETE CASCADE,
        source_url TEXT NOT NULL,
        category TEXT DEFAULT '',
        difficulty TEXT DEFAULT 'medium',
        source_quality TEXT DEFAULT 'medium',
        taobao_ref_url TEXT DEFAULT '',
        douyin_ref_url TEXT DEFAULT '',
        xiaohongshu_ref_url TEXT DEFAULT '',
        tags TEXT DEFAULT '[]',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS task_runs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        dataset_id TEXT REFERENCES datasets(id),
        platform TEXT NOT NULL,
        trigger TEXT DEFAULT 'manual',
        agent_version TEXT DEFAULT 'unknown',
        runs_per_case INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        progress_total INTEGER DEFAULT 0,
        progress_completed INTEGER DEFAULT 0,
        progress_failed INTEGER DEFAULT 0,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS run_results (
        id TEXT PRIMARY KEY,
        task_run_id TEXT REFERENCES task_runs(id) ON DELETE CASCADE,
        test_case_id TEXT REFERENCES test_cases(id),
        platform TEXT NOT NULL,
        attempt_number INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        duration_ms INTEGER DEFAULT 0,
        cost_rmb REAL DEFAULT 0,
        output TEXT DEFAULT 'null',
        trace TEXT DEFAULT 'null',
        agent_error TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS eval_scores (
        id TEXT PRIMARY KEY,
        run_result_id TEXT REFERENCES run_results(id) ON DELETE CASCADE,
        grader_id TEXT NOT NULL,
        grader_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        verdict TEXT,
        score REAL,
        confidence TEXT DEFAULT '',
        reason TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS human_annotations (
        id TEXT PRIMARY KEY,
        run_result_id TEXT REFERENCES run_results(id) ON DELETE CASCADE,
        q1_publishable INTEGER,
        q2_competitor_parity INTEGER,
        q3_would_click INTEGER,
        biggest_issue TEXT DEFAULT '',
        annotated_by TEXT DEFAULT 'user',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS case_ai_analyses (
        id TEXT PRIMARY KEY,
        run_result_id TEXT REFERENCES run_results(id) ON DELETE CASCADE,
        analysis_json TEXT DEFAULT '{}',
        summary TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS failure_codes (
        code TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        category TEXT DEFAULT '',
        severity TEXT DEFAULT 'warning',
        description TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS case_failure_codes (
        id TEXT PRIMARY KEY,
        run_result_id TEXT REFERENCES run_results(id) ON DELETE CASCADE,
        code TEXT REFERENCES failure_codes(code),
        source TEXT DEFAULT 'human',
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(run_result_id, code)
    );

    CREATE TABLE IF NOT EXISTS case_snapshots (
        id TEXT PRIMARY KEY,
        test_case_id TEXT REFERENCES test_cases(id) ON DELETE CASCADE,
        source_url TEXT NOT NULL,
        source_id TEXT DEFAULT '',
        snapshot_version TEXT DEFAULT 'source-package-v1',
        source_title TEXT DEFAULT '',
        attributes_count INTEGER DEFAULT 0,
        images_count INTEGER DEFAULT 0,
        raw_data_available INTEGER DEFAULT 0,
        quality_score INTEGER DEFAULT 0,
        completeness_json TEXT DEFAULT '{}',
        snapshot_json TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(test_case_id)
    );

    CREATE TABLE IF NOT EXISTS duty_reports (
        id TEXT PRIMARY KEY,
        task_run_id TEXT,
        report_date TEXT NOT NULL,
        health_score REAL DEFAULT 0,
        pass_rate REAL DEFAULT 0,
        quality_score REAL DEFAULT 0,
        fatal_failures INTEGER DEFAULT 0,
        warning_failures INTEGER DEFAULT 0,
        total_cases INTEGER DEFAULT 0,
        ai_analysis TEXT DEFAULT '',
        report_json TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    """)

    _ensure_columns(conn, "failure_codes", {
        "stage": "TEXT DEFAULT ''",
        "root_cause": "TEXT DEFAULT ''",
        "suggested_fix": "TEXT DEFAULT ''",
    })

    conn.commit()
    conn.close()


def _ensure_columns(conn, table: str, columns: dict[str, str]):
    existing = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
