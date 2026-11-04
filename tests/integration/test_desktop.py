"""Real desktop scenarios run in separate Python/Tk processes, including restart."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.conftest import cleanup_draft_key

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


def test_desktop_db_unavailable_preserves_text_and_closes_pending(tmp_path, monkeypatch):
    directory = tmp_path / "owned-offline-drafts"
    monkeypatch.setenv("NOTEAPP_DRAFT_DIR", str(directory))
    try:
        run_scenario("unavailable")
    finally:
        if directory.exists():
            cleanup_draft_key(directory)


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


def test_phase3_category_management_and_image_lifecycle(mongo_database):
    config = mongo_database[1]
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        NOTEAPP_MONGO_URI=config.mongo_uri,
        NOTEAPP_DB_NAME=config.db_name,
    )
    result = subprocess.run(
        [sys.executable, "-m", "tests.phase3_desktop_scenarios", "phase3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SCENARIO PASSED" in result.stdout


def test_phase3_reminder_missed_scan_live_delivery_and_trash(mongo_database):
    config = mongo_database[1]
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        NOTEAPP_MONGO_URI=config.mongo_uri,
        NOTEAPP_DB_NAME=config.db_name,
        NOTEAPP_TIMEZONE="Asia/Ho_Chi_Minh",
        NOTEAPP_REMINDER_POLL_SECONDS="5",
    )
    result = subprocess.run(
        [sys.executable, "-m", "tests.phase3_desktop_scenarios", "phase3b"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SCENARIO PASSED" in result.stdout


def test_r1_pin_persists_and_orders_across_restart(mongo_database):
    config = mongo_database[1]
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        NOTEAPP_MONGO_URI=config.mongo_uri,
        NOTEAPP_DB_NAME=config.db_name,
    )

    for scenario in ("create", "restart"):
        result = subprocess.run(
            [sys.executable, "-m", "tests.r1_desktop_scenarios", scenario],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "SCENARIO PASSED" in result.stdout


def run_recovery_scenario(name, config, directory):
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        NOTEAPP_MONGO_URI=config.mongo_uri,
        NOTEAPP_DB_NAME=config.db_name,
        NOTEAPP_RECOVERY_TEST_DIR=str(directory),
    )
    result = subprocess.run(
        [sys.executable, "-m", "tests.r1_recovery_desktop_scenarios", name],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SCENARIO PASSED" in result.stdout


def test_r1_draft_recovers_after_restart_and_reconnects_without_duplicate(mongo_database, tmp_path):
    directory = tmp_path / "recovery"
    config = mongo_database[1]
    run_recovery_scenario("offline_create", config, directory)
    run_recovery_scenario("recover_reconnect", config, directory)
    run_recovery_scenario("verify_final", config, directory)


def test_r1_draft_ack_loss_reuses_operation_id_after_restart(mongo_database, tmp_path):
    directory = tmp_path / "recovery"
    config = mongo_database[1]
    run_recovery_scenario("ack_loss", config, directory)
    assert mongo_database[0].notes.count_documents({}) == 1
    run_recovery_scenario("recover_retry", config, directory)
    run_recovery_scenario("verify_final", config, directory)


def test_r1_draft_conflict_preserves_local_and_remote_versions(mongo_database, tmp_path):
    directory = tmp_path / "recovery"
    config = mongo_database[1]
    run_recovery_scenario("conflict_create", config, directory)
    run_recovery_scenario("conflict_recover", config, directory)


def test_r1_draft_tamper_and_missing_key_fail_closed(mongo_database, tmp_path):
    directory = tmp_path / "recovery"
    config = mongo_database[1]
    run_recovery_scenario("offline_create", config, directory)
    run_recovery_scenario("missing_key", config, directory)
    (path,) = directory.glob("*.draft")
    wrapper = json.loads(path.read_bytes())
    ciphertext = wrapper["encrypted_envelope"]["ciphertext"]
    wrapper["encrypted_envelope"]["ciphertext"] = (
        "A" if ciphertext[0] != "A" else "B"
    ) + ciphertext[1:]
    path.write_text(json.dumps(wrapper), encoding="utf-8")
    run_recovery_scenario("tampered", config, directory)
