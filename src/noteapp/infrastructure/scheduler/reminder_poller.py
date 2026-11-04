"""Bounded poll loop: wake, run the application delivery job, sleep. No business rules."""

import logging
import threading
from collections.abc import Callable
from typing import Any

LOGGER = logging.getLogger("noteapp.reminders")
MAX_BACKOFF_FACTOR = 8


class ReminderPoller:
    """One non-daemon thread; stop() signals it and joins, so shutdown is deterministic.

    `job` receives a should_continue() callable so a long batch can stop early. A failing job is
    logged (no payload) and retried at the next, backed-off interval; the loop never spins.
    """

    def __init__(
        self,
        job: Callable[[Callable[[], bool]], Any],
        interval_seconds: float,
        on_result: Callable[[Any], None] | None = None,
        join_timeout: float = 10.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._job, self._interval, self._on_result = job, interval_seconds, on_result
        self._join_timeout = join_timeout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Start once; False if already running or already stopped."""
        with self._lock:
            if self._thread is not None or self._stop.is_set():
                return False
            self._thread = threading.Thread(target=self._run, name="noteapp-reminders")
            self._thread.start()
            return True

    def _run(self) -> None:
        failures = 0
        # Wait first: startup runs its own missed-reminder scan before starting the poller.
        while not self._stop.wait(self._interval * min(2**failures, MAX_BACKOFF_FACTOR)):
            try:
                result = self._job(lambda: not self._stop.is_set())
                failures = 0
            except Exception:
                failures += 1
                LOGGER.warning("reminder_poll_failed", extra={"stage": "poll"})
                continue
            if self._on_result is not None and not self._stop.is_set():
                try:
                    self._on_result(result)
                except Exception:
                    LOGGER.warning("reminder_poll_result_dropped", extra={"stage": "poll"})

    def stop(self) -> bool:
        """Signal and join. Returns False if the thread outlived the join timeout."""
        self._stop.set()
        with self._lock:
            thread = self._thread
        if thread is None or thread is threading.current_thread():
            return True
        thread.join(self._join_timeout)
        return not thread.is_alive()
