#!/usr/bin/env python3
"""ReqTrace deterministic eval harness.

Runs every case in ``golden.jsonl`` against the tool layer
(:mod:`reqtrace.logic`) on a fresh database built from the checked-in
seed data, scores exact-match pass/fail, prints a summary, and exits
non-zero if any case fails — so it can gate CI.

The expected answers were defined from the seed data before the tool
layer was scored against them: criteria first, regression-checked on
every run. That is the same discipline as requirements verification,
applied to an AI tool layer.

Usage:  .venv/bin/python evals/run_evals.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from reqtrace import db as dbmod  # noqa: E402
from reqtrace import logic  # noqa: E402

TOOLS = {
    "list_requirements": logic.list_requirements,
    "get_requirement": logic.get_requirement,
    "search_requirements": logic.search_requirements,
    "find_uncovered_requirements": logic.find_uncovered_requirements,
    "get_failing_tests": logic.get_failing_tests,
    "get_coverage_summary": logic.get_coverage_summary,
    "generate_qualification_report": logic.generate_qualification_report,
}


def _normalise(result):
    """Add derived fields the golden cases assert on."""
    if isinstance(result, dict) and "tests" in result:
        result = dict(result)
        result["_test_ids"] = [t["test_id"] for t in result["tests"]]
        result["_latest_statuses"] = [t["latest_status"] for t in result["tests"]]
    return result


def check(expect, actual) -> bool:
    if isinstance(expect, dict):
        if isinstance(actual, str):
            return all(s in actual for s in expect.get("contains", []))
        if isinstance(actual, list):
            if "_count" in expect and len(actual) != expect["_count"]:
                return False
            if "_ids" in expect:
                ids = [i.get("test_id") or i.get("req_id") for i in actual]
                if ids != expect["_ids"]:
                    return False
            if "_field_values" in expect:
                vals = [i.get(expect["_field"]) for i in actual]
                if vals != expect["_field_values"]:
                    return False
            return True
        if isinstance(actual, dict):
            return all(k in actual and check(v, actual[k])
                       for k, v in expect.items())
        return False
    if isinstance(expect, list):
        return expect == actual
    return expect == actual


def main() -> int:
    cases = [json.loads(line) for line in
             (PROJECT_ROOT / "evals" / "golden.jsonl").read_text().splitlines()
             if line.strip()]
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "eval.db"
        dbmod.build_from_seed(PROJECT_ROOT / "data" / "seed.json", db_path)
        passed = 0
        for case in cases:
            fn = TOOLS[case["tool"]]
            result = _normalise(fn(db_path, **case["args"]))
            ok = check(case["expect"], result)
            passed += ok
            print(f"{'PASS' if ok else 'FAIL'}  {case['id']}  "
                  f"{case['tool']}  — {case['question']}")
            if not ok:
                print(f"      expected: {json.dumps(case['expect'])[:300]}")
                print(f"      actual:   {json.dumps(result, default=str)[:300]}")
    total = len(cases)
    print(f"\nEval score: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
