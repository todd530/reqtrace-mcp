"""Business logic for ReqTrace — plain functions over SQLite.

The MCP server in ``server.py`` is a thin wrapper around this module, so
every tool can be unit-tested (and eval-scored) without the MCP transport.

Definitions used consistently across tools, evals, and the README:

- A test's *latest result* is its result with the greatest ``run_date``
  (ties broken by the greatest ``result_id``).
- A requirement is *verified* if at least one linked test has a latest
  result of ``pass``.
- A requirement is *uncovered* if it has no linked test, or none of its
  linked tests has a passing latest result.
- *Coverage %* is verified requirements / total requirements, rounded to
  one decimal place.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import db as dbmod

FAILING_STATUSES = ("fail", "blocked")


def _open(db_path: str | Path) -> sqlite3.Connection:
    return dbmod.connect(db_path, read_only=True)


def _latest_results(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT tr.* FROM test_results tr WHERE tr.result_id = ("
        "  SELECT result_id FROM test_results"
        "  WHERE test_id = tr.test_id"
        "  ORDER BY run_date DESC, result_id DESC LIMIT 1)"
    ).fetchall()
    return {r["test_id"]: r for r in rows}


def _tests_by_req(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    out: dict[str, list[sqlite3.Row]] = {}
    for t in conn.execute("SELECT * FROM test_cases ORDER BY test_id"):
        out.setdefault(t["req_id"], []).append(t)
    return out


def _is_verified(req_id: str, tests_by_req: dict, latest: dict) -> bool:
    return any(
        (r := latest.get(t["test_id"])) is not None and r["status"] == "pass"
        for t in tests_by_req.get(req_id, [])
    )


def _subsystem_matches(req: sqlite3.Row, subsystem: str) -> bool:
    code = req["req_id"].split("-")[1]  # REQ-NAV-001 -> NAV
    return subsystem.lower() in (req["subsystem"].lower(), code.lower())


def list_requirements(db_path, subsystem=None, priority=None) -> list[dict]:
    """List requirements, optionally filtered by subsystem (name or code
    such as ``NAV``) and/or priority (e.g. ``Critical``)."""
    conn = _open(db_path)
    try:
        reqs = [dict(r) for r in conn.execute(
            "SELECT * FROM requirements ORDER BY req_id")]
    finally:
        conn.close()
    if subsystem:
        reqs = [r for r in reqs if _subsystem_matches(r, subsystem)]
    if priority:
        reqs = [r for r in reqs if r["priority"].lower() == priority.lower()]
    return reqs


def get_requirement(db_path, req_id: str) -> dict | None:
    """One requirement plus its linked tests and each test's latest result.
    Returns ``None`` if the requirement does not exist."""
    conn = _open(db_path)
    try:
        row = conn.execute("SELECT * FROM requirements WHERE req_id = ?",
                           (req_id,)).fetchone()
        if row is None:
            return None
        latest = _latest_results(conn)
        tests = []
        for t in conn.execute(
                "SELECT * FROM test_cases WHERE req_id = ? ORDER BY test_id",
                (req_id,)):
            r = latest.get(t["test_id"])
            runs = conn.execute(
                "SELECT COUNT(*) AS n FROM test_results WHERE test_id = ?",
                (t["test_id"],)).fetchone()["n"]
            tests.append({
                "test_id": t["test_id"], "title": t["title"], "type": t["type"],
                "latest_status": r["status"] if r else None,
                "latest_run_date": r["run_date"] if r else None,
                "total_runs": runs,
            })
        out = dict(row)
        out["tests"] = tests
        out["verified"] = any(t["latest_status"] == "pass" for t in tests)
        return out
    finally:
        conn.close()


def search_requirements(db_path, query: str) -> list[dict]:
    """Case-insensitive substring search over requirement id, title, text."""
    q = query.lower()
    return [r for r in list_requirements(db_path)
            if q in r["req_id"].lower() or q in r["title"].lower()
            or q in r["text"].lower()]


def find_uncovered_requirements(db_path) -> list[dict]:
    """Requirements with no linked test, or no passing latest result."""
    conn = _open(db_path)
    try:
        latest = _latest_results(conn)
        tests_by_req = _tests_by_req(conn)
        out = []
        for req in conn.execute("SELECT * FROM requirements ORDER BY req_id"):
            tests = tests_by_req.get(req["req_id"], [])
            if not tests:
                reason = "no linked test"
            elif not _is_verified(req["req_id"], tests_by_req, latest):
                reason = "no passing test result"
            else:
                continue
            d = dict(req)
            d["reason"] = reason
            d["linked_tests"] = [t["test_id"] for t in tests]
            out.append(d)
        return out
    finally:
        conn.close()


def get_failing_tests(db_path) -> list[dict]:
    """Test cases whose latest result is fail or blocked, with the
    requirement each one is linked to."""
    conn = _open(db_path)
    try:
        latest = _latest_results(conn)
        out = []
        for t in conn.execute(
                "SELECT tc.*, r.title AS req_title FROM test_cases tc"
                " JOIN requirements r ON r.req_id = tc.req_id"
                " ORDER BY tc.test_id"):
            r = latest.get(t["test_id"])
            if r is not None and r["status"] in FAILING_STATUSES:
                out.append({
                    "test_id": t["test_id"], "title": t["title"],
                    "req_id": t["req_id"], "requirement_title": t["req_title"],
                    "latest_status": r["status"],
                    "latest_run_date": r["run_date"],
                })
        return out
    finally:
        conn.close()


def get_coverage_summary(db_path) -> dict:
    """Counts and verification coverage, overall and by subsystem."""
    conn = _open(db_path)
    try:
        latest = _latest_results(conn)
        tests_by_req = _tests_by_req(conn)
        reqs = [dict(r) for r in conn.execute(
            "SELECT * FROM requirements ORDER BY req_id")]
        total_tests = conn.execute(
            "SELECT COUNT(*) AS n FROM test_cases").fetchone()["n"]
    finally:
        conn.close()

    def summarise(rows: list[dict]) -> dict:
        total = len(rows)
        verified = sum(1 for r in rows
                       if _is_verified(r["req_id"], tests_by_req, latest))
        return {"total": total, "verified": verified,
                "unverified": total - verified,
                "coverage_pct": round(100.0 * verified / total, 1) if total else 0.0}

    overall = summarise(reqs)
    by_subsystem = {}
    for r in reqs:
        by_subsystem.setdefault(r["subsystem"], []).append(r)
    return {
        "total_requirements": overall["total"],
        "requirements_with_tests": sum(
            1 for r in reqs if tests_by_req.get(r["req_id"])),
        "verified": overall["verified"],
        "unverified": overall["unverified"],
        "coverage_pct": overall["coverage_pct"],
        "total_test_cases": total_tests,
        "failing_or_blocked_tests": len(get_failing_tests(db_path)),
        "by_subsystem": {name: summarise(rows)
                         for name, rows in sorted(by_subsystem.items())},
    }


def generate_qualification_report(db_path) -> str:
    """Markdown qualification report: coverage by subsystem, uncovered and
    failing lists, and an overall status line."""
    summary = get_coverage_summary(db_path)
    uncovered = find_uncovered_requirements(db_path)
    failing = get_failing_tests(db_path)
    status = ("READY FOR QUALIFICATION REVIEW" if not uncovered and not failing
              else "NOT READY — open gaps remain")
    lines = [
        "# Qualification Report — Meadowlark Ground Control Station (fictional)",
        "",
        f"**Overall status: {status}**",
        "",
        f"- Requirements verified: **{summary['verified']} of "
        f"{summary['total_requirements']} ({summary['coverage_pct']}%)**",
        f"- Requirements with at least one linked test: "
        f"{summary['requirements_with_tests']} of {summary['total_requirements']}",
        f"- Test cases: {summary['total_test_cases']} "
        f"({summary['failing_or_blocked_tests']} failing or blocked on latest run)",
        f"- Uncovered requirements: {len(uncovered)}",
        "",
        "## Coverage by subsystem",
        "",
        "| Subsystem | Verified | Total | Coverage |",
        "|---|---|---|---|",
    ]
    for name, s in summary["by_subsystem"].items():
        lines.append(f"| {name} | {s['verified']} | {s['total']} | {s['coverage_pct']}% |")
    lines += ["", "## Uncovered requirements", ""]
    if uncovered:
        for r in uncovered:
            lines.append(f"- `{r['req_id']}` {r['title']} ({r['subsystem']}, "
                         f"{r['priority']}) — {r['reason']}")
    else:
        lines.append("None.")
    lines += ["", "## Failing or blocked tests (latest run)", ""]
    if failing:
        for t in failing:
            lines.append(f"- `{t['test_id']}` {t['title']} — **{t['latest_status']}** "
                         f"on {t['latest_run_date']}, linked to `{t['req_id']}` "
                         f"({t['requirement_title']})")
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)
