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
from noteapp.domain.errors import AttachmentStoreFailure, RepositoryUnavailable
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


def test_category_management_flow(monkeypatch):
    from noteapp.application.commands.category import (
        CategoryTools,
        CreateCategory,
        DeleteCategory,
        RenameCategory,
        UpdateCategoryColor,
    )
    from noteapp.application.queries.list_notes import ListCategories

    ui_thread = get_ident()
    worker_threads = []
    notes = FakeNotes()

    class RecordingCategories(FakeCategories):
        def create(self, category):
            worker_threads.append(get_ident())
            return super().create(category)

    categories, clock = RecordingCategories(notes), FakeClock()
    tools = CategoryTools(
        CreateCategory(categories, clock),
        RenameCategory(categories),
        UpdateCategoryColor(categories),
        DeleteCategory(categories),
        ListCategories(categories),
    )
    runner, errors = TaskRunner(max_workers=2), []
    try:
        app = AppWindow(
            CreateNote(notes, categories, clock),
            UpdateNote(notes, categories, clock),
            ListNotes(notes),
            runner,
            lambda: ListCategories(categories).execute(),
            categories=tools,
        )
    except tk.TclError:
        runner.close(wait=True)
        if os.environ.get("NOTEAPP_REQUIRE_UI") == "1":
            pytest.fail("Required Tk display unavailable.")
        pytest.skip("Tk display unavailable.")
    app.root.withdraw()
    app.root.report_callback_exception = lambda *error: errors.append(error)
    module = "noteapp.presentation.tk.views.app_window."
    answer = {}
    monkeypatch.setattr(module + "ask_category_name", lambda *_: answer["name"])
    monkeypatch.setattr(module + "ask_category_color", lambda *_: answer["color"])
    monkeypatch.setattr(module + "confirm_delete_category", lambda *_: True)

    def settled():
        return not app.category_presenter.busy

    def names():
        return list(
            app.category_dialog.tree.item(i, "text")
            for i in app.category_dialog.tree.get_children()
        )

    try:
        drive(app, lambda: str(app.sidebar.manage_button.cget("state")) == "normal")
        app.open_category_manager()
        assert app.category_dialog is not None
        answer["name"] = "Học"
        app.add_category()
        drive(app, lambda: settled() and names() == ["Học"])
        assert worker_threads and worker_threads[0] != ui_thread
        assert "Học" in app.note_editor.categories and "Học" in app.sidebar.categories

        answer["name"] = " học "
        app.add_category()
        drive(app, settled)
        assert "đã tồn tại" in app.category_dialog.message.cget("text")
        assert names() == ["Học"]

        category = app.category_view[0]
        app.note_editor.title.set("Dùng danh mục")
        app.note_editor.category.set("Học")
        app.sidebar.category.set("Học")
        app.root.update()
        app.save()
        drive(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
        assert app.editor.state.category_id == category.category_id

        answer["name"] = "Học tập"
        app.rename_category(category)
        drive(app, lambda: settled() and names() == ["Học tập"])
        assert app.note_editor.category.get() == "Học tập"
        assert app.sidebar.category.get() == "Học tập"
        assert app.editor.state.category_id == category.category_id
        assert app.editor.state.phase == EditorPhase.SAVED

        answer["color"] = "#112233"
        app.recolor_category(app.category_view[0])
        drive(app, lambda: settled() and app.category_view[0].color_hex == "#112233")

        app.delete_category(app.category_view[0])
        drive(app, settled)
        assert "đang được ghi chú sử dụng" in app.category_dialog.message.cget("text")
        assert names() == ["Học tập"]

        answer["name"] = "Tạm"
        app.add_category()
        drive(app, lambda: settled() and len(names()) == 2)
        temporary = next(item for item in app.category_view if item.name == "Tạm")
        app.delete_category(temporary)
        drive(app, lambda: settled() and names() == ["Học tập"])
        assert "Tạm" not in app.note_editor.categories and "Tạm" not in app.sidebar.categories
    finally:
        app.close()
        runner.close(wait=True)
    assert app.category_dialog is None
    assert not errors, errors


def test_attachment_flow(monkeypatch):
    import shutil
    import tempfile
    from io import BytesIO
    from pathlib import Path

    from PIL import Image

    from noteapp.application.dto.note_view import NoteView
    from noteapp.application.services.attachment_service import AttachmentService
    from noteapp.infrastructure.attachment.file_reader import LocalImageFileReader
    from noteapp.infrastructure.attachment.image_validator import PillowImageProcessor
    from tests.attachment_fakes import FakeAttachmentStore
    from tests.fakes import FakeNotesWithAttachments

    ui_thread, put_threads, gate = get_ident(), [], Event()
    folder = Path(tempfile.mkdtemp(prefix="noteapp_ui_"))

    def write(name, size=(800, 600), color=(20, 140, 90), fmt="PNG"):
        out = BytesIO()
        Image.new("RGB", size, color).save(out, format=fmt)
        (folder / name).write_bytes(out.getvalue())
        return str(folder / name)

    class RecordingStore(FakeAttachmentStore):
        def put(self, *args):
            put_threads.append(get_ident())
            return super().put(*args)

        def get(self, ref):
            if gate_enabled:
                gate.wait(3)
            return super().get(ref)

    gate_enabled = False
    notes, categories, clock = FakeNotesWithAttachments(), FakeCategories(), FakeClock()
    store = RecordingStore()
    service = AttachmentService(
        notes, notes, store, PillowImageProcessor(), clock, LocalImageFileReader()
    )
    runner, errors = TaskRunner(max_workers=3), []
    try:
        app = AppWindow(
            CreateNote(notes, categories, clock),
            UpdateNote(notes, categories, clock),
            ListNotes(notes),
            runner,
            lambda: (),
            attachments=service,
        )
    except tk.TclError:
        runner.close(wait=True)
        if os.environ.get("NOTEAPP_REQUIRE_UI") == "1":
            pytest.fail("Required Tk display unavailable.")
        pytest.skip("Tk display unavailable.")
    app.root.withdraw()
    app.root.report_callback_exception = lambda *error: errors.append(error)
    module = "noteapp.presentation.tk.views.app_window."
    chosen = {}
    monkeypatch.setattr(module + "ask_image_file", lambda *_: chosen["path"])
    monkeypatch.setattr(module + "confirm_remove_image", lambda *_: True)
    editor, view = app.editor, app.note_editor

    def idle():
        return (
            not app.attachment_presenter.busy and app.attachment_presenter.loading_note_id is None
        )

    try:
        drive(app, lambda: app.sidebar._categories_ready)  # startup finished
        drive(app, lambda: not app.notes.state.loading)
        assert str(view.choose_image_button.cget("state")) == "disabled"
        assert "Lưu ghi chú trước" in view.image_info.cget("text")
        view.title.set("Ghi chú có ảnh")
        view.content.insert("1.0", "nội dung")
        app.root.update()
        app.save()
        drive(app, lambda: editor.state.phase == EditorPhase.SAVED)
        assert str(view.choose_image_button.cget("state")) == "normal"
        assert str(view.remove_image_button.cget("state")) == "disabled"

        chosen["path"] = write("big.png", (800, 600))
        app.choose_image()
        drive(
            app, lambda: editor.state.attachment is not None and view._photo is not None and idle()
        )
        assert put_threads and put_threads[0] != ui_thread
        assert editor.state.version == 2 and editor.state.phase == EditorPhase.SAVED
        assert (view._photo.width(), view._photo.height()) == (200, 150)  # 400x300 thumb / 2
        assert "big.png" in view.image_info.cget("text")
        assert str(view.choose_image_button.cget("text")) == "Thay ảnh…"
        assert str(view.remove_image_button.cget("state")) == "normal"

        # Rejected inputs leave the saved image and preview alone.
        (folder / "note.txt").write_text("not an image")
        for name, expected in (("note.txt", "PNG, JPEG"), ("corrupt.png", "hỏng")):
            if name == "corrupt.png":
                (folder / name).write_bytes((folder / "big.png").read_bytes()[:200])
            chosen["path"] = str(folder / name)
            app.choose_image()
            drive(app, lambda: not app.attachment_presenter.busy)
            drive(app, lambda expected=expected: expected in view.image_info.cget("text"))
            assert editor.state.version == 2 and view._photo is not None
            assert editor.state.attachment.display_name == "big.png"
        assert len(store.blobs) == 1

        # Storage failure keeps the old image and does not claim anything was saved.
        store.fail_put = AttachmentStoreFailure("down")
        chosen["path"] = write("other.jpg", (300, 300), (200, 10, 10), "JPEG")
        app.choose_image()
        drive(app, lambda: not app.attachment_presenter.busy)
        drive(app, lambda: "Ảnh cũ" in view.image_info.cget("text"))
        store.fail_put = None
        assert editor.state.version == 2 and editor.state.attachment.display_name == "big.png"

        # Dirty text survives an image change and then saves without a version conflict.
        view.title.set("Tiêu đề sửa khi đang có ảnh")
        app.root.update()
        assert editor.state.phase == EditorPhase.DIRTY
        app.choose_image()
        drive(app, lambda: editor.state.attachment.display_name == "other.jpg" and idle())
        assert editor.state.phase == EditorPhase.DIRTY and editor.state.version == 3
        assert editor.state.title == "Tiêu đề sửa khi đang có ảnh"
        app.save()
        drive(app, lambda: editor.state.phase == EditorPhase.SAVED)
        assert editor.state.version == 4 and len(store.blobs) == 1
        stored = notes.find_by_id(editor.state.note_id)
        assert stored.attachment.display_name == "other.jpg" and stored.title.endswith("ảnh")

        # A thumbnail that arrives after switching notes is discarded.
        first_id = editor.state.note_id
        saved_view = NoteView.from_note(notes.find_by_id(first_id))
        editor.new()
        gate_enabled = True
        gate.clear()
        editor.open(saved_view)
        drive(app, lambda: app.attachment_presenter.loading_note_id == first_id)
        editor.new()  # leave the note while the worker is still reading the image
        assert app.attachment_presenter.loading_note_id is None
        gate.set()
        done = Event()
        app.root.after(200, done.set)
        drive(app, done.is_set)
        assert editor.state.note_id is None and view._photo is None
        gate_enabled = False

        # Remove clears the preview and releases the payload.
        editor.open(saved_view)
        drive(app, lambda: view._photo is not None and idle())
        app.remove_image()
        drive(app, lambda: editor.state.attachment is None and idle())
        assert view._photo is None and store.blobs == {}
        assert "Chưa có ảnh" in view.image_info.cget("text")
    finally:
        app.close()
        runner.close(wait=True)
        shutil.rmtree(folder, ignore_errors=True)
    assert not errors, errors


if __name__ == "__main__":
    scenarios = {
        "phase1": test_three_panes_edit_async_and_close,
        "phase2": test_debounce_slow_io_stale_dirty_text_and_close,
        "category": test_category_management_flow,
        "attachment": test_attachment_flow,
    }
    with pytest.MonkeyPatch.context() as patches:
        scenarios[sys.argv[1]](patches)
    print("UI SCENARIO PASSED")
