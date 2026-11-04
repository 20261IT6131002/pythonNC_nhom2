"""Real Tk recovery/local-only statuses with deterministic ports and worker gates."""

from dataclasses import replace
from threading import Event

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.queries.list_notes import ListNotes
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.domain.errors import (
    AuthenticationFailed,
    RepositoryUnavailable,
    SecureStorageUnavailable,
)
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.state.sync_state import SyncState
from noteapp.presentation.tk.views.app_window import AppWindow
from tests.draft_fakes import FakeDraftStore, draft
from tests.fakes import FakeCategories, FakeClock, FakeNotes
from tests.repository_contracts import note
from tests.ui_scenarios import drive


def test_recovery_flow(monkeypatch):
    class ToggleNotes(FakeNotes):
        offline = True

        def create(self, value, operation_id):
            if self.offline:
                raise RepositoryUnavailable("offline")
            return super().create(value, operation_id)

    entered, release = Event(), Event()

    class GatedDrafts(FakeDraftStore):
        gated = False
        corrupt = None

        def save_if_newer(self, incoming):
            if self.gated:
                entered.set()
                assert release.wait(5)
            return super().save_if_newer(incoming)

        def get(self, identity):
            if identity == self.corrupt:
                raise AuthenticationFailed("private marker must not reach UI")
            return super().get(identity)

    notes, categories, clock = ToggleNotes(), FakeCategories(), FakeClock()
    store = GatedDrafts()
    original = draft()
    store.save_if_newer(original)
    service = DraftRecoveryService(store, notes, clock)
    runner = TaskRunner()

    def initialize():
        if notes.offline:
            raise RepositoryUnavailable("offline")
        return ()

    app = AppWindow(
        CreateNote(notes, categories, clock),
        UpdateNote(notes, categories, clock),
        ListNotes(notes),
        runner,
        initialize,
        drafts=service,
    )
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *args: errors.append(args)
    monkeypatch.setattr("noteapp.presentation.tk.views.app_window.confirm_discard", lambda *_: True)

    try:
        drive(app, lambda: app.recovery_dialog is not None)
        assert app.editor.state.content == ""  # no automatic plaintext recovery
        app.recovery_dialog.recover_button.invoke()
        drive(app, lambda: app.editor.state.draft_id == original.draft_id)
        assert app.editor.state.phase == EditorPhase.DIRTY
        assert app.editor.state.sync == SyncState.LOCAL_SAVED
        assert "chưa lưu vào máy chủ" in app.note_editor.status.cget("text")
        assert "phiên này" not in app.note_editor.status.cget("text")
        assert app.editor.state.operation_id == original.client_operation_id
        assert app.note_editor.content.get("1.0", "end-1c") == original.content

        app.save()
        drive(app, lambda: app.editor.state.phase == EditorPhase.ERROR)
        assert store.get(original.draft_id) == original
        assert "Bản nháp cục bộ" in app.note_editor.sync_status.cget("text")

        notes.offline = False
        app.connect()
        drive(app, lambda: app.sidebar._categories_ready)
        app.save()
        drive(app, lambda: app.editor.state.phase == EditorPhase.SAVED and not store.items)
        assert len(notes.items) == 1 and app.editor.state.sync == SyncState.REMOTE

        remote = notes.create(note(title="Remote", content="remote preserved"), "existing")
        local = draft(note_id=remote.id, base_version=1, category_id="missing-category")
        store.save_if_newer(local)
        notes.items[remote.id] = replace(remote, version=2)
        app.discover_drafts()
        drive(app, lambda: app.recovery_dialog is not None)
        app.recovery_dialog.rows.selection_set(local.draft_id)
        app.recovery_dialog.recover_button.invoke()
        drive(app, lambda: app.editor.state.draft_id == local.draft_id)
        assert app.editor.state.phase == EditorPhase.CONFLICT
        assert app.editor.state.category_id == "missing-category"
        assert app.note_editor.category.get() == "Danh mục không còn tồn tại"
        app.categories_changed(())
        assert app.editor.state.category_id == "missing-category"
        app.save()
        drive(app, lambda: not app.editor.saving)
        assert notes.items[remote.id].content == "remote preserved"
        assert store.get(local.draft_id) == local

        store.corrupt = local.draft_id
        app.new_note()
        app.discover_drafts()
        drive(app, lambda: app.recovery_dialog is not None)
        app.recovery_dialog.recover_button.invoke()
        drive(app, lambda: "không xác thực" in app.recovery_dialog.message.cget("text"))
        assert app.editor.state.content == ""
        app.recovery_dialog.close()
        store.corrupt = None

        app.note_editor.title.set("new content")
        app.root.update()
        store.error = SecureStorageUnavailable("private")
        app.draft_presenter.flush()
        drive(app, lambda: app.editor.state.sync == SyncState.SECURE_AUTOSAVE_DISABLED)
        assert "Không thể lưu nháp an toàn" in app.note_editor.sync_status.cget("text")
        assert "private" not in app.note_editor.sync_status.cget("text")

        store.error = None
        store.gated = True
        app.note_editor.content.insert("end", "pending close")
        app.root.update()
        app.draft_presenter.flush()
        drive(app, entered.is_set)
        app.close()
        release.set()
    finally:
        release.set()
        app.close()
        runner.close(wait=True)

    assert not errors, errors
