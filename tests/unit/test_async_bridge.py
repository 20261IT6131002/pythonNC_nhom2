"""P1-AC11: nonblocking I/O, bounded capacity, main-thread event delivery."""

import ast
import inspect
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident

import pytest

from noteapp.application.dto.operation_result import ErrorCode
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.async_bridge.ui_event_pump import UIEventPump


class FakeRoot:
    def __init__(self):
        self.owner = get_ident()
        self.callbacks = {}
        self.sequence = 0

    def after(self, delay, callback):
        assert get_ident() == self.owner
        self.sequence += 1
        self.callbacks[self.sequence] = callback
        return self.sequence

    def after_cancel(self, request_id):
        assert get_ident() == self.owner
        self.callbacks.pop(request_id, None)

    def tick(self):
        callbacks = list(self.callbacks.values())
        self.callbacks.clear()
        for callback in callbacks:
            callback()


def test_slow_io_does_not_block_and_delivers_only_on_main_thread():
    root, runner = FakeRoot(), TaskRunner(max_workers=1)
    received = []
    pump = UIEventPump(root, runner, lambda event: received.append((get_ident(), event)))
    worker_started, worker_finished = Event(), Event()

    def slow():
        assert get_ident() != root.owner
        worker_started.set()
        time.sleep(0.5)
        worker_finished.set()
        return "done"

    try:
        pump.start()
        start = time.monotonic()
        assert runner.submit("slow", "demo", slow)
        assert time.monotonic() - start < 0.2
        assert worker_started.wait(1)
        for _ in range(10):
            root.tick()  # Tk owner can process input while the worker is busy.
        assert not received
        assert worker_finished.wait(2)
        deadline = time.monotonic() + 2
        while not received and time.monotonic() < deadline:
            root.tick()
            time.sleep(0.005)
        assert received[0][0] == root.owner
        assert received[0][1].result.value == "done"
        pump.close()
        assert not root.callbacks
        assert not any(
            isinstance(node, (ast.Import, ast.ImportFrom)) and "tkinter" in ast.unparse(node)
            for node in ast.walk(ast.parse(inspect.getsource(TaskRunner)))
        )
    finally:
        pump.close()
        runner.close(wait=True)


def test_worker_capacity_remains_bounded_until_results_are_consumed():
    runner = TaskRunner(max_workers=1, max_pending=1)
    done = Event()
    try:
        assert runner.submit("first", "test", lambda: done.set())
        assert done.wait(1)
        assert not runner.submit("second", "test", lambda: None)
        deadline = time.monotonic() + 1
        events = []
        while not events and time.monotonic() < deadline:
            events = runner.drain()
            time.sleep(0.005)
        assert events
        assert runner.submit("second", "test", lambda: None)
    finally:
        runner.close(wait=True)


def test_pump_rejects_worker_calls():
    runner, root = TaskRunner(), FakeRoot()
    pump = UIEventPump(root, runner, lambda event: None)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(RuntimeError, match="owner thread"):
                pool.submit(pump.start).result()
    finally:
        runner.close(wait=True)


def test_worker_errors_are_sanitized_and_closed_runner_rejects_work():
    runner = TaskRunner()

    def fail():
        raise RuntimeError("private URI and note content")

    try:
        runner.submit("error", "test", fail)
        deadline = time.monotonic() + 1
        events = []
        while not events and time.monotonic() < deadline:
            events = runner.drain()
            time.sleep(0.005)
        assert events[0].result.error == ErrorCode.UNEXPECTED
        assert "private" not in repr(events[0])
    finally:
        runner.close(wait=True)
    assert not runner.submit("closed", "test", lambda: None)
