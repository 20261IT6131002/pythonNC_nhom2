"""Actual Tk smoke; no fake root and no Mongo dependency."""

import time
import tkinter as tk
from threading import Event

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.queries.list_notes import ListNotes
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.views.app_window import AppWindow
from tests.fakes import FakeCategories, FakeClock, FakeNotes

pytestmark = pytest.mark.ui


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
        pytest.skip("Tk smoke requires a working display.")
    app.root.withdraw()
    try:
        app.root.update()
        assert len(app.root.winfo_children()[0].panes()) == 3
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
