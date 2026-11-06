"""Tests for the ReqTrace tool/business-logic layer (no MCP transport)."""
from reqtrace import logic


def test_coverage_summary_headline_figures(seed_db):
    s = logic.get_coverage_summary(seed_db)
    assert s["total_requirements"] == 40
    assert s["requirements_with_tests"] == 36
    assert s["verified"] == 33
    assert s["unverified"] == 7
    assert s["coverage_pct"] == 82.5
    assert s["total_test_cases"] == 55
    assert s["failing_or_blocked_tests"] == 6


def test_coverage_by_subsystem(seed_db):
    by = logic.get_coverage_summary(seed_db)["by_subsystem"]
    assert by["Mission Data & Logging"] == {
        "total": 6, "verified": 4, "unverified": 2, "coverage_pct": 66.7}
    assert by["Power Management"]["coverage_pct"] == 83.3
    assert sum(v["total"] for v in by.values()) == 40


def test_list_requirements_filters(seed_db):
    assert len(logic.list_requirements(seed_db)) == 40
    nav = logic.list_requirements(seed_db, subsystem="NAV")
    assert [r["req_id"] for r in nav] == [f"REQ-NAV-{i:03d}" for i in range(1, 8)]
    # full subsystem name works as well as the code
    assert logic.list_requirements(seed_db, subsystem="Navigation & Geofencing") == nav
    crit = logic.list_requirements(seed_db, priority="Critical")
    assert len(crit) == 11
    combo = logic.list_requirements(seed_db, subsystem="PWR", priority="High")
    assert [r["req_id"] for r in combo] == ["REQ-PWR-001", "REQ-PWR-006"]


def test_get_requirement_with_history(seed_db):
    req = logic.get_requirement(seed_db, "REQ-COM-002")
    assert req["verified"] is True
    tc3 = next(t for t in req["tests"] if t["test_id"] == "TC-003")
    # TC-003 failed an earlier run, then passed: latest result must win.
    assert tc3["total_runs"] == 2
    assert tc3["latest_status"] == "pass"


def test_get_requirement_unknown_returns_none(seed_db):
    assert logic.get_requirement(seed_db, "REQ-XXX-999") is None


def test_get_requirement_without_tests(seed_db):
    req = logic.get_requirement(seed_db, "REQ-NAV-007")
    assert req["tests"] == []
    assert req["verified"] is False


def test_search_requirements(seed_db):
    hits = logic.search_requirements(seed_db, "geofence")
    assert [r["req_id"] for r in hits] == ["REQ-NAV-001", "REQ-SAF-005"]
    # case-insensitive
    assert logic.search_requirements(seed_db, "GEOFENCE") == hits
    assert logic.search_requirements(seed_db, "warp drive") == []


def test_find_uncovered_requirements(seed_db):
    uncovered = logic.find_uncovered_requirements(seed_db)
    assert [r["req_id"] for r in uncovered] == [
        "REQ-COM-006", "REQ-DAT-004", "REQ-DAT-006", "REQ-NAV-007",
        "REQ-PWR-005", "REQ-SAF-005", "REQ-UI-005"]
    reasons = {r["req_id"]: r["reason"] for r in uncovered}
    assert reasons["REQ-NAV-007"] == "no linked test"
    assert reasons["REQ-COM-006"] == "no passing test result"


def test_get_failing_tests(seed_db):
    failing = logic.get_failing_tests(seed_db)
    assert [t["test_id"] for t in failing] == [
        "TC-009", "TC-010", "TC-035", "TC-036", "TC-054", "TC-055"]
    assert [t["latest_status"] for t in failing] == [
        "fail", "blocked", "fail", "fail", "blocked", "fail"]
    assert failing[0]["req_id"] == "REQ-COM-006"


def test_qualification_report(seed_db):
    report = logic.generate_qualification_report(seed_db)
    assert "33 of 40 (82.5%)" in report
    assert "NOT READY" in report
    assert "REQ-DAT-004" in report  # uncovered list
    assert "TC-054" in report      # failing list
    assert "| Mission Data & Logging | 4 | 6 | 66.7% |" in report
