"""FR-12 real Mongo: CAS, migration, filters and all keyset ordering partitions."""

import base64
import json
from dataclasses import replace
from datetime import timedelta, timezone
from secrets import token_hex

import pytest
from bson import ObjectId

from noteapp.application.commands.set_pinned import SetPinned
from noteapp.application.dto.note_filter import SearchNotesCriteria, SortDirection, SortMode
from noteapp.application.dto.note_input import SetPinnedInput
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import NotFound, ValidationError
from noteapp.domain.value_objects.attachment_ref import AttachmentRef
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.mongo.migrations import (
    normalize_pinned,
    pin_schema_report,
    require_pinned_schema,
)
from noteapp.infrastructure.mongo.models import (
    attachment_to_document,
    decode_cursor,
    note_from_document,
    note_to_document,
)
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from tests.fakes import FakeClock
from tests.pin_contracts import PinRepositoryContract
from tests.repository_contracts import note

pytestmark = pytest.mark.integration


@pytest.fixture
def pin_notes(mongo_database):
    return MongoNoteRepository(mongo_database[0])


class TestMongoPinRepository(PinRepositoryContract):
    """The same public port contract as the fake implementation."""


def test_pin_trash_restore_and_independent_read(mongo_database):
    database = mongo_database[0]
    notes = MongoNoteRepository(database)
    trash = MongoTrashRepository(database)
    original = notes.create(note(), "original")
    pinned = SetPinned(notes).execute(SetPinnedInput(original.id, 1, True))
    assert MongoNoteRepository(database).find_by_id(original.id).is_pinned

    moved = trash.move_to_trash(original.id, pinned.version, original.updated_at)
    assert moved.note.is_pinned
    with pytest.raises(NotFound):
        SetPinned(notes).execute(SetPinnedInput(original.id, moved.note.version, False))
    assert not notes.set_pinned_if_version(moved.note.with_pinned(False), moved.note.version)

    restored = trash.restore(original.id, moved.note.version, original.updated_at)
    assert restored.is_pinned
    assert notes.find_by_id(original.id).is_pinned


def test_pin_does_not_replace_attachment_reminder_or_delivery_claim(mongo_database):
    database = mongo_database[0]
    notes = MongoNoteRepository(database)
    original = notes.create(note(), "with-metadata")
    attachment = AttachmentRef("INLINE", "opaque-image", "image/png", 42, "a" * 64, "image.png")
    database.notes.update_one(
        {"_id": ObjectId(original.id)},
        {
            "$set": {
                "attachment": attachment_to_document(attachment),
                "reminder": {
                    "due_at": original.updated_at + timedelta(days=1),
                    "updated_at": original.updated_at,
                    "status": "ACTIVE",
                    "claim_token": "ongoing-delivery",
                    "claim_until": original.updated_at + timedelta(minutes=2),
                    "attempts": 1,
                },
            }
        },
    )
    before = database.notes.find_one({"_id": ObjectId(original.id)})

    SetPinned(notes).execute(SetPinnedInput(original.id, original.version, True))

    after = database.notes.find_one({"_id": ObjectId(original.id)})
    assert after == {**before, "is_pinned": True, "version": 2}


def test_migration_plan_apply_idempotence_and_legacy_read(mongo_database):
    database = mongo_database[0]
    original = note()
    document = note_to_document(original, "legacy")
    document.pop("is_pinned")
    document["is_deleted"] = True  # trash must be normalized too
    database.notes.insert_one(document)
    before = database.notes.find_one({})

    assert note_from_document(before).is_pinned is False
    assert pin_schema_report(database)["missing_is_pinned"] == 1
    assert database.notes.find_one({}) == before  # plan is read-only
    with pytest.raises(ValidationError):
        require_pinned_schema(database)

    assert normalize_pinned(database) == 1
    assert normalize_pinned(database) == 0
    require_pinned_schema(database)
    assert database.notes.find_one({}) == {**before, "is_pinned": False}


@pytest.mark.parametrize("invalid", [0, 1, "true", None, [False], {}])
def test_migration_refuses_invalid_types_without_partial_writes(mongo_database, invalid):
    database = mongo_database[0]
    database.notes.insert_many(
        [
            {"_id": ObjectId(), "is_pinned": invalid},
            {"_id": ObjectId()},
        ]
    )
    before = list(database.notes.find({}).sort("_id"))

    assert pin_schema_report(database)["invalid_is_pinned"] == 1
    with pytest.raises(ValidationError):
        normalize_pinned(database)
    assert list(database.notes.find({}).sort("_id")) == before


SORTS = [
    (SortMode.UPDATED_AT, SortDirection.DESC),
    (SortMode.CREATED_AT, SortDirection.DESC),
    (SortMode.CREATED_AT, SortDirection.ASC),
    (SortMode.PRIORITY, SortDirection.DESC),
    (SortMode.CATEGORY, SortDirection.ASC),
]


def collect(query, criteria):
    seen = []
    for _ in range(100):
        page = query.execute(criteria)
        seen.extend(page.items)
        if page.next_cursor is None:
            return seen
        criteria = replace(criteria, cursor=page.next_cursor)
    pytest.fail("Pagination did not terminate.")


@pytest.fixture
def mixed(mongo_database):
    database = mongo_database[0]
    notes = MongoNoteRepository(database)
    categories = MongoCategoryRepository(database)
    now = FakeClock().now()
    alpha = categories.create(Category(token_hex(12), "Alpha", "#123456", now))
    zebra = categories.create(Category(token_hex(12), "Zebra", "#123456", now))
    names = {None: "", alpha.id: "alpha", zebra.id: "zebra"}
    originals = []

    for index in range(60):
        timestamp = now + timedelta(days=index // 20, seconds=index // 3)
        original = note(
            title="needle" if index % 4 else "unmatched",
            content="",
            category_id=(None, alpha.id, zebra.id)[index % 3],
            priority=(Priority.HIGH, Priority.MEDIUM, Priority.LOW)[index % 3],
            created_at=timestamp,
            updated_at=timestamp + timedelta(seconds=60 - index // 2),
            is_pinned=index % 5 < 2,
        )
        originals.append(notes.create(original, str(index)))

    query = SearchNotes(MongoSearchRepository(database), timezone.utc)
    return database, notes, query, originals, names


def expected_order(items, mode, direction, names):
    keys = {
        SortMode.UPDATED_AT: lambda item: (item.updated_at, item.id),
        SortMode.CREATED_AT: lambda item: (item.created_at, item.id),
        SortMode.PRIORITY: lambda item: (item.priority.rank, item.updated_at, item.id),
        SortMode.CATEGORY: lambda item: (names.get(item.category_id, ""), item.id),
    }
    ordered = sorted(items, key=keys[mode], reverse=direction == SortDirection.DESC)
    return sorted(ordered, key=lambda item: item.is_pinned, reverse=True)


@pytest.mark.parametrize("mode,direction", SORTS)
@pytest.mark.parametrize("filter_kind", ["none", "text", "category", "priority", "date", "all"])
def test_tc_adv_001_all_sorts_filters_and_partition_pages(mixed, mode, direction, filter_kind):
    _, _, query, originals, names = mixed
    criteria = SearchNotesCriteria(sort=mode, direction=direction, limit=7)

    if filter_kind in ("text", "all"):
        criteria = replace(criteria, text="needle")
    if filter_kind in ("category", "all"):
        criteria = replace(criteria, category_id=originals[1].category_id)
    if filter_kind in ("priority", "all"):
        criteria = replace(criteria, priority=Priority.MEDIUM)
    if filter_kind in ("date", "all"):
        selected_day = originals[0].created_at.date() + timedelta(days=1)
        criteria = replace(criteria, start_date=selected_day, end_date=selected_day)

    matching = [
        item
        for item in originals
        if (not criteria.text or item.title == "needle")
        and (criteria.category_id is None or item.category_id == criteria.category_id)
        and (criteria.priority is None or item.priority == criteria.priority)
        and (criteria.start_date is None or item.updated_at.date() >= criteria.start_date)
        and (criteria.end_date is None or item.updated_at.date() <= criteria.end_date)
    ]
    expected = expected_order(matching, mode, direction, names)
    actual = collect(query, criteria)
    assert [item.note_id for item in actual] == [item.id for item in expected]
    assert len({item.note_id for item in actual}) == len(actual)


def test_tc_adv_002_unpin_returns_to_selected_order(mixed):
    _, notes, query, originals, names = mixed
    original = next(item for item in originals if not item.is_pinned)
    command = SetPinned(notes)
    pinned = command.execute(SetPinnedInput(original.id, original.version, True))
    command.execute(SetPinnedInput(original.id, pinned.version, False))

    for mode, direction in SORTS:
        criteria = SearchNotesCriteria(sort=mode, direction=direction, limit=7)
        actual = collect(query, criteria)
        expected = expected_order(originals, mode, direction, names)
        assert [item.note_id for item in actual] == [item.id for item in expected]


@pytest.mark.parametrize("bad", [1, 0, "true", None])
def test_query_rejects_corrupted_partition_key(mixed, bad):
    _, _, query, _, _ = mixed
    criteria = SearchNotesCriteria(limit=7)
    cursor = query.execute(criteria).next_cursor
    payload = json.loads(base64.urlsafe_b64decode(cursor))
    payload["keys"][0] = bad
    cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    with pytest.raises(ValidationError):
        query.execute(replace(criteria, cursor=cursor))


def test_old_recent_cursor_is_rejected():
    old = base64.urlsafe_b64encode(
        json.dumps([FakeClock().now().isoformat(), token_hex(12)]).encode()
    ).decode()
    with pytest.raises(ValidationError):
        decode_cursor(old)
