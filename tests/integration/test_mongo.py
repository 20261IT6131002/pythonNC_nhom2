"""P1-AC04/06/07/08/09: real Mongo, never a mock database."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from secrets import token_hex
from uuid import uuid4

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_filter import ListNotesInput
from noteapp.application.dto.note_input import CreateNoteInput, UpdateNoteInput
from noteapp.application.queries.list_notes import ListNotes
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import (
    Conflict,
    DuplicateCategory,
    RepositoryUnavailable,
    ValidationError,
)
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from tests.fakes import FakeClock

pytestmark = pytest.mark.integration


@pytest.fixture
def mongo_core(mongo_database):
    database, config = mongo_database
    notes, categories, clock = (
        MongoNoteRepository(database),
        MongoCategoryRepository(database),
        FakeClock(),
    )
    return database, config, notes, categories, clock, CreateNote(notes, categories, clock)


def command(**changes):
    return replace(
        CreateNoteInput("Ghi chú", "Nội dung", Priority.MEDIUM, None, str(uuid4())), **changes
    )


def test_create_persists_after_new_client(mongo_core):
    database, config, _, categories, clock, create = mongo_core
    category = categories.create(Category(token_hex(12), "Study", "#123456", clock.now()))
    view = create.execute(command(category_id=category.id, priority=Priority.HIGH))
    with create_client(config) as new_client:
        reloaded = MongoNoteRepository(new_client[config.db_name]).find_by_id(view.note_id)
    assert reloaded.content == "Nội dung"
    assert reloaded.category_id == category.id
    assert reloaded.priority == Priority.HIGH
    assert reloaded.created_at.utcoffset() == timedelta(0)
    document = database.notes.find_one()
    assert document["priority_rank"] == 3
    assert document["schema_version"] == 1


def test_retry_create_idempotent_under_concurrency(mongo_core):
    database, _, _, _, _, create = mongo_core
    input_note = command()
    with ThreadPoolExecutor(max_workers=4) as pool:
        views = list(pool.map(lambda _: create.execute(input_note), range(8)))
    assert len({view.note_id for view in views}) == 1
    assert database.notes.count_documents({}) == 1
    assert create.execute(replace(input_note, title="Retry")) == views[0]


def test_atomic_update_version_conflict(mongo_core):
    _, _, notes, categories, clock, create = mongo_core
    view = create.execute(command())
    clock.value += timedelta(seconds=1)
    current = notes.find_by_id(view.note_id)
    one = current.edited(
        title="First", content="1", priority=Priority.HIGH, category_id=None, now=clock.now()
    )
    two = current.edited(
        title="Second", content="2", priority=Priority.LOW, category_id=None, now=clock.now()
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda note: notes.update_if_version(note, 1), (one, two)))
    assert sorted(outcomes) == [False, True]
    persisted = notes.find_by_id(view.note_id)
    assert persisted.version == 2
    assert persisted.updated_at > current.updated_at
    with pytest.raises(Conflict):
        UpdateNote(notes, categories, clock).execute(
            UpdateNoteInput(view.note_id, "Stale", "stale", Priority.LOW, None, 1)
        )
    assert notes.find_by_id(view.note_id) == persisted


def test_update_ack_and_utc(mongo_core):
    _, _, notes, categories, clock, create = mongo_core
    view = create.execute(command())
    clock.value += timedelta(seconds=1)
    updated = UpdateNote(notes, categories, clock).execute(
        UpdateNoteInput(view.note_id, "Edited", "text", Priority.LOW, None, 1)
    )
    assert updated.version == 2
    persisted = notes.find_by_id(view.note_id)
    assert persisted.version == updated.version
    assert persisted.updated_at.utcoffset() == timedelta(0)


def test_category_normalized_unique(mongo_core):
    _, _, _, categories, clock, _ = mongo_core
    categories.create(Category(token_hex(12), "Study", "#123456", clock.now()))
    with pytest.raises(DuplicateCategory):
        categories.create(Category(token_hex(12), " study ", "#654321", clock.now()))
    assert len(categories.list_all()) == 1


def test_indexes_idempotent_and_no_ttl(mongo_core):
    database = mongo_core[0]
    before = database.notes.index_information()
    create_indexes(database)
    assert database.notes.index_information() == before
    assert all("expireAfterSeconds" not in index for index in before.values())
    assert before["uq_notes_operation"]["unique"]
    assert database.categories.index_information()["uq_categories_name_key"]["unique"]


def test_recent_list_stable_pagination(mongo_core):
    database, _, notes, _, _, create = mongo_core
    for i in range(65):
        create.execute(command(title=f"Note {i}"))
    hidden = create.execute(command(title="Hidden"))
    database.notes.update_one({"title": hidden.title}, {"$set": {"is_deleted": True}})
    seen, cursor = [], None
    while True:
        page = ListNotes(notes).execute(ListNotesInput(30, cursor))
        assert len(page.items) <= 30
        seen.extend(note.note_id for note in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 65
    expected = [
        str(item["_id"])
        for item in database.notes.find({"is_deleted": False}).sort(
            [("updated_at", -1), ("_id", -1)]
        )
    ]
    assert seen == expected


@pytest.mark.parametrize("note_id", ["", "$where", "bad", {"$ne": None}])
def test_invalid_id_rejected(mongo_core, note_id):
    with pytest.raises(ValidationError):
        mongo_core[2].find_by_id(note_id)


@pytest.mark.parametrize("cursor", ["bad", "e30=", "W251bGwsbnVsbF0=", "x" * 513])
def test_invalid_cursor_rejected(mongo_core, cursor):
    with pytest.raises(ValidationError):
        mongo_core[2].list_recent(30, cursor)


def test_db_unavailable_mapped():
    config = Config("mongodb://127.0.0.1:1", "noteapp_test_unavailable", 100)
    with create_client(config) as client, pytest.raises(RepositoryUnavailable) as error:
        MongoNoteRepository(client[config.db_name]).list_recent(30)
    assert "127.0.0.1" not in str(error.value)
