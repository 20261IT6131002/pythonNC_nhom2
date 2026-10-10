"""Run the documented scripts twice against a fixture-owned real database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_index_and_demo_seed_scripts_are_repeatable(mongo_database):
    database, config = mongo_database
    env = dict(os.environ, NOTEAPP_MONGO_URI=config.mongo_uri, NOTEAPP_DB_NAME=config.db_name)
    for _ in range(2):
        for script, args in (("create_indexes.py", []), ("seed_notes.py", ["--count", "35"])):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / script), *args],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, result.stderr
    assert database.notes.count_documents({}) == 35
    assert database.categories.count_documents({}) == 3
    assert database.categories.find_one({"name_key": "học tập"}) is not None
