"""P1-AC13: telemetry never serializes note payloads or driver exceptions."""

import logging
import time

from noteapp.infrastructure.telemetry.logging import OperationFormatter
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner


def test_formatter_only_emits_whitelisted_metadata():
    record = logging.LogRecord(
        "noteapp.operations", logging.INFO, "", 0, "secret-password", (), None
    )
    record.content = "private note"
    record.mongo_uri = "mongodb://secret"
    record.correlation_id = "request-1"
    record.stage = "save"
    formatted = OperationFormatter().format(record)
    assert "request-1" in formatted
    assert "save" in formatted
    assert "secret" not in formatted
    assert "private" not in formatted


def test_worker_telemetry_does_not_log_result_content(caplog):
    caplog.set_level(logging.INFO, logger="noteapp.operations")
    logger = logging.getLogger("noteapp.operations")
    logger.addHandler(caplog.handler)
    runner = TaskRunner()
    try:
        runner.submit("safe-id", "save", lambda: "private note")
        deadline = time.monotonic() + 2
        while not caplog.records and time.monotonic() < deadline:
            time.sleep(0.01)
        assert caplog.records
        record = caplog.records[-1]
        assert record.correlation_id == "safe-id"
        assert record.duration_ms >= 0
        assert "private" not in repr(record.__dict__)
    finally:
        runner.close(wait=True)
        logger.removeHandler(caplog.handler)
