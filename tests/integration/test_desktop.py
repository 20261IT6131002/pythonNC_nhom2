"""Real desktop scenarios run in separate Python/Tk processes, including restart."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.ui,
    pytest.mark.skipif(
        sys.platform != "win32"
        and not os.environ.get("DISPLAY")
        and os.environ.get("NOTEAPP_REQUIRE_UI") != "1",
        reason="Desktop Mongo E2E needs a display; headless CI runs Mongo tests.",
    ),
]
ROOT = Path(__file__).resolve().parents[2]


def run_scenario(scenario, config=None):
    env = dict(os.environ, PYTHONUTF8="1")
    if config is not None:
        env.update(NOTEAPP_MONGO_URI=config.mongo_uri, NOTEAPP_DB_NAME=config.db_name)
    result = subprocess.run(
        [sys.executable, "-m", "tests.desktop_scenarios", scenario],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SCENARIO PASSED" in result.stdout


def test_desktop_create_restart_edit_conflict(mongo_database):
    config = mongo_database[1]
    run_scenario("create", config)
    assert mongo_database[0].notes.count_documents({}) == 1
    run_scenario("edit", config)


def test_desktop_db_unavailable_preserves_text_and_closes_pending():
    run_scenario("unavailable")


def test_real_launcher_mainloop_and_shutdown(mongo_database):
    run_scenario("launcher", mongo_database[1])


def test_phase2_search_trash_restart_restore_and_confirmed_purge(mongo_database):
    config = mongo_database[1]
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        NOTEAPP_MONGO_URI=config.mongo_uri,
        NOTEAPP_DB_NAME=config.db_name,
        NOTEAPP_ENABLE_RETENTION="1",
    )
    for scenario in ("create", "restart"):
        result = subprocess.run(
            [sys.executable, "-m", "tests.phase2_desktop_scenarios", scenario],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "SCENARIO PASSED" in result.stdout
