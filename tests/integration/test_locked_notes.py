"""FR-14 checks with MongoDB, real PBKDF2 and AES-256-GCM."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from bson import ObjectId

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.locked_notes import LockedNotes
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.local_draft import DraftAck, RecoveryKind
from noteapp.application.dto.note_input import CreateNoteInput, UpdateNoteInput
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.application.services.reminder_service import ReminderDeliveryService
from noteapp.domain.entities.reminder import Reminder
from noteapp.domain.errors import AuthenticationFailed, Conflict, ValidationError
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.mongo.migrations import locked_schema_report
from noteapp.infrastructure.mongo.repositories import (
    MongoCategoryRepository,
    MongoNoteRepository,
    MongoReminderRepository,
)
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.passphrase_kdf import Pbkdf2PassphraseKdf
from tests.draft_fakes import draft
from tests.fakes import FakeClock
from tests.integration.test_encrypted_drafts import make_store
from tests.security_fakes import FakeSecretStore

pytestmark = pytest.mark.integration
SECRET = "mật khẩu hợp lệ 123"
NEW_SECRET = "mật khẩu mới khác 456"
TITLE = "privatetitlecanary"
CONTENT = "privatecontentcanary — nội dung 🌱"


@pytest.fixture
def world(mongo_database):
    database, _ = mongo_database
    notes, categories, clock = (
        MongoNoteRepository(database),
        MongoCategoryRepository(database),
        FakeClock(),
    )
    create = CreateNote(notes, categories, clock)
    locked = LockedNotes(notes, create, AesGcmCipher(), Pbkdf2PassphraseKdf())
    command = CreateNoteInput(TITLE, CONTENT, Priority.HIGH, None, str(uuid4()))
    return database, notes, categories, clock, create, locked, command


def test_lock_removes_indexed_plaintext_and_blocks_direct_plain_cas(world):
    db, notes, categories, clock, create, locked, command = world
    plain = create.execute(command)
    stale = notes.find_by_id(plain.note_id)
    assert db.notes.count_documents({"$text": {"$search": TITLE}}) == 1
    saved = locked.lock(plain.note_id, 1, SECRET)
    assert saved.is_locked and saved.content is None and saved.version == 2
    raw = db.notes.find_one({"_id": ObjectId(saved.note_id)})
    assert raw["schema_version"] == 3
    assert "content_plain" not in raw
    assert TITLE not in repr(raw) and CONTENT not in repr(raw) and SECRET not in repr(raw)
    assert db.notes.count_documents({"$text": {"$search": f"{TITLE} privatecontentcanary"}}) == 0
    assert notes.list_recent(10).items[0].content is None
    assert locked_schema_report(db)["invalid_note_representation"] == 0
    update = UpdateNoteInput(saved.note_id, TITLE, CONTENT, Priority.HIGH, None, 2)
    with pytest.raises(ValidationError):
        UpdateNote(notes, categories, clock).execute(update)
    assert not notes.update_if_version(replace(stale, version=3), 2)
    assert locked.unlock(saved.note_id, 2, SECRET).content == CONTENT


def test_create_update_rekey_remove_and_tamper(world):
    db, _, _, _, _, locked, command = world
    first = locked.create_locked(command, SECRET)
    assert locked.create_locked(command, SECRET) == first
    query = {"_id": ObjectId(first.note_id)}
    assert db.notes.count_documents({}) == 1
    initial = db.notes.find_one(query)["content_encrypted"]
    with pytest.raises(AuthenticationFailed):
        locked.unlock(first.note_id, 1, NEW_SECRET)
    next_view = locked.update(
        UpdateNoteInput(first.note_id, TITLE, "Changed", Priority.LOW, None, 1), SECRET
    )
    edited = db.notes.find_one(query)["content_encrypted"]
    assert edited["nonce"] != initial["nonce"] and edited["kdf"]["salt"] != initial["kdf"]["salt"]
    changed = locked.change_passphrase(first.note_id, next_view.version, SECRET, NEW_SECRET)
    rotated = db.notes.find_one(query)["content_encrypted"]
    assert rotated["nonce"] != edited["nonce"]
    assert rotated["kdf"]["salt"] != edited["kdf"]["salt"]
    with pytest.raises(AuthenticationFailed):
        locked.unlock(first.note_id, changed.version, SECRET)
    ciphertext = rotated["ciphertext"]
    db.notes.update_one(
        query,
        {"$set": {"content_encrypted.ciphertext": ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])}},
    )
    with pytest.raises(AuthenticationFailed):
        locked.unlock(first.note_id, changed.version, NEW_SECRET)
    db.notes.update_one(query, {"$set": {"content_encrypted": rotated}})
    with pytest.raises(ValidationError):
        locked.remove(first.note_id, changed.version, NEW_SECRET, confirmed=False)
    unlocked = locked.remove(first.note_id, changed.version, NEW_SECRET, confirmed=True)
    assert not unlocked.is_locked and unlocked.content == "Changed"
    raw = db.notes.find_one(query)
    assert "content_encrypted" not in raw and raw["content_plain"] == "Changed"


def test_metadata_trash_purge_and_notification_keep_ciphertext(world):
    db, notes, _, clock, _, locked, command = world
    saved = locked.create_locked(command, SECRET)
    query = {"_id": ObjectId(saved.note_id)}
    payload = db.notes.find_one(query)["content_encrypted"]
    note = notes.find_by_id(saved.note_id)
    pinned = note.with_pinned(True)
    assert notes.set_pinned_if_version(pinned, note.version)
    with pytest.raises(Conflict):
        locked.unlock(saved.note_id, note.version, SECRET)

    reminders = MongoReminderRepository(db)
    scheduled = pinned.with_reminder(
        Reminder(clock.now() - timedelta(seconds=1), "ACTIVE", clock.now()), clock.now()
    )
    assert reminders.set_reminder_if_version(scheduled, pinned.version)
    messages = []

    class Gateway:
        def notify(self, title, message):
            messages.append((title, message))

    assert ReminderDeliveryService(reminders, Gateway(), clock).deliver_due().delivered
    assert messages == [("Nhắc nhở", "Bạn có một ghi chú đến hạn")]
    trash = MongoTrashRepository(db)
    deleted = trash.move_to_trash(saved.note_id, scheduled.version, clock.now())
    assert deleted.note.is_locked
    assert trash.list_trashed(1).items[0].note.content is None
    restored = trash.restore(saved.note_id, deleted.note.version, clock.now())
    assert restored.is_locked and restored.is_pinned
    assert db.notes.find_one(query)["content_encrypted"] == payload
    deleted = trash.move_to_trash(saved.note_id, restored.version, clock.now())
    trash.purge_confirmed(saved.note_id, deleted.note.version)
    assert db.notes.find_one(query) is None


def test_copied_payload_and_unbounded_kdf_fail_closed(world):
    db, _, _, _, _, locked, command = world
    first = locked.create_locked(command, SECRET)
    second = locked.create_locked(replace(command, client_operation_id=str(uuid4())), SECRET)
    raw = db.notes.find_one({"_id": ObjectId(first.note_id)})["content_encrypted"]
    query = {"_id": ObjectId(second.note_id)}
    db.notes.update_one(query, {"$set": {"content_encrypted": raw}})
    with pytest.raises(AuthenticationFailed):
        locked.unlock(second.note_id, second.version, SECRET)
    db.notes.update_one(query, {"$set": {"content_encrypted.kdf.iterations": 10**9}})
    with pytest.raises(ValidationError):
        locked.unlock(second.note_id, second.version, SECRET)
    assert locked_schema_report(db)["invalid_note_representation"] == 1


def test_locked_draft_is_encrypted_and_cleared_only_after_exact_ack(world, tmp_path):
    db, notes, _, clock, _, locked, command = world
    saved = locked.create_locked(command, SECRET)
    directory = tmp_path / "locked-drafts"
    secrets = FakeSecretStore()
    snapshot = draft(
        note_id=saved.note_id,
        base_version=saved.version,
        source_locked=True,
        content=CONTENT,
        revision=4,
    )
    store = make_store(directory, secrets)
    try:
        assert DraftRecoveryService(store, notes, clock, locked_notes=True).autosave.execute(
            snapshot
        )
        files = tuple(directory.glob("*.draft"))
        assert len(files) == 1
        assert CONTENT.encode() not in files[0].read_bytes()
        assert SECRET.encode() not in files[0].read_bytes()
    finally:
        store.close()
    reopened = make_store(directory, secrets)
    try:
        recovery = DraftRecoveryService(reopened, notes, clock, locked_notes=True)
        decision = recovery.recover(snapshot.draft_id)
        assert decision.kind == RecoveryKind.SAFE_EXISTING and decision.draft == snapshot
        with pytest.raises(AuthenticationFailed):
            locked.unlock(saved.note_id, saved.version, NEW_SECRET)
        assert reopened.get(snapshot.draft_id) == snapshot
        assert not recovery.acknowledge(DraftAck(snapshot.draft_id, snapshot.revision - 1))
        updated = locked.update(
            UpdateNoteInput(
                snapshot.note_id,
                snapshot.title,
                snapshot.content,
                snapshot.priority,
                snapshot.category_id,
                snapshot.base_version,
            ),
            SECRET,
        )
        assert updated.version == saved.version + 1
        assert recovery.recover(snapshot.draft_id).kind == RecoveryKind.REMOTE_CONFLICT
        assert "content_plain" not in db.notes.find_one()
        assert recovery.acknowledge(DraftAck(snapshot.draft_id, snapshot.revision))
        assert reopened.get(snapshot.draft_id) is None
    finally:
        reopened.close()
