"""FR-12 real desktop and Mongo, executed in two independent processes."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

from noteapp.bootstrap import build_runtime
from noteapp.infrastructure.config import Config
from noteapp.presentation.tk.state.editor_state import EditorPhase
from tests.desktop_scenarios import wait_for

WINDOW = "noteapp.presentation.tk.views.app_window."


def wait_list(app, count=3):
    wait_for(
        app,
        lambda: not app.notes.state.loading and len(app.notes.state.items) == count,
    )


def select_title(app, title):
    row = next(item for item in app.notes.state.items if item.title == title)
    assert app.open_note(row)
    return row


def change_sort(app, label):
    app.sidebar.sort.set(label)
    wait_list(app)


def screenshot(app):
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
        picture = ImageGrab.grab(window=get_parent(app.root.winfo_id()))
    else:
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        picture = ImageGrab.grab(
            bbox=(x, y, x + app.root.winfo_width(), y + app.root.winfo_height())
        )

    picture.save(Path(__file__).resolve().parents[1] / "docs/testing/R1_PIN_DESKTOP.png")
    app.root.withdraw()


def create(app):
    wait_for(app, lambda: app.sidebar._categories_ready and not app.notes.state.loading)

    for title in ("C needle", "B needle", "A needle"):
        app.new_note()
        app.note_editor.title.set(title)
        app.note_editor.priority.set("Thấp" if title.startswith("C") else "Cao")
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)

    wait_list(app)
    select_title(app, "C needle")
    app.note_editor.content.insert("end", "Nội dung đang sửa vẫn được giữ")
    app.root.update()
    app.note_editor.pin_button.invoke()
    wait_for(app, lambda: app.editor.state.is_pinned and not app.pin_presenter.busy)
    assert app.editor.state.phase == EditorPhase.DIRTY
    assert app.note_editor.content.get("1.0", "end-1c") == "Nội dung đang sửa vẫn được giữ"
    app.save()
    wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
    wait_list(app)
    assert app.notes.state.items[0].title == "C needle"

    for label in ("Ưu tiên cao trước", "Danh mục A–Z"):
        change_sort(app, label)
        assert app.notes.state.items[0].title == "C needle"

    app.sidebar.text.set("needle")
    wait_list(app)
    assert app.notes.state.items[0].title == "C needle"
    screenshot(app)


def restart(app):
    wait_list(app)
    row = select_title(app, "C needle")
    assert row.is_pinned and app.editor.state.is_pinned
    assert app.editor.state.content == "Nội dung đang sửa vẫn được giữ"

    change_sort(app, "Ưu tiên cao trước")
    app.pin_selected()
    wait_for(app, lambda: not app.editor.state.is_pinned and not app.pin_presenter.busy)
    wait_list(app)
    assert app.notes.state.items[-1].title == "C needle"

    select_title(app, "A needle")
    app.pin_selected()
    wait_for(app, lambda: app.editor.state.is_pinned and not app.pin_presenter.busy)
    with patch(WINDOW + "confirm_trash", return_value=True):
        app.trash_selected()
    wait_list(app, 2)

    app.switch_mode("trash")
    wait_list(app, 1)
    assert app.notes.state.items[0].is_pinned
    select_title(app, "A needle")
    assert not app.note_editor.pin_button.winfo_manager()
    app.restore_selected()
    wait_for(app, lambda: app.mode == "active" and app._mutation_pending is None)
    wait_list(app)
    assert app.notes.state.items[0].title == "A needle"
    assert app.notes.state.items[0].is_pinned


def main():
    runtime = build_runtime(Config.from_env())
    app = runtime.window
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)

    try:
        {"create": create, "restart": restart}[sys.argv[1]](app)
        assert not errors, errors
    finally:
        runtime.close()

    print("SCENARIO PASSED")


if __name__ == "__main__":
    main()
