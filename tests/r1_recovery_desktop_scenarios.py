"""Real process crash/restart and Mongo; only the device-key port is a synthetic test double."""

import os
import sys
from pathlib import Path
from uuid import uuid4

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_input import CreateNoteInput
from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.bootstrap import build_runtime
from noteapp.domain.errors import RepositoryUnavailable
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.local.encrypted_draft_store import EncryptedLocalDraftStore
from noteapp.infrastructure.mongo.client import SystemClock, create_client
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.state.sync_state import SyncState
from tests.desktop_scenarios import wait_for
from tests.security_fakes import FakeSecretStore

MARKER = "Bản nháp riêng tư sống qua lần đóng đột ngột"


class FaultInjectedNotes:
    """Transport fault injection never stops or modifies the shared Mongo service."""

    def __init__(self, actual):
        self.actual = actual
        self.offline = False
        self.lose_ack = False

    def _check(self):
        if self.offline:
            raise RepositoryUnavailable("Synthetic transport outage.")

    def create(self, value, operation_id):
        self._check()
        saved = self.actual.create(value, operation_id)
        if self.lose_ack:
            self.lose_ack = False
            raise RepositoryUnavailable("Synthetic lost acknowledgement after commit.")
        return saved

    def find_by_id(self, identity):
        self._check()
        return self.actual.find_by_id(identity)

    def update_if_version(self, value, version):
        self._check()
        return self.actual.update_if_version(value, version)


def abrupt_exit():
    print("SCENARIO PASSED — encrypted snapshot acknowledged before abrupt exit", flush=True)
    os._exit(0)  # intentionally bypass Runtime.close/finally to exercise kernel lease release


def capture_recovery(app):
    if os.environ.get("NOTEAPP_CAPTURE_RECOVERY_UI") != "1":
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

    picture.save(Path(__file__).resolve().parents[1] / "docs/testing/R1_DRAFT_RECOVERY_DESKTOP.png")
    app.root.withdraw()


def main():
    mode = sys.argv[1]
    config = Config.from_env()
    client = create_client(config)
    database = client[config.db_name]
    actual = MongoNoteRepository(database)
    notes = FaultInjectedNotes(actual)
    clock = SystemClock()
    categories = MongoCategoryRepository(database)
    directory = Path(os.environ["NOTEAPP_RECOVERY_TEST_DIR"])
    secrets = FakeSecretStore()

    if mode != "missing_key":
        # Stable synthetic test material, never available in production bootstrap/config.
        secrets.put("draft-master-key.v1", bytes(range(32)))

    store = EncryptedLocalDraftStore(
        directory, AesGcmCipher(), DraftKeyProvider(secrets, lambda: bytes(range(32)))
    )
    service = DraftRecoveryService(store, notes, clock)
    runtime = build_runtime(config, drafts=service)
    app = runtime.window
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)
    app.editor.create = CreateNote(notes, categories, clock)
    app.editor.update = UpdateNote(notes, categories, clock)
    initialize = app.initialize

    def probe():
        notes._check()
        return initialize()

    app.initialize = probe
    notes.offline = mode in {"offline_create", "recover_reconnect"}
    app.connect()

    try:
        if mode in {"offline_create", "ack_loss", "conflict_create"}:
            if mode == "conflict_create":
                saved = CreateNote(actual, categories, clock).execute(
                    CreateNoteInput(
                        "Existing",
                        "original remote",
                        Priority.MEDIUM,
                        None,
                        str(uuid4()),
                    )
                )
                app.open_note(saved)
            else:
                app.note_editor.title.set("Recovery note")

            app.note_editor.content.delete("1.0", "end")
            app.note_editor.content.insert("1.0", MARKER)
            app.root.update()
            app.draft_presenter.flush()
            wait_for(app, lambda: app.editor.state.sync == SyncState.LOCAL_SAVED)
            files = list(directory.glob("*.draft"))
            assert len(files) == 1 and MARKER.encode() not in files[0].read_bytes()

            if mode == "conflict_create":
                current = actual.find_by_id(app.editor.state.note_id)
                assert actual.update_if_version(
                    current.edited(
                        title="Remote winner",
                        content="remote preserved",
                        priority=current.priority,
                        category_id=None,
                        now=clock.now(),
                    ),
                    current.version,
                )
            else:
                notes.lose_ack = mode == "ack_loss"
                app.save()
                wait_for(app, lambda: app.editor.state.phase == EditorPhase.ERROR)
                assert store.get(app.editor.state.draft_id).content == MARKER
                assert database.notes.count_documents({}) == (1 if mode == "ack_loss" else 0)

            assert not errors, errors
            abrupt_exit()

        if mode == "verify_final":
            wait_for(app, lambda: not app.notes.state.loading and len(app.notes.state.items) == 1)
            assert app.notes.state.items[0].content == MARKER
            assert not list(directory.glob("*.draft"))
        else:
            wait_for(app, lambda: app.recovery_dialog is not None)
            assert app.editor.state.content == ""
            app.recovery_dialog.recover_button.invoke()

            if mode in {"missing_key", "tampered"}:
                phrase = "khóa" if mode == "missing_key" else "không xác thực"
                wait_for(app, lambda: phrase in app.recovery_dialog.message.cget("text"))
                assert app.editor.state.content == "" and list(directory.glob("*.draft"))
                if mode == "missing_key":
                    assert secrets.get("draft-master-key.v1") is None
            elif mode == "conflict_recover":
                wait_for(app, lambda: app.editor.state.phase == EditorPhase.CONFLICT)
                assert app.editor.state.content == MARKER and app.editor.state.version == 1
                app.save()
                wait_for(app, lambda: not app.editor.saving)
                assert app.editor.state.phase == EditorPhase.CONFLICT
                assert database.notes.find_one({})["content_plain"] == "remote preserved"
                assert store.get(app.editor.state.draft_id).content == MARKER
            else:
                wait_for(app, lambda: app.editor.state.content == MARKER)
                assert app.editor.state.phase == EditorPhase.DIRTY
                identity = app.editor.state.draft_id
                if mode == "recover_reconnect":
                    app.save()
                    wait_for(app, lambda: app.editor.state.phase == EditorPhase.ERROR)
                    notes.offline = False
                    app.connect()
                    wait_for(app, lambda: app.sidebar._categories_ready)
                    capture_recovery(app)

                app.save()
                wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
                wait_for(app, lambda: store.get(identity) is None)
                assert database.notes.count_documents({}) == 1
                assert database.notes.find_one({})["content_plain"] == MARKER

        assert not errors, errors
    finally:
        runtime.close()
        client.close()

    print("SCENARIO PASSED")


if __name__ == "__main__":
    main()
