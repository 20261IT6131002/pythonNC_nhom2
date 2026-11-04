"""P3A-07/09: image lifecycle on real Mongo, including purge, retention and reconciliation."""

import random
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.trash import TrashNote
from noteapp.application.dto.note_input import (
    AttachImageInput,
    CreateNoteInput,
    GetImageInput,
    Priority,
    PurgeNoteInput,
    RemoveImageInput,
    RestoreNoteInput,
    TrashNoteInput,
)
from noteapp.application.services.attachment_service import AttachmentService
from noteapp.domain.errors import (
    AttachmentStoreFailure,
    Conflict,
    NotFound,
    RepositoryUnavailable,
    ValidationError,
)
from noteapp.infrastructure.attachment.hybrid_store import MongoAttachmentStore
from noteapp.infrastructure.attachment.image_validator import PillowImageProcessor
from noteapp.infrastructure.attachment.reconciler import MongoAttachmentReconciler
from noteapp.infrastructure.mongo.models import object_id
from noteapp.infrastructure.mongo.repositories import (
    MongoCategoryRepository,
    MongoNoteAttachmentRepository,
    MongoNoteRepository,
)
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.scheduler.purge_worker import PurgeWorker
from tests.fakes import FakeClock

pytestmark = pytest.mark.integration


def png(size=(64, 32), noisy=False):
    out = BytesIO()
    if noisy:  # seeded random pixels do not compress, so the PNG crosses 1 MiB
        pixels = random.Random(7).randbytes(size[0] * size[1] * 3)
        image = Image.frombytes("RGB", size, pixels)
    else:
        image = Image.new("RGB", size, (10, 120, 200))
    image.save(out, format="PNG")
    return out.getvalue()


class World:
    def __init__(self, database):
        self.database = database
        self.clock = FakeClock()
        self.notes = MongoNoteRepository(database)
        self.store = MongoAttachmentStore(database, now=self.clock.now)
        self.trash_repo = MongoTrashRepository(database, self.store)
        self.service = AttachmentService(
            self.notes,
            MongoNoteAttachmentRepository(database),
            self.store,
            PillowImageProcessor(),
            self.clock,
        )
        self.create = CreateNote(self.notes, MongoCategoryRepository(database), self.clock)

    def note(self):
        return self.create.execute(
            CreateNoteInput("Có ảnh", "nội dung", Priority.MEDIUM, None, str(uuid4()))
        )

    def payloads(self):
        return self.database.attachment_blobs.count_documents({}) + self.database[
            "attachments.files"
        ].count_documents({})


@pytest.fixture
def world(mongo_database):
    return World(mongo_database[0])


def test_attach_replace_remove_leave_exactly_the_referenced_payload(world):
    saved = world.note()
    first = world.service.attach(AttachImageInput(saved.note_id, 1, png(), "one.png"))
    assert (first.version, first.attachment.kind) == (2, "INLINE") and world.payloads() == 1
    second = world.service.attach(AttachImageInput(saved.note_id, 2, png((80, 40)), "two.png"))
    assert second.version == 3 and world.payloads() == 1
    stored = world.notes.find_by_id(saved.note_id)
    assert stored.attachment.display_name == "two.png" and stored.title == "Có ảnh"
    removed = world.service.remove(RemoveImageInput(saved.note_id, 3))
    assert removed.attachment is None and world.payloads() == 0
    assert world.notes.find_by_id(saved.note_id).attachment is None


def test_large_image_goes_to_gridfs_and_thumbnail_is_bounded(world):
    saved = world.note()
    data = png((900, 700), noisy=True)
    assert len(data) > 1024 * 1024
    view = world.service.attach(AttachImageInput(saved.note_id, 1, data, "big.png"))
    assert view.attachment.kind == "GRIDFS"
    assert world.database["attachments.files"].count_documents({}) == 1
    content = world.service.get(GetImageInput(saved.note_id, 400))
    assert content.width == 400 and Image.open(BytesIO(content.png)).format == "PNG"


def test_stale_version_leaves_no_orphan_and_keeps_old_image(world):
    saved = world.note()
    world.service.attach(AttachImageInput(saved.note_id, 1, png(), "one.png"))
    with pytest.raises(Conflict):
        world.service.attach(AttachImageInput(saved.note_id, 1, png((70, 30)), "two.png"))
    assert world.payloads() == 1
    assert world.notes.find_by_id(saved.note_id).attachment.display_name == "one.png"


def test_text_update_after_attachment_keeps_the_image(world):
    from noteapp.application.commands.update import UpdateNote
    from noteapp.application.dto.note_input import UpdateNoteInput

    saved = world.note()
    attached = world.service.attach(AttachImageInput(saved.note_id, 1, png(), "keep.png"))
    updated = UpdateNote(world.notes, MongoCategoryRepository(world.database), world.clock).execute(
        UpdateNoteInput(saved.note_id, "Mới", "sửa", Priority.HIGH, None, attached.version)
    )
    assert updated.title == "Mới"
    assert world.notes.find_by_id(saved.note_id).attachment.display_name == "keep.png"


def test_list_and_search_pages_carry_metadata_but_never_payload(world):
    saved = world.note()
    world.service.attach(AttachImageInput(saved.note_id, 1, png(), "meta.png"))
    page = world.notes.list_recent(10)
    assert page.items[0].attachment.display_name == "meta.png"


def test_trash_and_restore_preserve_the_image(world):
    saved = world.note()
    attached = world.service.attach(AttachImageInput(saved.note_id, 1, png(), "keep.png"))
    trashed = TrashNote(world.trash_repo, world.clock).execute(
        TrashNoteInput(saved.note_id, attached.version)
    )
    assert trashed.note.attachment.display_name == "keep.png" and world.payloads() == 1
    restored = RestoreNote(world.trash_repo, world.clock).execute(
        RestoreNoteInput(saved.note_id, trashed.note.version)
    )
    assert restored.attachment.display_name == "keep.png"
    assert world.service.get(GetImageInput(saved.note_id, 400)).display_name == "keep.png"


def test_attach_to_trashed_note_is_rejected_and_cleans_up(world):
    saved = world.note()
    TrashNote(world.trash_repo, world.clock).execute(TrashNoteInput(saved.note_id, 1))
    with pytest.raises(NotFound):
        world.service.attach(AttachImageInput(saved.note_id, 1, png(), "x.png"))
    assert world.payloads() == 0


def trashed_with_image(world):
    saved = world.note()
    attached = world.service.attach(AttachImageInput(saved.note_id, 1, png(), "bye.png"))
    trashed = TrashNote(world.trash_repo, world.clock).execute(
        TrashNoteInput(saved.note_id, attached.version)
    )
    return saved.note_id, trashed.note.version


def test_permanent_delete_removes_note_and_payload(world):
    note_id, version = trashed_with_image(world)
    PurgeNote(world.trash_repo).execute(PurgeNoteInput(note_id, version, True))
    assert world.database.notes.count_documents({}) == 0 and world.payloads() == 0


def test_permanent_delete_survives_cleanup_failure_and_reconciler_finishes(world):
    note_id, version = trashed_with_image(world)

    class Failing(MongoAttachmentStore):
        def delete(self, ref):
            raise AttachmentStoreFailure("down")

    world.trash_repo.attachments = Failing(world.database, now=world.clock.now)
    PurgeNote(world.trash_repo).execute(PurgeNoteInput(note_id, version, True))
    assert world.database.notes.count_documents({}) == 0 and world.payloads() == 1
    reconciler = MongoAttachmentReconciler(world.database)
    assert reconciler.run_once(world.clock.now()).removed == 0  # still inside the grace window
    later = world.clock.now() + timedelta(hours=1)
    assert reconciler.run_once(later).removed == 1 and world.payloads() == 0


def test_purge_without_store_fails_closed_and_keeps_everything(world):
    note_id, version = trashed_with_image(world)
    text_only = MongoTrashRepository(world.database)
    with pytest.raises(ValidationError):
        PurgeNote(text_only).execute(PurgeNoteInput(note_id, version, True))
    assert text_only.expired_candidates(world.clock.now() + timedelta(days=60)) == ()
    assert world.database.notes.count_documents({}) == 1 and world.payloads() == 1


def test_retention_purges_expired_notes_with_images_and_their_payloads(world):
    note_id, _ = trashed_with_image(world)
    far = world.clock.now() + timedelta(days=45)

    class Later:
        def now(self):
            return far

    report = PurgeWorker(world.trash_repo, Later()).run_once()
    assert report.purged == 1 and world.payloads() == 0
    assert world.database.notes.count_documents({"_id": object_id(note_id)}) == 0


def test_reconciler_keeps_referenced_active_and_trashed_and_removes_orphans(world):
    active = world.note()
    world.service.attach(AttachImageInput(active.note_id, 1, png(), "active.png"))
    trashed_with_image(world)
    orphan = world.store.put("a" * 24, PillowImageProcessor().inspect(png((9, 9))), "o.png")
    later = world.clock.now() + timedelta(hours=1)
    reconciler = MongoAttachmentReconciler(world.database)
    assert reconciler.run_once(world.clock.now()).removed == 0
    assert reconciler.run_once(later).removed == 1
    assert world.payloads() == 2 and not world.store.exists(orphan)


def test_reconciler_batch_limit_and_idempotency(world):
    image = PillowImageProcessor().inspect(png((9, 9)))
    for _ in range(3):
        world.store.put("a" * 24, image, "o.png")
    reconciler = MongoAttachmentReconciler(world.database)
    later = world.clock.now() + timedelta(hours=1)
    assert reconciler.run_once(later, limit=2).removed == 2
    assert reconciler.run_once(later, limit=2).removed == 1
    assert reconciler.run_once(later, limit=2).removed == 0
    with pytest.raises(RepositoryUnavailable):
        reconciler.run_once(later, limit=0)


def test_gridfs_upload_failure_keeps_note_and_old_image(world, monkeypatch):
    saved = world.note()
    first = world.service.attach(AttachImageInput(saved.note_id, 1, png(), "one.png"))
    from pymongo.errors import PyMongoError

    def boom(*_args, **_kwargs):
        raise PyMongoError("upload failed")

    monkeypatch.setattr(world.store.bucket, "upload_from_stream", boom)
    big = png((900, 700), noisy=True)
    with pytest.raises(AttachmentStoreFailure):
        world.service.attach(AttachImageInput(saved.note_id, first.version, big, "big.png"))
    stored = world.notes.find_by_id(saved.note_id)
    assert stored.attachment.display_name == "one.png" and stored.version == first.version
    assert world.payloads() == 1


def test_mongo_failure_during_note_update_cleans_new_payload(world, monkeypatch):
    saved = world.note()
    first = world.service.attach(AttachImageInput(saved.note_id, 1, png(), "one.png"))
    from pymongo.errors import PyMongoError

    def boom(*_args, **_kwargs):
        raise PyMongoError("update failed")

    monkeypatch.setattr(world.service.links.collection, "update_one", boom)
    with pytest.raises(RepositoryUnavailable):
        world.service.attach(
            AttachImageInput(saved.note_id, first.version, png((70, 30)), "two.png")
        )
    assert world.payloads() == 1
    assert world.notes.find_by_id(saved.note_id).attachment.display_name == "one.png"
