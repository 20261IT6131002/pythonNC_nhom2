"""Run native Tcl/Tk assertions without sharing interpreter globals between tests."""

import os
import subprocess
import sys

import pytest


def run_ui_scenario(name):
    result = subprocess.run(
        [sys.executable, "-m", "tests.ui_scenarios", name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
    )
    if (
        result.returncode
        and os.environ.get("NOTEAPP_REQUIRE_UI") != "1"
        and "Skipped:" in result.stderr
    ):
        pytest.skip("Tk smoke requires a working display.")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "UI SCENARIO PASSED" in result.stdout
