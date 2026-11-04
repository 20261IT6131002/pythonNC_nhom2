"""P3B-04: real Tk reminder configuration, state display, stale results and live delivery."""

import pytest

from tests.ui_process import run_ui_scenario

pytestmark = pytest.mark.ui


def test_reminder_set_reschedule_cancel_stale_and_delivery_flow():
    run_ui_scenario("reminder")
