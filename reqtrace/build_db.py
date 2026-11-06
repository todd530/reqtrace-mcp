"""Build the ReqTrace SQLite database from the checked-in seed data.

Usage:
    python -m reqtrace.build_db [--seed data/seed.json] [--db reqtrace.db]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import db as dbmod

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=str(PROJECT_ROOT / "data" / "seed.json"))
    parser.add_argument("--db", default=str(PROJECT_ROOT / "reqtrace.db"))
    args = parser.parse_args()
    stats = dbmod.build_from_seed(args.seed, args.db)
    print(f"Built {stats['db_path']}: {stats['requirements']} requirements, "
          f"{stats['test_cases']} test cases, {stats['test_results']} test results")


if __name__ == "__main__":
    main()
