"""FR-14 desktop workflows in fresh processes using isolated Mongo."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

from noteapp.application.dto.operation_result import ErrorCode
from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.bootstrap import build_runtime
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.local.encrypted_draft_store import EncryptedLocalDraftStore
from noteapp.infrastructure.mongo.client import SystemClock, create_client
from noteapp.infrastructure.mongo.repositories import MongoNoteRepository
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.state.sync_state import SyncState
from tests.desktop_scenarios import wait_for
from tests.security_fakes import FakeSecretStore

WINDOW = "noteapp.presentation.tk.views.app_window."
TITLE = "Desktop private title"
CONTENT = "Desktop private content — tiếng Việt"
PASSWORD = "desktop synthetic phrase"
DRAFT_MARKER = "private draft content after process restart"


def create(app):
    wait_for(app, lambda: app.sidebar._categories_ready)
    app.note_editor.title.set(TITLE)
    app.note_editor.content.insert("end", CONTENT)
    app.root.update()
    with patch(WINDOW + "ask_passphrase", return_value=PASSWORD):
        app.lock_selected()
    wait_for(app, lambda: app.editor.state.locked_closed)
    assert app.note_editor.title.get() != TITLE
    assert not app.note_editor.content.get("1.0", "end-1c")


def unlock(app, password):
    with patch(WINDOW + "ask_passphrase", return_value=password):
        app.unlock_selected()
    wait_for(app, lambda: not app.editor.lock_busy)


def restart(app):
    wait_for(app, lambda: len(app.notes.state.items) == 1)
    row = app.notes.state.items[0]
    assert row.is_locked and row.content is None and row.title != TITLE
    assert app.open_note(row)
    unlock(app, "incorrect desktop phrase")
    assert app.editor.state.error == ErrorCode.AUTHENTICATION_FAILED
    assert not app.note_editor.content.get("1.0", "end-1c")

    unlock(app, PASSWORD)
    assert app.note_editor.title.get() == TITLE
    assert app.note_editor.content.get("1.0", "end-1c") == CONTENT
    app.note_editor.content.insert("end", " • edited")
    app.root.update()
    app.save()
    wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
    assert app.editor.state.version == 2

    app._expire_lock_session()
    assert app.editor.state.locked_closed
    assert app.note_editor.content.get("1.0", "end-1c") == ""
    unlock(app, PASSWORD)
    assert app.note_editor.content.get("1.0", "end-1c") == CONTENT + " • edited"
    app.new_note()
    assert not app.editor.unlocked
    assert not app.note_editor.content.get("1.0", "end-1c")


def draft_crash(app):
    wait_for(app, lambda: len(app.notes.state.items) == 1)
    assert app.open_note(app.notes.state.items[0])
    unlock(app, PASSWORD)
    app.note_editor.content.delete("1.0", "end")
    app.note_editor.content.insert("1.0", DRAFT_MARKER)
    app.root.update()
    app.draft_presenter.flush()
    wait_for(app, lambda: app.editor.state.sync == SyncState.LOCAL_SAVED)
    print("SCENARIO PASSED", flush=True)
    os._exit(0)


def draft_recover(app):
    wait_for(app, lambda: app.sidebar._categories_ready)
    app.discover_drafts()
    wait_for(app, lambda: app.recovery_dialog is not None and len(app.draft_headers) == 1)
    identity = app.draft_headers[0].draft_id
    with patch(WINDOW + "ask_passphrase", return_value="wrong draft recovery phrase"):
        app.recover_draft(identity)
        wait_for(app, lambda: app.editor.state.error == ErrorCode.AUTHENTICATION_FAILED)
    assert DRAFT_MARKER not in app.note_editor.content.get("1.0", "end-1c")
    assert app.recovery_dialog is not None
    with patch(WINDOW + "ask_passphrase", return_value=PASSWORD):
        app.recover_draft(identity)
        wait_for(app, lambda: app.recovery_dialog is None)
    assert app.editor.state.source_locked and app.editor.state.version == 1
    assert app.note_editor.content.get("1.0", "end-1c") == DRAFT_MARKER
    app.save()
    wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
    assert app.editor.state.version == 2
    wait_for(app, lambda: not list(Path(os.environ["NOTEAPP_LOCKED_TEST_DRAFTS"]).glob("*.draft")))


def main():
    config = Config.from_env()
    mode = sys.argv[1]
    directory = os.environ.get("NOTEAPP_LOCKED_TEST_DRAFTS")
    client = create_client(config)
    store = None
    drafts = None
    if directory and mode.startswith("draft_"):
        keys = DraftKeyProvider(FakeSecretStore(), lambda: bytes(range(32)))
        keys.get_key(existing_ciphertext=False)
        store = EncryptedLocalDraftStore(Path(directory), AesGcmCipher(), keys)
        notes = MongoNoteRepository(client[config.db_name])
        drafts = DraftRecoveryService(store, notes, SystemClock(), locked_notes=True)
    runtime = build_runtime(config, drafts=drafts)
    app = runtime.window
    callbacks = []
    app.root.report_callback_exception = lambda *error: callbacks.append(error)
    app.root.withdraw()
    try:
        scenarios = {
            "create": create,
            "restart": restart,
            "draft_crash": draft_crash,
            "draft_recover": draft_recover,
        }
        scenarios[mode](app)
        assert not callbacks
    finally:
        runtime.close()
        if store is not None:
            store.close()
        client.close()
    print("SCENARIO PASSED")


if __name__ == "__main__":
    main()
