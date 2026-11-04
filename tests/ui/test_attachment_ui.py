"""P3A-08: real Tk image attach/replace/remove with real Pillow and files, no Mongo."""

import pytest

from tests.ui_process import run_ui_scenario

pytestmark = pytest.mark.ui


def test_image_attach_replace_remove_errors_stale_and_dirty_text():
    run_ui_scenario("attachment")
