"""Structured operation telemetry restricted to non-content metadata."""

import json
import logging


class OperationFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "event": "operation_completed",
                "correlation_id": getattr(record, "correlation_id", None),
                "stage": getattr(record, "stage", None),
                "duration_ms": getattr(record, "duration_ms", None),
                "error_code": getattr(record, "error_code", None),
            },
            ensure_ascii=True,
        )


def configure_logging() -> None:
    logger = logging.getLogger("noteapp.operations")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(OperationFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
