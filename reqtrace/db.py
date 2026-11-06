"""SQLite data layer for ReqTrace.

The database is a disposable build artifact: it is rebuilt from checked-in
seed data (``data/seed.json``) or from an imported requirements-tool CSV
export. Nothing here talks to the network or to any proprietary tool.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
DROP TABLE IF EXISTS test_results;
DROP TABLE IF EXISTS test_cases;
DROP TABLE IF EXISTS requirements;
CREATE TABLE requirements (
    req_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    subsystem TEXT NOT NULL,
    priority TEXT NOT NULL,
    verification_method TEXT NOT NULL
);
CREATE TABLE test_cases (
    test_id TEXT PRIMARY KEY,
    req_id TEXT NOT NULL REFERENCES requirements(req_id),
    title TEXT NOT NULL,
    type TEXT NOT NULL
);
CREATE TABLE test_results (
    result_id INTEGER PRIMARY KEY,
    test_id TEXT NOT NULL REFERENCES test_cases(test_id),
    run_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'blocked')),
    environment TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
"""


def connect(db_path: str | Path, read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def write_db(db_path: str | Path, requirements: list[dict],
             test_cases: list[dict], test_results: list[dict]) -> dict:
    """Create a fresh database at ``db_path`` from in-memory records."""
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO requirements VALUES (:req_id, :title, :text, :subsystem,"
            " :priority, :verification_method)", requirements)
        conn.executemany(
            "INSERT INTO test_cases VALUES (:test_id, :req_id, :title, :type)",
            test_cases)
        conn.executemany(
            "INSERT INTO test_results VALUES (:result_id, :test_id, :run_date,"
            " :status, :environment, :notes)", test_results)
        conn.commit()
    finally:
        conn.close()
    return {"db_path": str(db_path), "requirements": len(requirements),
            "test_cases": len(test_cases), "test_results": len(test_results)}


def build_from_seed(seed_path: str | Path, db_path: str | Path) -> dict:
    """Build the database from the checked-in synthetic seed JSON."""
    seed = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    return write_db(db_path, seed["requirements"], seed["test_cases"],
                    seed["test_results"])
