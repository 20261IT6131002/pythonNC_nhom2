"""Real CAS/lazy migration/purge guard, including races and retention cutoff."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from bson import ObjectId

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.dto.note_input import CreateNoteInput, PurgeNoteInput
from noteapp.domain.errors import Conflict, NotFound, ValidationError
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.mongo.migrations import schema_report
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.scheduler.purge_worker import PurgeWorker
from tests.fakes import FakeClock

pytestmark = pytest.mark.integration


@pytest.fixture
def trash_core(mongo_database):
    db = mongo_database[0]
    clock = FakeClock()
    notes = MongoNoteRepository(db)
    create = CreateNote(notes, MongoCategoryRepository(db), clock)
    trash = MongoTrashRepository(db)
    return db, clock, notes, create, trash


def make_note(core, title="Text note"):
    return core[3].execute(
        CreateNoteInput(title, "Keep content", Priority.HIGH, None, str(uuid4()))
    )


def test_v1_trash_restore_same_id_and_payload(trash_core):
    db, clock, notes, _, trash = trash_core
    saved = make_note(trash_core)
    before = db.notes.find_one()
    assert before["schema_version"] == 1 and "deleted_at" not in before
    clock.value += timedelta(seconds=1)
    deleted = trash.move_to_trash(saved.note_id, 1, clock.now())
    assert deleted.note.version == 2 and deleted.deleted_at.utcoffset() == timedelta(0)
    assert notes.find_by_id(saved.note_id) is None and not notes.list_recent(30).items
    assert schema_report(db) == {"schema_v1": 0, "schema_v2": 1, "invalid_tombstones": 0}
    with pytest.raises(Conflict):
        trash.move_to_trash(saved.note_id, 1, clock.now())
    restored = trash.restore(saved.note_id, 2, clock.now())
    assert restored.id == saved.note_id and restored.content == saved.content
    assert restored.created_at == saved.created_at and restored.priority == saved.priority
    assert restored.version == 3 and "deleted_at" not in db.notes.find_one()
    with pytest.raises(Conflict):
        trash.restore(saved.note_id, 2, clock.now())


def test_confirm_cancel_and_stale_purge(trash_core):
    db, clock, _, _, trash = trash_core
    saved = make_note(trash_core)
    deleted = trash.move_to_trash(saved.note_id, 1, clock.now())
    with pytest.raises(ValidationError):
        PurgeNote(trash).execute(PurgeNoteInput(saved.note_id, 2))
    assert db.notes.count_documents({}) == 1
    with pytest.raises(Conflict):
        trash.purge_confirmed(saved.note_id, 1)
    PurgeNote(trash).execute(PurgeNoteInput(saved.note_id, deleted.note.version, True))
    assert db.notes.count_documents({}) == 0
    with pytest.raises(NotFound):
        trash.restore(saved.note_id, 2, clock.now())


@pytest.mark.parametrize(
    "field",
    ["attachment", "image_binary", "image_gridfs_id", "content_encrypted", "unknown_extension"],
)
def test_manual_and_automatic_purge_reject_future_payload(trash_core, field):
    db, clock, _, _, trash = trash_core
    now = clock.now()
    clock.value -= timedelta(days=31)
    saved = make_note(trash_core)
    trash.move_to_trash(saved.note_id, 1, clock.now())
    db.notes.update_one({"_id": ObjectId(saved.note_id)}, {"$set": {field: "unknown payload"}})
    with pytest.raises(ValidationError):
        trash.purge_confirmed(saved.note_id, 2)
    clock.value = now
    assert PurgeWorker(trash, clock).run_once().purged == 0
    assert db.notes.count_documents({}) == 1


def test_save_delete_race_has_one_cas_winner(trash_core):
    _, clock, notes, _, trash = trash_core
    saved = make_note(trash_core)
    note = notes.find_by_id(saved.note_id)
    edited = note.edited(
        title="Winner", content="changed", priority=Priority.LOW, category_id=None, now=clock.now()
    )

    def remove():
        try:
            trash.move_to_trash(saved.note_id, 1, clock.now())
            return True
        except (Conflict, NotFound):
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        update = pool.submit(notes.update_if_version, edited, 1)
        deletion = pool.submit(remove)
        assert sorted((update.result(), deletion.result())) == [False, True]


def test_restore_purge_race_has_one_winner(trash_core):
    db, clock, _, _, trash = trash_core
    saved = make_note(trash_core)
    trash.move_to_trash(saved.note_id, 1, clock.now())

    def perform(action):
        try:
            action()
            return True
        except (Conflict, NotFound):
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                perform,
                (
                    lambda: trash.restore(saved.note_id, 2, clock.now()),
                    lambda: trash.purge_confirmed(saved.note_id, 2),
                ),
            )
        )
    assert sorted(outcomes) == [False, True]
    remaining = db.notes.find_one()
    assert remaining is None or (remaining["version"] == 3 and remaining["is_deleted"] is False)


def test_retention_cutoff_and_stale_candidate(trash_core):
    db, clock, _, _, trash = trash_core
    now = clock.now()
    for age in (timedelta(days=30), timedelta(days=29, hours=23)):
        clock.value = now - age
        saved = make_note(trash_core, str(age))
        trash.move_to_trash(saved.note_id, 1, clock.now())
    clock.value = now
    report = PurgeWorker(trash, clock).run_once()
    assert report.purged == 1 and db.notes.count_documents({}) == 1
    assert PurgeWorker(trash, clock).run_once().purged == 0
    clock.value += timedelta(days=1)
    candidate = trash.expired_candidates(clock.now() - timedelta(days=30))[0]
    trash.restore(candidate.note.id, candidate.note.version, clock.now())
    with pytest.raises(Conflict):
        trash.purge_expired(candidate.note.id, candidate.note.version, clock.now())
    assert db.notes.count_documents({"is_deleted": False}) == 1


def test_trash_keyset_pages_and_namespace_guard(trash_core):
    _, clock, _, _, trash = trash_core
    for i in range(35):
        saved = make_note(trash_core, f"Note {i}")
        trash.move_to_trash(saved.note_id, 1, clock.now())
    first = trash.list_trashed(30)
    second = trash.list_trashed(30, first.next_cursor)
    assert len({row.note.id for row in (*first.items, *second.items)}) == 35
    assert second.next_cursor is None
    with pytest.raises(ValidationError):
        trash.list_trashed(20, first.next_cursor)


def test_missing_tombstone_is_not_eligible(trash_core):
    db, clock, _, _, trash = trash_core
    saved = make_note(trash_core)
    db.notes.update_one({"_id": ObjectId(saved.note_id)}, {"$set": {"is_deleted": True}})
    assert schema_report(db)["invalid_tombstones"] == 1
    assert PurgeWorker(trash, clock).run_once().purged == 0
    assert db.notes.count_documents({}) == 1
