"""P3B-07/09: bounded poll loop, failure containment and deterministic shutdown."""

import threading
import time

import pytest

from noteapp.infrastructure.scheduler.reminder_poller import ReminderPoller


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_runs_the_job_repeatedly_and_reports_each_result():
    results = []
    poller = ReminderPoller(lambda _go: "tick", 0.01, results.append)
    assert poller.start()
    assert wait_until(lambda: len(results) >= 3)
    assert poller.stop() and not poller.running
    assert set(results) == {"tick"}


def test_first_poll_waits_one_interval_so_startup_scan_is_not_duplicated():
    calls = []
    poller = ReminderPoller(lambda _go: calls.append(1), 0.3)
    poller.start()
    time.sleep(0.1)
    assert calls == []
    assert poller.stop()


def test_start_is_single_shot():
    poller = ReminderPoller(lambda _go: None, 0.01)
    assert poller.start() and not poller.start()
    assert poller.stop()
    assert not poller.start()  # a stopped poller is never resurrected


def test_thread_is_not_a_daemon_and_stops_on_request():
    poller = ReminderPoller(lambda _go: None, 0.01)
    poller.start()
    thread = poller._thread
    assert not thread.daemon
    assert poller.stop() and not thread.is_alive()
    assert thread not in threading.enumerate()


def test_stop_before_start_and_repeated_stop_are_safe():
    poller = ReminderPoller(lambda _go: None, 0.01)
    assert poller.stop() and poller.stop()
    assert not poller.start()


def test_job_failure_is_contained_and_polling_continues(caplog):
    outcomes = iter([RuntimeError("secret /etc/passwd"), RuntimeError("again"), "ok", "ok"])
    seen = []

    def job(_go):
        outcome = next(outcomes, "ok")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    poller = ReminderPoller(job, 0.01, seen.append)
    with caplog.at_level("WARNING", logger="noteapp.reminders"):
        poller.start()
        assert wait_until(lambda: len(seen) >= 2, timeout=5)
        assert poller.stop()
    assert "secret" not in caplog.text and "/etc/passwd" not in caplog.text
    assert "reminder_poll_failed" in caplog.text


def test_failures_back_off_instead_of_spinning():
    calls = []

    def job(_go):
        calls.append(time.monotonic())
        raise RuntimeError("down")

    poller = ReminderPoller(job, 0.05)
    poller.start()
    time.sleep(0.8)
    assert poller.stop()
    gaps = [b - a for a, b in zip(calls, calls[1:], strict=False)]
    assert len(calls) <= 6 and gaps == sorted(gaps)  # intervals only grow


def test_a_failing_result_callback_does_not_stop_the_loop():
    calls = []

    def bad_callback(_result):
        calls.append(1)
        raise RuntimeError("ui gone")

    poller = ReminderPoller(lambda _go: 1, 0.01, bad_callback)
    poller.start()
    assert wait_until(lambda: len(calls) >= 3)
    assert poller.stop()


def test_stop_while_a_poll_is_running_waits_for_it_and_hides_its_result():
    entered, release, results = threading.Event(), threading.Event(), []
    flags = []

    def slow(go):
        entered.set()
        release.wait(5)
        flags.append(go())
        return "late"

    poller = ReminderPoller(slow, 0.01, results.append, join_timeout=5)
    poller.start()
    assert entered.wait(3)
    stopper = threading.Thread(target=poller.stop)
    stopper.start()
    time.sleep(0.05)
    assert stopper.is_alive()  # stop() is joining, not abandoning the thread
    release.set()
    stopper.join(5)
    assert not stopper.is_alive() and not poller.running
    assert flags == [False] and results == []  # job saw the stop; late result is dropped


def test_stop_reports_a_stuck_job_without_hanging_forever():
    entered, release = threading.Event(), threading.Event()

    def stuck(_go):
        entered.set()
        release.wait(5)

    poller = ReminderPoller(stuck, 0.01, join_timeout=0.1)
    poller.start()
    assert entered.wait(3)
    assert poller.stop() is False
    release.set()
    assert wait_until(lambda: not poller.running)


def test_interval_must_be_positive():
    with pytest.raises(ValueError):
        ReminderPoller(lambda _go: None, 0)
