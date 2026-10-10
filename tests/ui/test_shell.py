"""Actual Tk smoke in a fresh process; no Mongo dependency."""

import pytest

from tests.ui_process import run_ui_scenario

pytestmark = pytest.mark.ui


def test_three_panes_edit_async_and_close():
    run_ui_scenario("phase1")
