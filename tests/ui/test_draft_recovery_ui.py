"""REC-UI01..06: real Tk recovery, local status, failure and safe close behavior."""

import pytest

from tests.ui_process import run_ui_scenario

pytestmark = pytest.mark.ui


def test_recovery_offline_conflict_and_safe_autosave_flow():
    run_ui_scenario("recovery")
