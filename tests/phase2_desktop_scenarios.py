"""Fresh-process real Tk/Mongo Phase2 flow, confirmation and dirty-state guards."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

from noteapp.bootstrap import build_runtime
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import SystemClock, create_client
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository
from noteapp.presentation.tk.state.editor_state import EditorPhase
from scripts.seed_notes import seed_categories
from tests.desktop_scenarios import wait_for


def ready(app):
    wait_for(app, lambda: "Học tập" in app.note_editor.categories and not app.notes.state.loading)


def create_scenario():
    config = Config.from_env()
    with create_client(config) as client:
        seed_categories(MongoCategoryRepository(client[config.db_name]), SystemClock())
    runtime = build_runtime(config)
    app = runtime.window
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)
    try:
        ready(app)
        for title, category, priority, content in (
            (
                "Kế hoạch học tập",
                "Học tập",
                "Cao",
                "Mục tiêu tuần này\nÔn tập Python\nHoàn thành bài tập\nGhi lại ý tưởng và tiến độ.",
            ),
            ("Công việc cần làm", "Công việc", "Thấp", "Sắp xếp lịch họp và nhiệm vụ."),
        ):
            app.new_note()
            app.note_editor.title.set(title)
            app.note_editor.category.set(category)
            app.note_editor.priority.set(priority)
            app.note_editor.content.insert("1.0", content)
            app.root.update()
            app.save()
            wait_for(
                app,
                lambda: app.editor.state.phase == EditorPhase.SAVED and not app.notes.state.loading,
            )
        app.sidebar.text.set("hoc")
        app.sidebar.category.set("Học tập")
        app.sidebar.priority.set("Cao")
        app.sidebar.sort.set("Danh mục A–Z")
        wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
        target = app.notes.state.items[0]
        app.note_list._choose(target.note_id)
        with patch("noteapp.presentation.tk.views.app_window.confirm_trash", return_value=True):
            app.trash_selected()
        wait_for(
            app,
            lambda: (
                app._mutation_pending is None
                and not app.notes.state.loading
                and not app.notes.state.items
            ),
        )
        app.switch_mode("trash")
        wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
        app.note_list._choose(target.note_id)
        assert app.note_editor.content.cget("state") == "disabled"
        with patch("noteapp.presentation.tk.views.app_window.confirm_purge", return_value=False):
            app.purge_selected()
        assert app._mutation_pending is None
        assert runtime.client[config.db_name].notes.count_documents({"is_deleted": True}) == 1
        assert app.icons and all(icon.width() == 24 for icon in app.icons.values())
        assert not errors
    finally:
        runtime.close()


def capture(app):
    target = os.environ.get("NOTEAPP_PHASE2_CAPTURE")
    if not target:
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
        shot = ImageGrab.grab(window=get_parent(app.root.winfo_id()))
    else:
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        shot = ImageGrab.grab(bbox=(x, y, x + app.root.winfo_width(), y + app.root.winfo_height()))
    shot.save(Path(target))
    app.root.withdraw()


def restart_scenario():
    runtime = build_runtime(Config.from_env())
    app = runtime.window
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)
    try:
        ready(app)
        app.switch_mode("trash")
        wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
        item = app.notes.state.items[0]
        app.note_list._choose(item.note_id)
        assert item.version == 2
        app.restore_selected()
        wait_for(
            app,
            lambda: (
                app._mutation_pending is None
                and app.mode == "active"
                and not app.notes.state.loading
            ),
        )
        assert app.editor.state.note_id == item.note_id and app.editor.state.version == 3
        assert app.note_editor.content.cget("state") == "normal"
        wait_for(app, lambda: app._debounce_id is None and not app.notes.state.loading)
        capture(app)
        app.note_editor.content.insert("end", "\nChưa lưu")
        app.root.update()
        with patch("noteapp.presentation.tk.views.app_window.confirm_discard", return_value=False):
            assert not app.switch_mode("trash")
        assert app.editor.state.content.endswith("Chưa lưu")
        with (
            patch("noteapp.presentation.tk.views.app_window.confirm_discard", return_value=True),
            patch("noteapp.presentation.tk.views.app_window.confirm_trash", return_value=True),
        ):
            app.trash_selected()
        wait_for(app, lambda: app._mutation_pending is None)
        app.switch_mode("trash")
        wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
        app.note_list._choose(item.note_id)
        with patch("noteapp.presentation.tk.views.app_window.confirm_purge", return_value=True):
            app.purge_selected()
        wait_for(
            app,
            lambda: (
                app._mutation_pending is None
                and not app.notes.state.loading
                and not app.notes.state.items
            ),
        )
        assert (
            runtime.client[Config.from_env().db_name].notes.count_documents({"title": item.title})
            == 0
        )
        app.switch_mode("active")
        app.sidebar.text.set("pending debounce")
        assert app._debounce_id is not None
        app.close()
        assert app._debounce_id is None
        assert not errors
    finally:
        runtime.close()


if __name__ == "__main__":
    {"create": create_scenario, "restart": restart_scenario}[sys.argv[1]]()
    print("SCENARIO PASSED")
