"""Tests for the DOORS-shaped CSV importer (adapter pattern).

The key property: a database rebuilt from the flat CSV export produces
the same traceability figures as the seed-built database.
"""
from pathlib import Path

from reqtrace import db as dbmod
from reqtrace import logic
from reqtrace.import_csv import import_csv_rows

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "sample_doors_export.csv"


def test_importer_row_counts():
    reqs, tests, results = import_csv_rows(CSV_PATH)
    assert len(reqs) == 40
    assert len(tests) == 55
    assert len(results) == 55  # one latest result per test in the export


def test_imported_db_matches_seed_figures(seed_db, tmp_path):
    reqs, tests, results = import_csv_rows(CSV_PATH)
    imported = tmp_path / "imported.db"
    dbmod.write_db(imported, reqs, tests, results)

    seed_summary = logic.get_coverage_summary(seed_db)
    imported_summary = logic.get_coverage_summary(imported)
    assert imported_summary == seed_summary
    assert [r["req_id"] for r in logic.find_uncovered_requirements(imported)] == \
           [r["req_id"] for r in logic.find_uncovered_requirements(seed_db)]
    assert [t["test_id"] for t in logic.get_failing_tests(imported)] == \
           [t["test_id"] for t in logic.get_failing_tests(seed_db)]


def test_importer_keeps_unlinked_requirements():
    reqs, tests, _ = import_csv_rows(CSV_PATH)
    ids = {r["req_id"] for r in reqs}
    assert "REQ-NAV-007" in ids  # present in the export with no test link
    assert all(t["req_id"] != "REQ-NAV-007" for t in tests)
