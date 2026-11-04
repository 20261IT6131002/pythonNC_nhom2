"""PIN-UI01..06: toolbar, card hit target, async guards, dirty text and failure states."""

import pytest

from tests.ui_process import run_ui_scenario

pytestmark = pytest.mark.ui


def test_pin_toolbar_card_dirty_text_and_failure_flow():
    run_ui_scenario("pin")
