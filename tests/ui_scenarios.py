"""Real Tk scenarios in fresh interpreters; assertions shared with pytest wrappers."""

import os
import sys
import time
import tkinter as tk
from dataclasses import replace
from threading import Event, get_ident
from zoneinfo import ZoneInfo

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.trash import TrashNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.ports.note_repository import NotePage
from noteapp.application.queries.list_notes import ListNotes
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.errors import RepositoryUnavailable
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.views.app_window import AppWindow
from tests.fakes import FakeCategories, FakeClock, FakeNotes
from tests.repository_contracts import note


def test_three_panes_edit_async_and_close(monkeypatch):
    notes, categories, clock = FakeNotes(), FakeCategories(), FakeClock()
    runner = TaskRunner(max_workers=1)
    gate = Event()

    def initialize():
        gate.wait(2)
        return ()

    try:
        app = AppWindow(
            CreateNote(notes, categories, clock),
            UpdateNote(notes, categories, clock),
            ListNotes(notes),
            runner,
            initialize,
        )
    except tk.TclError:
        runner.close(wait=True)
        if os.environ.get("NOTEAPP_REQUIRE_UI") == "1":
            pytest.fail("Required Windows Tk display is unavailable.")
        pytest.skip("Tk smoke requires a working display.")
    app.root.withdraw()
    try:
        app.root.update()
        panes = app.root.winfo_children()[0]
        assert len(panes.winfo_children()) == 3
        assert app.sidebar.winfo_width() / panes.winfo_width() == pytest.approx(0.2, abs=0.03)
        assert app.note_list.winfo_width() / panes.winfo_width() == pytest.approx(0.3, abs=0.03)
        assert app.note_editor.winfo_width() / panes.winfo_width() == pytest.approx(0.5, abs=0.03)
        app.note_editor.title.set("Ghi chú tiếng Việt")
        app.note_editor.content.insert("1.0", "Nội dung chưa lưu")
        app.root.update()
        assert app.editor.state.phase == EditorPhase.DIRTY
        assert app.editor.state.content == "Nội dung chưa lưu"
        # The Tk event loop continues while a worker is blocked.
        gate.set()
        app.save()
        deadline = time.monotonic() + 5
        while app.editor.state.phase == EditorPhase.SAVING and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.01)
        assert app.editor.state.phase == EditorPhase.SAVED
        assert len(notes.items) == 1
        app.notes.refresh()
        app.close()
        app.runner.close(wait=True)
        assert not app.alive
        assert app.pump._after_id is None
    finally:
        gate.set()
        app.close()
        runner.close(wait=True)


def drive(app, condition, seconds=3):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.005)
    app.root.update()
    assert condition()


def test_debounce_slow_io_stale_dirty_text_and_close(monkeypatch):
    notes, categories, clock = FakeNotes(), FakeCategories(), FakeClock()
    entered, release = Event(), Event()
    calls, errors, ticks, maintenance_threads = [], [], [], []
    original = note(content="Stored payload")

    class Query:
        def search(self, criteria):
            calls.append(criteria.text)
            if criteria.text == "slow":
                entered.set()
                release.wait(3)
            return NotePage((replace(original, title=criteria.text or "All notes"),), None)

    class FailedTrash:
        def move_to_trash(self, *args):
            raise RepositoryUnavailable("No connection.")

    runner = TaskRunner(max_workers=2)
    try:
        app = AppWindow(
            CreateNote(notes, categories, clock),
            UpdateNote(notes, categories, clock),
            ListNotes(notes),
            runner,
            lambda: (),
            search=SearchNotes(Query(), ZoneInfo("UTC")),
            trash=TrashNote(FailedTrash(), clock),
            maintenance=lambda: maintenance_threads.append(get_ident()),
        )
    except tk.TclError:
        runner.close(wait=True)
        if os.environ.get("NOTEAPP_REQUIRE_UI") == "1":
            pytest.fail("Required Tk display unavailable.")
        pytest.skip("Tk display unavailable.")
    app.root.withdraw()
    app.root.report_callback_exception = lambda *error: errors.append(error)
    try:
        drive(app, lambda: bool(app.notes.state.items) and not app.notes.state.loading)
        assert app._maintenance_id is not None
        app.root.after_cancel(app._maintenance_id)
        app.run_maintenance()
        drive(app, lambda: bool(maintenance_threads))
        assert maintenance_threads[0] != get_ident()
        assert app._maintenance_id is not None
        calls.clear()
        app.note_editor.title.set("Unsaved title")
        app.note_editor.content.insert("1.0", "Keep draft in editor")
        app.root.update()
        for text in ("s", "sl", "slow"):
            app.sidebar.text.set(text)
        assert calls == []
        app.root.after(150, lambda: ticks.append("before debounce"))
        drive(app, lambda: bool(ticks))
        assert calls == []
        drive(app, entered.is_set)
        app.root.after(500, lambda: ticks.append("responsive"))
        drive(app, lambda: "responsive" in ticks)
        assert calls == ["slow"] and app.notes.state.loading
        app.sidebar.text.set("fast")
        drive(app, lambda: not app.notes.state.loading and calls[-1] == "fast")
        assert app.notes.state.items[0].title == "fast"
        release.set()
        drive(app, lambda: not runner._executor._work_queue.qsize())
        # Drain the late result; it must not replace the new generation.
        done = Event()
        app.root.after(100, done.set)
        drive(app, done.is_set)
        assert app.notes.state.items[0].title == "fast"
        assert app.editor.state.content == "Keep draft in editor"
        assert app.editor.state.phase == EditorPhase.DIRTY

        app.sidebar.start.set("2026-02-30")
        assert app.notes.state.error.value == "VALIDATION"
        assert app._debounce_id is None
        assert calls == ["slow", "fast"]
        app.sidebar.clear_filters()
        drive(app, lambda: not app.notes.state.loading and app._debounce_id is None)
        monkeypatch.setattr(
            "noteapp.presentation.tk.views.app_window.confirm_discard", lambda *_: False
        )
        app.note_list._choose(original.id)
        assert app.note_list.selected_id is None
        assert app.editor.state.content == "Keep draft in editor"
        monkeypatch.setattr(
            "noteapp.presentation.tk.views.app_window.confirm_discard", lambda *_: True
        )
        app.note_list._choose(original.id)
        monkeypatch.setattr(
            "noteapp.presentation.tk.views.app_window.confirm_trash", lambda *_: True
        )
        app.trash_selected()
        drive(app, lambda: app._mutation_pending is None)
        assert app.editor.state.phase == EditorPhase.ERROR
        assert app.editor.state.content == "Stored payload"
        assert "chưa hoàn tất" in app.note_editor.status.cget("text")
        app.root.minsize(800, 600)
        app.root.deiconify()
        app.root.geometry("1000x600")
        app.root.update()
        assert app.sidebar.winfo_height() > app.sidebar.container.winfo_height()
        app.sidebar.yview_moveto(1)
        app.root.update()
        assert app.sidebar.reset_button.winfo_ismapped()
        app.sidebar.text.set("pending")
        assert app._debounce_id is not None
    finally:
        release.set()
        app.close()
        runner.close(wait=True)
    assert app._debounce_id is None
    assert app._maintenance_id is None
    assert not errors, errors


if __name__ == "__main__":
    scenarios = {
        "phase1": test_three_panes_edit_async_and_close,
        "phase2": test_debounce_slow_io_stale_dirty_text_and_close,
    }
    with pytest.MonkeyPatch.context() as patches:
        scenarios[sys.argv[1]](patches)
    print("UI SCENARIO PASSED")
