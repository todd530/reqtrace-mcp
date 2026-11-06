import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from reqtrace import db as dbmod  # noqa: E402


@pytest.fixture()
def seed_db(tmp_path):
    path = tmp_path / "test.db"
    dbmod.build_from_seed(PROJECT_ROOT / "data" / "seed.json", path)
    return path
