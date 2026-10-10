"""Bounded worker executor. No Tk/widget references or worker UI calls."""

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from queue import Empty, Queue
from threading import BoundedSemaphore, Lock
from time import monotonic

from noteapp.application.dto.operation_result import OperationResult


@dataclass(frozen=True)
class TaskEvent:
    request_id: str
    operation: str
    result: OperationResult


class TaskRunner:
    def __init__(self, max_workers: int = 4, max_pending: int = 16) -> None:
        self.events: Queue[TaskEvent] = Queue(maxsize=max_pending)
        self._slots = BoundedSemaphore(max_pending)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="noteapp")
        self._lock = Lock()
        self._closed = False

    def submit(self, request_id: str, operation: str, task: Callable) -> bool:
        started = monotonic()
        with self._lock:
            if self._closed or not self._slots.acquire(blocking=False):
                return False
            try:
                future = self._executor.submit(task)
            except RuntimeError:
                self._slots.release()
                return False
        future.add_done_callback(lambda done: self._completed(request_id, operation, started, done))
        return True

    def _completed(self, request_id: str, operation: str, started: float, future: Future) -> None:
        try:
            result = OperationResult(value=future.result())
        except Exception as error:
            result = OperationResult.failed(error)
        logging.getLogger("noteapp.operations").info(
            "operation_completed",
            extra={
                "correlation_id": request_id,
                "stage": operation,
                "duration_ms": round((monotonic() - started) * 1000, 2),
                "error_code": result.error.value if result.error else None,
            },
        )
        with self._lock:
            if self._closed:
                self._slots.release()
                return
            self.events.put_nowait(TaskEvent(request_id, operation, result))

    def drain(self, limit: int = 32) -> list[TaskEvent]:
        events = []
        for _ in range(limit):
            try:
                event = self.events.get_nowait()
            except Empty:
                break
            self._slots.release()
            events.append(event)
        return events

    def close(self, wait: bool = False) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=True)
        self.drain()
