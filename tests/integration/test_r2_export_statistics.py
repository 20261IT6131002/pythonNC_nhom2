"""FR-15/16 with isolated Mongo, actual attachment storage and aggregation."""

from pathlib import Path
from uuid import uuid4

import pytest
from bson import ObjectId

from noteapp.application.commands.export_note import ExportFormat, ExportNote, ExportNoteInput
from noteapp.application.commands.locked_notes import LockedNotes
from noteapp.application.dto.local_draft import DraftAck, RecoveryKind
from noteapp.application.dto.note_input import AttachImageInput, CreateNoteInput, Priority
from noteapp.application.queries.note_statistics import GetNoteStatistics
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import AuthenticationFailed, ExportLocked, NotFound
from noteapp.infrastructure.export.files import FileNoteExporter
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository
from noteapp.infrastructure.mongo.statistics import MongoNoteStatisticsRepository
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.passphrase_kdf import Pbkdf2PassphraseKdf
from tests.draft_fakes import draft
from tests.integration.test_attachment_lifecycle import World, png
from tests.integration.test_encrypted_drafts import make_store
from tests.security_fakes import FakeSecretStore

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("gridfs", [False, True])
def test_export_reads_image_and_rejects_locked_and_trashed_notes(mongo_database, tmp_path, gridfs):
    db, _ = mongo_database
    world = World(db)
    export = ExportNote(world.notes, world.store, FileNoteExporter())
    saved = world.create.execute(
        CreateNoteInput("Ảnh minh họa", "Nội dung tiếng Việt", Priority.HIGH, None, str(uuid4()))
    )
    image = png((640, 640), noisy=True) if gridfs else png()
    assert (len(image) > 1024 * 1024) is gridfs
    updated = world.service.attach(AttachImageInput(saved.note_id, 1, image, "../../secret.png"))
    command = ExportNoteInput(saved.note_id, updated.version, str(tmp_path), ExportFormat.MARKDOWN)
    artifact = Path(export.execute(command))
    assert (artifact.parent / "assets" / "attachment.png").read_bytes() == image
    locked = LockedNotes(world.notes, world.create, AesGcmCipher(), Pbkdf2PassphraseKdf())
    masked = locked.lock(saved.note_id, updated.version, "synthetic FR15 passphrase")
    with pytest.raises(ExportLocked):
        export.execute(command)
    assert list(tmp_path.iterdir()) == [artifact.parent]
    world.trash_repo.move_to_trash(saved.note_id, masked.version, world.clock.now())
    with pytest.raises(NotFound):
        export.execute(command)


def test_statistics_empty_and_seeded_with_locked_trash_and_orphan_category(mongo_database):
    db, _ = mongo_database
    world = World(db)
    stats = GetNoteStatistics(MongoNoteStatisticsRepository(db))
    empty = stats.execute()
    assert empty.total == 0 and not empty.categories
    assert tuple(dict(empty.priorities).values()) == (0, 0, 0)

    categories = MongoCategoryRepository(db)
    catalog = categories.create(Category(str(ObjectId()), "Học tập", "#123456", world.clock.now()))

    def create(priority, category_id=None):
        return world.create.execute(
            CreateNoteInput("Title", "", priority, category_id, str(uuid4()))
        )

    create(Priority.HIGH, catalog.id)
    masked = create(Priority.LOW, catalog.id)
    create(Priority.HIGH)
    orphaned = create(Priority.LOW)
    db.notes.update_one({"_id": ObjectId(orphaned.note_id)}, {"$set": {"category_id": ObjectId()}})
    deleted = create(Priority.MEDIUM, catalog.id)
    world.trash_repo.move_to_trash(deleted.note_id, 1, world.clock.now())
    locked = LockedNotes(world.notes, world.create, AesGcmCipher(), Pbkdf2PassphraseKdf())
    locked.lock(masked.note_id, masked.version, "synthetic stats passphrase")

    counts = stats.execute()
    assert counts.total == 4
    assert {row.label: row.count for row in counts.categories} == {
        "Học tập": 2,
        "Chưa phân loại": 2,
    }
    assert dict(counts.priorities) == {Priority.HIGH: 2, Priority.MEDIUM: 0, Priority.LOW: 2}


@pytest.mark.parametrize("committed_before_recovery", [False, True])
def test_unsynced_locked_new_draft_reuses_operation_id_without_plaintext(
    mongo_database, tmp_path, committed_before_recovery
):
    db, _ = mongo_database
    world = World(db)
    locked = LockedNotes(world.notes, world.create, AesGcmCipher(), Pbkdf2PassphraseKdf())
    snapshot = draft(source_locked=True, title="Ghi chú khóa chưa đồng bộ")
    command = CreateNoteInput(
        snapshot.title,
        snapshot.content,
        snapshot.priority,
        snapshot.category_id,
        snapshot.client_operation_id,
    )
    password = "synthetic recovery phrase"
    previous = locked.create_locked(command, password) if committed_before_recovery else None
    store = make_store(tmp_path / "drafts", FakeSecretStore())
    try:
        recovery = DraftRecoveryService(store, world.notes, world.clock, locked_notes=True)
        assert recovery.autosave.execute(snapshot)
        decision = recovery.recover(snapshot.draft_id)
        assert decision.kind == RecoveryKind.SAFE_NEW and decision.draft == snapshot
        if previous is not None:
            with pytest.raises(AuthenticationFailed):
                locked.create_locked(command, "wrong recovery phrase")
            assert store.get(snapshot.draft_id) == snapshot
        saved = locked.create_locked(command, password)
        if previous is not None:
            assert saved.note_id == previous.note_id
        assert db.notes.count_documents({}) == 1
        assert "content_plain" not in db.notes.find_one()
        assert recovery.acknowledge(DraftAck(snapshot.draft_id, snapshot.revision))
    finally:
        store.close()
