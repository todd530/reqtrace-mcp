"""Importer for a DOORS-shaped CSV export — the adapter-pattern proof.

A typical DOORS module/link export is a flat CSV: one row per
requirement–test link, with the requirement attributes repeated. This
importer consumes exactly that shape (see ``data/sample_doors_export.csv``)
and rebuilds the same vendor-neutral SQLite database the seed builder
produces. A live DOORS, Jira, or Azure DevOps connector would be just
another adapter feeding the same :func:`reqtrace.db.write_db` call.

Note: the CSV carries each test's *latest* result only, so an imported
database has one result row per test; run history is a native-database
enrichment. Coverage, uncovered, and failing figures are identical.

Usage:
    python -m reqtrace.import_csv [--csv data/sample_doors_export.csv]
                                  [--db reqtrace_from_csv.db]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from . import db as dbmod

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMPORT_DATE = "2026-10-15"
IMPORT_ENV = "Imported from CSV export"


def import_csv_rows(csv_path: str | Path):
    """Parse the export into (requirements, test_cases, test_results)."""
    requirements: dict[str, dict] = {}
    test_cases: dict[str, dict] = {}
    test_results: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            req_id = row["Object ID"].strip()
            requirements.setdefault(req_id, {
                "req_id": req_id,
                "title": row["Title"].strip(),
                "text": row["Requirement Text"].strip(),
                "subsystem": row["Subsystem"].strip(),
                "priority": row["Priority"].strip(),
                "verification_method": row["Verification Method"].strip(),
            })
            test_id = (row.get("Linked Test ID") or "").strip()
            if not test_id:
                continue  # requirement with no verification link
            test_cases.setdefault(test_id, {
                "test_id": test_id,
                "req_id": req_id,
                "title": (row.get("Linked Test Title") or "").strip(),
                "type": "Imported",
            })
            status = (row.get("Latest Test Result") or "").strip().lower()
            if status:
                test_results.append({
                    "result_id": len(test_results) + 1,
                    "test_id": test_id,
                    "run_date": IMPORT_DATE,
                    "status": status,
                    "environment": IMPORT_ENV,
                    "notes": "Latest result at time of export.",
                })
    return (list(requirements.values()), list(test_cases.values()), test_results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv",
                        default=str(PROJECT_ROOT / "data" / "sample_doors_export.csv"))
    parser.add_argument("--db", default=str(PROJECT_ROOT / "reqtrace_from_csv.db"))
    args = parser.parse_args()
    reqs, tests, results = import_csv_rows(args.csv)
    stats = dbmod.write_db(args.db, reqs, tests, results)
    print(f"Imported {args.csv} -> {stats['db_path']}: "
          f"{stats['requirements']} requirements, {stats['test_cases']} test cases, "
          f"{stats['test_results']} test results")


if __name__ == "__main__":
    main()
