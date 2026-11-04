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


class RecordingGateway:
    """Stands in for the OS: the real PlyerGateway needs a desktop notification daemon."""

    sent: list = []

    def notify(self, title, message):
        self.sent.append((title, message))


def reminder_scenario():
    """Real Tk + real Mongo + real poller thread; only the OS notification is replaced."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from bson import ObjectId

    config = Config.from_env()
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(timezone.utc)
    sent = RecordingGateway.sent = []
    client_notes = None
    with patch("noteapp.bootstrap.PlyerGateway", RecordingGateway):
        # A reminder that came due while the app was closed.
        from noteapp.infrastructure.mongo.client import create_client

        with create_client(config) as client:
            client_notes = client[config.db_name].notes
            client_notes.insert_one(
                {
                    "_id": ObjectId(),
                    "client_operation_id": "missed-1",
                    "title": "Đã lỡ hẹn",
                    "content_plain": "",
                    "priority": "MEDIUM",
                    "priority_rank": 2,
                    "category_id": None,
                    "version": 1,
                    "created_at": now - timedelta(hours=3),
                    "updated_at": now - timedelta(hours=3),
                    "is_deleted": False,
                    "schema_version": 1,
                    "reminder": {
                        "due_at": now - timedelta(hours=1),
                        "status": "ACTIVE",
                        "updated_at": now - timedelta(hours=3),
                    },
                }
            )
        runtime = build_runtime(config)
    app = runtime.window
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)
    database = runtime.client[config.db_name]
    editor, view = app.editor, app.note_editor
    try:
        wait_for(app, lambda: str(app.sidebar.manage_button.cget("state")) == "normal")
        wait_for(app, lambda: sent == [("Nhắc nhở", "Đã lỡ hẹn")] and runtime.poller.running)
        wait_for(app, lambda: not app.notes.state.loading)
        missed = database.notes.find_one({"title": "Đã lỡ hẹn"})["reminder"]
        assert missed["status"] == "DELIVERED" and "claim_token" not in missed

        view.title.set("Họp nhóm")
        app.root.update()
        app.save()
        wait_for(app, lambda: editor.state.phase == EditorPhase.SAVED)
        note_id = editor.state.note_id
        local_due = (now + timedelta(hours=1)).astimezone(zone).replace(tzinfo=None)
        with patch(WINDOW + "ask_reminder_time", return_value=local_due):
            app.set_reminder()
        wait_for(app, lambda: editor.state.reminder is not None and not app.reminder_presenter.busy)
        stored = database.notes.find_one({"_id": ObjectId(note_id)})
        assert stored["version"] == 2 and stored["reminder"]["status"] == "ACTIVE"
        assert stored["reminder"]["due_at"].replace(tzinfo=timezone.utc) - now > timedelta(
            minutes=55
        )

        # Time passes: the due time moves into the past and the live poller delivers it.
        database.notes.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": {"reminder.due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
        )
        wait_for(app, lambda: editor.state.reminder.status == "DELIVERED", seconds=15)
        assert sent[-1] == ("Nhắc nhở", "Họp nhóm") and len(sent) == 2
        assert "Đã nhắc lúc" in view.reminder_info.cget("text")
        assert database.notes.find_one({"_id": ObjectId(note_id)})["version"] == 2

        # Reschedule revives it; trashing silences it; nothing is delivered twice.
        with patch(WINDOW + "ask_reminder_time", return_value=local_due):
            app.set_reminder()
        wait_for(
            app, lambda: editor.state.reminder.status == "ACTIVE" and editor.state.version == 3
        )
        database.notes.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": {"reminder.due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
        )
        with patch(WINDOW + "confirm_trash", return_value=True):
            app.trash_selected()
        wait_for(
            app,
            lambda: (
                app._mutation_pending is None
                and not any(i.note_id == note_id for i in app.notes.state.items)
            ),
        )
        wait_until_quiet = datetime.now(timezone.utc) + timedelta(seconds=7)
        while datetime.now(timezone.utc) < wait_until_quiet:
            app.root.update()
        assert len(sent) == 2
        assert database.notes.find_one({"_id": ObjectId(note_id)})["reminder"]["status"] == "ACTIVE"
        assert not errors, errors
    finally:
        runtime.close()
    assert not runtime.poller.running


if __name__ == "__main__":
    {"phase3": scenario, "phase3b": reminder_scenario}[sys.argv[1]]()
    print("SCENARIO PASSED")
