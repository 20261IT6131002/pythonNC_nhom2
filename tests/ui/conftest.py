"""Dispose completed Tcl interpreters on the test owner thread before another Tk."""

import gc

import pytest


@pytest.fixture(autouse=True)
def collect_closed_ui_cycles():
    # Window/presenter callbacks form cycles. Collect them before Tk initialization,
    # rather than letting GC finalize an old interpreter midway through a new one.
    gc.collect()
    yield
    gc.collect()
