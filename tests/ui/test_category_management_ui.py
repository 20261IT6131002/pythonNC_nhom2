"""P3A-03: real Tk category management without Mongo."""

import pytest

from tests.ui_process import run_ui_scenario

pytestmark = pytest.mark.ui


def test_category_create_rename_duplicate_delete_and_sync():
    run_ui_scenario("category")
