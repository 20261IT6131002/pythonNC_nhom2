"""Fresh-process real Tk + real Mongo: category management and image lifecycle end to end."""

import shutil
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from noteapp.bootstrap import build_runtime
from noteapp.infrastructure.config import Config
from noteapp.presentation.tk.state.editor_state import EditorPhase
from tests.desktop_scenarios import wait_for

WINDOW = "noteapp.presentation.tk.views.app_window."


def scenario():
    config = Config.from_env()
    folder = Path(tempfile.mkdtemp(prefix="noteapp_p3_"))
    image_path = folder / "ảnh thử.png"
    out = BytesIO()
    Image.new("RGB", (900, 450), (30, 90, 200)).save(out, format="PNG")
    image_path.write_bytes(out.getvalue())
    runtime = build_runtime(config)
    app = runtime.window
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)
    database = runtime.client[config.db_name]
    editor, view = app.editor, app.note_editor
    try:
        wait_for(app, lambda: str(app.sidebar.manage_button.cget("state")) == "normal")
        wait_for(app, lambda: not app.notes.state.loading)
        # Category management through the real adapters.
        app.open_category_manager()
        with patch(WINDOW + "ask_category_name", return_value="Dự án"):
            app.add_category()
        wait_for(app, lambda: "Dự án" in view.categories and not app.category_presenter.busy)
        with patch(WINDOW + "ask_category_name", return_value=" DỰ ÁN "):
            app.add_category()
        wait_for(app, lambda: not app.category_presenter.busy)
        assert "đã tồn tại" in app.category_dialog.message.cget("text")
        assert database.categories.count_documents({}) == 1

        view.title.set("Ghi chú có ảnh và danh mục")
        view.category.set("Dự án")
        app.root.update()
        app.save()
        wait_for(app, lambda: editor.state.phase == EditorPhase.SAVED)
        category_id = editor.state.category_id
        assert category_id is not None
        category = app.category_view[0]
        with patch(WINDOW + "confirm_delete_category", return_value=True):
            app.delete_category(category)
        wait_for(app, lambda: not app.category_presenter.busy)
        assert "đang được ghi chú sử dụng" in app.category_dialog.message.cget("text")
        assert database.categories.count_documents({}) == 1

        with patch(WINDOW + "ask_category_name", return_value="Dự án mới"):
            app.rename_category(category)
        wait_for(app, lambda: "Dự án mới" in view.categories and not app.category_presenter.busy)
        assert view.category.get() == "Dự án mới" and editor.state.category_id == category_id
        assert editor.state.phase == EditorPhase.SAVED

        # Image attach/preview against Mongo + GridFS/BinData.
        with patch(WINDOW + "ask_image_file", return_value=str(image_path)):
            app.choose_image()
        wait_for(
            app,
            lambda: (
                editor.state.attachment is not None
                and view._photo is not None
                and not app.attachment_presenter.busy
            ),
        )
        assert editor.state.attachment.kind == "INLINE" and view._photo.width() == 400 // 2
        assert database.attachment_blobs.count_documents({}) == 1
        note_id = editor.state.note_id

        # Soft delete + restore keep the image; purge removes note and payload.
        with patch(WINDOW + "confirm_trash", return_value=True):
            app.trash_selected()
        wait_for(app, lambda: app._mutation_pending is None and not app.notes.state.items)
        assert database.attachment_blobs.count_documents({}) == 1
        app.switch_mode("trash")
        wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
        app.note_list._choose(note_id)
        app.restore_selected()
        wait_for(app, lambda: app._mutation_pending is None and app.mode == "active")
        wait_for(app, lambda: view._photo is not None and editor.state.attachment is not None)
        with patch(WINDOW + "confirm_trash", return_value=True):
            app.trash_selected()
        wait_for(app, lambda: app._mutation_pending is None and not app.notes.state.items)
        app.switch_mode("trash")
        wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
        app.note_list._choose(note_id)
        with patch(WINDOW + "confirm_purge", return_value=True):
            app.purge_selected()
        wait_for(app, lambda: app._mutation_pending is None and not app.notes.state.items)
        assert database.notes.count_documents({}) == 0
        assert database.attachment_blobs.count_documents({}) == 0
        assert not errors, errors
    finally:
        runtime.close()
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    {"phase3": scenario}[sys.argv[1]]()
    print("SCENARIO PASSED")
