"""P2-05/06: real native text/filter/sort/seek and non-destructive indexes."""

from dataclasses import replace
from datetime import date, timedelta
from secrets import token_hex
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from bson import ObjectId

from noteapp.application.commands.create import CreateNote
from noteapp.application.dto.note_filter import SearchNotesCriteria, SortDirection, SortMode
from noteapp.application.dto.note_input import CreateNoteInput
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import RepositoryUnavailable, ValidationError
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.mongo.indexes import create_indexes, plan_indexes
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from tests.fakes import FakeClock

pytestmark = pytest.mark.integration


@pytest.fixture
def search_core(mongo_database):
    db = mongo_database[0]
    clock = FakeClock()
    categories = MongoCategoryRepository(db)
    create = CreateNote(MongoNoteRepository(db), categories, clock)
    query = SearchNotes(MongoSearchRepository(db), ZoneInfo("UTC"))
    return db, create, query, categories, clock


def create_note(create, **changes):
    return create.execute(
        replace(
            CreateNoteInput("Học tập", "Ôn tập kiến thức", Priority.MEDIUM, None, str(uuid4())),
            **changes,
        )
    )


def test_text_title_content_phrase_and_accent(search_core):
    _, create, query, _, _ = search_core
    title = create_note(create, content="")
    content = create_note(create, title="Other", content="Học tập mỗi ngày")
    other = create_note(create, title="Else", content="kiến thức")
    for text in ("học", "hoc", '"học tập"', '"hoc tap"', "HỌC"):
        assert {item.note_id for item in query.execute(SearchNotesCriteria(text=text)).items} == {
            title.note_id,
            content.note_id,
        }
    assert [item.note_id for item in query.execute(SearchNotesCriteria(text="kiến")).items] == [
        other.note_id
    ]


def test_intersection_and_excludes_deleted(search_core):
    db, create, query, categories, clock = search_core
    category = categories.create(Category(token_hex(12), "Study", "#123456", clock.now()))
    yes = create_note(create, category_id=category.id, priority=Priority.HIGH)
    create_note(create, priority=Priority.HIGH)
    hidden = create_note(create, category_id=category.id, priority=Priority.HIGH)
    db.notes.update_one(
        {
            "title": hidden.title,
            "client_operation_id": {"$exists": True},
            "_id": ObjectId(hidden.note_id),
        },
        {"$set": {"is_deleted": True}},
    )
    result = query.execute(
        SearchNotesCriteria(
            text="học",
            category_id=category.id,
            priority=Priority.HIGH,
            start_date=date(2026, 10, 9),
            end_date=date(2026, 10, 9),
        )
    )
    assert [item.note_id for item in result.items] == [yes.note_id]
    assert not query.execute(SearchNotesCriteria(category_id=token_hex(12))).items


@pytest.mark.parametrize(
    ("sort", "direction"),
    [
        (SortMode.UPDATED_AT, SortDirection.DESC),
        (SortMode.CREATED_AT, SortDirection.ASC),
        (SortMode.CREATED_AT, SortDirection.DESC),
        (SortMode.PRIORITY, SortDirection.DESC),
        (SortMode.CATEGORY, SortDirection.ASC),
    ],
)
def test_all_orders_paginate_without_duplicates(search_core, sort, direction):
    _, create, query, categories, clock = search_core
    catalog = [
        categories.create(Category(token_hex(12), name, "#123456", clock.now()))
        for name in ("Zebra", "Alpha")
    ]
    names = {item.id: item.name_key for item in catalog}
    saved = []
    for i in range(65):
        clock.value += timedelta(milliseconds=i % 3)
        saved.append(
            create_note(
                create,
                title=f"Học {i}",
                category_id=catalog[i % 2].id if i % 3 else None,
                priority=list(Priority)[i % 3],
            )
        )
    keys = {
        SortMode.UPDATED_AT: lambda n: (n.updated_at, n.note_id),
        SortMode.CREATED_AT: lambda n: (n.created_at, n.note_id),
        SortMode.PRIORITY: lambda n: (n.priority.rank, n.updated_at, n.note_id),
        SortMode.CATEGORY: lambda n: (names.get(n.category_id, ""), n.note_id),
    }
    expected = sorted(saved, key=keys[sort], reverse=direction == SortDirection.DESC)
    command = SearchNotesCriteria(sort=sort, direction=direction)
    seen = []
    for _ in range(3):
        page = query.execute(command)
        seen.extend(page.items)
        command = replace(command, cursor=page.next_cursor)
        if page.next_cursor is None:
            break
    assert [item.note_id for item in seen] == [item.note_id for item in expected]


def test_cursor_is_query_bound_and_new_insert_does_not_repeat(search_core):
    _, create, query, _, clock = search_core
    for i in range(4):
        create_note(create, title=f"Học {i}")
    command = SearchNotesCriteria(limit=2)
    first = query.execute(command)
    clock.value += timedelta(seconds=1)
    new = create_note(create)
    second = query.execute(replace(command, cursor=first.next_cursor))
    assert len({n.note_id for n in (*first.items, *second.items)}) == 4
    assert new.note_id not in {n.note_id for n in second.items}
    with pytest.raises(ValidationError):
        query.execute(replace(command, cursor=first.next_cursor, text="other"))
    for cursor in ("bad", "e30=", "x" * 2049):
        with pytest.raises(ValidationError):
            query.execute(replace(command, cursor=cursor))


def test_dry_run_and_index_conflict_do_not_write(search_core):
    db = search_core[0]
    before = db.notes.index_information()
    assert all(status == "matching" for _, status in plan_indexes(db))
    assert db.notes.index_information() == before
    create_indexes(db)
    assert db.notes.index_information() == before
    assert before["idx_notes_text"]["default_language"] == "none"
    db.notes.create_index("deleted_at", name="unexpected_ttl", expireAfterSeconds=0)
    with pytest.raises(RepositoryUnavailable):
        create_indexes(db)
    assert "unexpected_ttl" in db.notes.index_information()
