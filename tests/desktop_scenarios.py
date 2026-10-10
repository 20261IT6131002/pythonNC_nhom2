"""QA-owned fresh-process Tk scenarios; synthetic notes only."""

import os
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

from noteapp.bootstrap import build_runtime
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import SystemClock, create_client
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.presentation.tk.state.editor_state import EditorPhase
from scripts.seed_notes import seed_categories


def wait_for(app, condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.01)
    app.root.update()
    assert condition(), "Timed out waiting for desktop operation"


def create_scenario():
    config = Config.from_env()
    with create_client(config) as client:
        seed_categories(MongoCategoryRepository(client[config.db_name]), SystemClock())
    runtime = build_runtime(config)
    app = runtime.window
    app.root.withdraw()
    callbacks = []
    app.root.report_callback_exception = lambda *error: callbacks.append(error)
    try:
        wait_for(app, lambda: "Học tập" in app.note_editor.categories)
        app.note_editor.title.set("Bài tập tiếng Việt")
        app.note_editor.priority.set("Cao")
        app.note_editor.category.set("Học tập")
        app.note_editor.content.insert("1.0", "Nội dung lưu bền vững")
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
        database = runtime.client[config.db_name]
        assert database.notes.count_documents({}) == 1
        saved = MongoNoteRepository(database).find_by_id(app.editor.state.note_id)
        assert saved.priority == Priority.HIGH
        assert saved.category_id is not None
        assert saved.version == 1
        assert not callbacks
    finally:
        runtime.close()


def capture(app):
    if os.environ.get("NOTEAPP_CAPTURE_UI") != "1":
        return
    from PIL import ImageGrab

    app.root.deiconify()
    app.root.lift()
    app.root.update()
    if sys.platform == "win32":
        import ctypes

        get_parent = ctypes.windll.user32.GetParent
        get_parent.argtypes = [ctypes.c_void_p]
        get_parent.restype = ctypes.c_void_p
        # Capture the application's own HWND; desktop DPI coordinates may differ.
        image = ImageGrab.grab(window=get_parent(app.root.winfo_id()))
    else:
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        image = ImageGrab.grab(bbox=(x, y, x + app.root.winfo_width(), y + app.root.winfo_height()))
    image.save(Path(__file__).resolve().parents[1] / "docs/testing/PHASE1_DESKTOP_SMOKE.png")
    app.root.withdraw()


def edit_scenario():
    config = Config.from_env()
    runtime = build_runtime(config)
    app = runtime.window
    app.root.withdraw()
    callbacks = []
    app.root.report_callback_exception = lambda *error: callbacks.append(error)
    try:
        assert app.root.style.master is app.root
        wait_for(app, lambda: len(app.notes.state.items) == 1)
        app.open_note(app.notes.state.items[0])
        note_id = app.editor.state.note_id
        assert app.note_editor.content.get("1.0", "end-1c") == "Nội dung lưu bền vững"
        app.note_editor.content.insert("end", " — đã sửa")
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
        assert app.editor.state.version == 2
        repository = MongoNoteRepository(runtime.client[config.db_name])
        server = repository.find_by_id(note_id)
        assert server.version == 2
        assert server.content.endswith("— đã sửa")
        assert server.updated_at.tzinfo is not None
        assert app.note_editor.metadata.cget("text").startswith("Cập nhật: ")
        wait_for(app, lambda: not app.notes.state.loading)
        capture(app)
        app.note_editor.title.set(" ")
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.ERROR)
        assert app.note_editor.content.get("1.0", "end-1c").endswith("— đã sửa")
        assert repository.find_by_id(note_id).version == 2

        changed = server.edited(
            title="Server",
            content="Other editor",
            priority=Priority.HIGH,
            category_id=None,
            now=server.updated_at,
        )
        assert repository.update_if_version(changed, 2)
        app.note_editor.title.set("My version")
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.CONFLICT)
        assert repository.find_by_id(note_id).content == "Other editor"
        assert app.note_editor.content.get("1.0", "end-1c").endswith("— đã sửa")
        app.notes.refresh()
        wait_for(app, lambda: not app.notes.state.loading)
        with patch("noteapp.presentation.tk.views.app_window.confirm_discard", return_value=True):
            app.open_note(app.notes.state.items[0])
        assert app.editor.state.version == 3
        assert app.editor.state.content == "Other editor"
        assert not callbacks
    finally:
        runtime.close()


def unavailable_scenario():
    runtime = build_runtime(Config("mongodb://127.0.0.1:1", "noteapp_test_ui_unavailable", 100))
    app = runtime.window
    app.root.withdraw()
    callbacks = []
    app.root.report_callback_exception = lambda *error: callbacks.append(error)
    try:
        app.note_editor.title.set("Chưa đồng bộ")
        app.note_editor.content.insert("1.0", "Giữ nguyên nội dung khi mất kết nối")
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.ERROR)
        assert app.editor.state.note_id is None
        assert app.note_editor.content.get("1.0", "end-1c") == "Giữ nguyên nội dung khi mất kết nối"
        assert "LOCAL_DRAFT" not in app.note_editor.status.cget("text")
        assert app.runner.submit("pending-close", "demo", lambda: time.sleep(0.5))
        app.close()
        assert app.pump._after_id is None
    finally:
        runtime.close()
    assert not callbacks, ["".join(traceback.format_exception(*error)) for error in callbacks]


def launcher_scenario():
    import noteapp.main as launcher

    config = Config.from_env()
    opened = []

    def timed_runtime():
        runtime = build_runtime(config)
        runtime.window.root.withdraw()
        runtime.window.root.after(500, runtime.window.close)
        opened.append(runtime)
        return runtime

    with patch.object(launcher, "build_runtime", timed_runtime):
        assert launcher.main() == 0
    assert not opened[0].window.alive


if __name__ == "__main__":
    scenarios = {
        "create": create_scenario,
        "edit": edit_scenario,
        "unavailable": unavailable_scenario,
        "launcher": launcher_scenario,
    }
    scenarios[sys.argv[1]]()
    print("SCENARIO PASSED")
