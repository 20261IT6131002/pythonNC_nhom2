"""P2-15/16: real Unicode, native expressions, day boundaries and live category names."""

import unicodedata
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from bson import ObjectId

from noteapp.application.dto.note_filter import (
    DateField,
    SearchNotesCriteria,
    SortDirection,
    SortMode,
)
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.errors import RepositoryUnavailable
from noteapp.infrastructure.mongo.indexes import create_indexes, plan_indexes
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository
from tests.integration.test_search import create_note
from tests.integration.test_search import search_core as search_core

pytestmark = pytest.mark.integration


def ids(query, **criteria):
    return {n.note_id for n in query.execute(SearchNotesCriteria(**criteria)).items}


def test_native_or_exclusion_unicode_and_literals(search_core):
    _, create, query, _, _ = search_core
    study = create_note(create, title="HỌC tập", content="")
    work = create_note(create, title="Công việc", content="")
    nfd = create_note(create, title=unicodedata.normalize("NFD", "Học tập"), content="")
    assert ids(query, text="học công") == {study.note_id, work.note_id, nfd.note_id}
    assert ids(query, text="học -công") == {study.note_id, nfd.note_id}
    assert ids(query, text='"""') == set()
    assert ids(query, text="$where") == set()
    assert ids(query, text='{"$ne": null}') == set()
    assert ids(query, text="họ") == set()  # whole tokens, not substring matching
    assert ids(query, text="học") == {study.note_id, nfd.note_id}


def test_local_day_exact_utc_bounds_and_date_field(search_core):
    db, create, _, _, clock = search_core
    query = SearchNotes(MongoSearchRepository(db), ZoneInfo("Asia/Ho_Chi_Minh"))
    midnight = datetime(2026, 10, 8, 17, tzinfo=timezone.utc)
    saved = []
    for delta in (-1, 0, 86400 - 1, 86400):
        clock.value = midnight + timedelta(seconds=delta)
        saved.append(create_note(create, title=f"Day {delta}"))
    criteria = SearchNotesCriteria(start_date=date(2026, 10, 9), end_date=date(2026, 10, 9))
    expected = {saved[1].note_id, saved[2].note_id}
    assert {n.note_id for n in query.execute(criteria).items} == expected
    assert ids(query, start_date=date(2026, 10, 9)) == expected | {saved[3].note_id}
    assert ids(query, end_date=date(2026, 10, 9)) == expected | {saved[0].note_id}
    db.notes.update_one({"_id": ObjectId(saved[0].note_id)}, {"$set": {"updated_at": midnight}})
    assert {n.note_id for n in query.execute(criteria).items} == expected | {saved[0].note_id}
    assert {
        n.note_id for n in query.execute(replace(criteria, date_field=DateField.CREATED_AT)).items
    } == expected


def test_category_rename_and_missing_reference(search_core):
    from secrets import token_hex

    from noteapp.domain.entities.category import Category

    db, create, query, categories, clock = search_core
    alpha = categories.create(Category(token_hex(12), "Alpha", "#123456", clock.now()))
    beta = categories.create(Category(token_hex(12), "Beta", "#123456", clock.now()))
    a = create_note(create, category_id=alpha.id)
    b = create_note(create, category_id=beta.id)
    command = SearchNotesCriteria(sort=SortMode.CATEGORY, direction=SortDirection.ASC)
    assert [n.note_id for n in query.execute(command).items] == [a.note_id, b.note_id]
    db.categories.update_one(
        {"_id": ObjectId(alpha.id)}, {"$set": {"name": "Zebra", "name_key": "zebra"}}
    )
    assert [n.note_id for n in query.execute(command).items] == [b.note_id, a.note_id]
    assert ids(query, category_id=alpha.id) == {a.note_id}
    db.categories.delete_one({"_id": ObjectId(alpha.id)})
    assert [n.note_id for n in query.execute(command).items] == [a.note_id, b.note_id]


def test_partial_named_index_is_not_mistaken_for_full_index(search_core):
    db = search_core[0]
    db.notes.drop_index("idx_notes_recent")  # fixture-owned database only
    db.notes.create_index(
        [("is_deleted", 1), ("updated_at", -1), ("_id", -1)],
        name="idx_notes_recent",
        partialFilterExpression={"priority": "HIGH"},
    )
    before = db.notes.index_information()
    assert dict(plan_indexes(db))["idx_notes_recent"] == "incompatible"
    with pytest.raises(RepositoryUnavailable):
        create_indexes(db)
    assert db.notes.index_information() == before


def test_category_text_pages_with_null_dangling_and_missing_category(search_core):
    from secrets import token_hex

    from noteapp.domain.entities.category import Category

    db, create, query, categories, clock = search_core
    alpha = categories.create(Category(token_hex(12), "Alpha", "#123456", clock.now()))
    zebra = categories.create(Category(token_hex(12), "Zebra", "#123456", clock.now()))
    # Unknown references simulate an older imported dataset; normal create validates them.
    saved = []
    names = {alpha.id: "alpha", zebra.id: "zebra"}
    for i in range(65):
        row = create_note(
            create, title=f"Học tập {i}", category_id=(None, alpha.id, zebra.id)[i % 3]
        )
        if i % 7 == 0:
            db.notes.update_one(
                {"_id": ObjectId(row.note_id)}, {"$set": {"category_id": ObjectId(token_hex(12))}}
            )
            row = replace(row, category_id=None)
        saved.append(row)
    db.notes.update_one({"_id": ObjectId(saved[0].note_id)}, {"$unset": {"category_id": ""}})
    create_note(create, title="Non matching", content="Else")
    criteria = SearchNotesCriteria(
        text="học", sort=SortMode.CATEGORY, direction=SortDirection.ASC, limit=7
    )
    expected = sorted(saved, key=lambda n: (names.get(n.category_id, ""), n.note_id))
    seen, cursor = [], None
    for _ in range(10):
        page = query.execute(replace(criteria, cursor=cursor))
        seen.extend(page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert cursor is None
    assert [n.note_id for n in seen] == [n.note_id for n in expected]
