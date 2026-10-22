"""P3A-02: real Mongo category management, uniqueness races and guarded delete."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from secrets import token_hex
from uuid import uuid4

import pytest

from noteapp.domain.entities.category import Category
from noteapp.domain.errors import CategoryInUse, DuplicateCategory
from noteapp.infrastructure.mongo.models import object_id
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from tests.fakes import FakeClock
from tests.repository_contracts import note

pytestmark = pytest.mark.integration


@pytest.fixture
def repos(mongo_database):
    database = mongo_database[0]
    return MongoNoteRepository(database), MongoCategoryRepository(database), database


def make(name):
    return Category(token_hex(12), name, "#123456", FakeClock().now())


def test_concurrent_duplicate_creates_leave_exactly_one(repos):
    _, categories, _ = repos

    def attempt(name):
        try:
            categories.create(make(name))
            return "created"
        except DuplicateCategory:
            return "duplicate"

    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(attempt, ["Race", "RACE", " race ", "race"] * 2))
    assert outcomes.count("created") == 1
    assert len(categories.list_all()) == 1


def test_delete_referenced_by_trashed_note_is_rejected(repos):
    notes, categories, database = repos
    category = categories.create(make("Used"))
    saved = notes.create(note(category_id=category.id), str(uuid4()))
    database.notes.update_one(
        {"_id": object_id(saved.id)},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}},
    )
    with pytest.raises(CategoryInUse):
        categories.delete(category.id)
    assert categories.find_by_id(category.id) == category
    assert "deleting_until" not in database.categories.find_one({"_id": object_id(category.id)})


def test_expired_delete_marker_does_not_hide_category(repos):
    _, categories, database = repos
    category = categories.create(make("Stuck"))
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    database.categories.update_one(
        {"_id": object_id(category.id)},
        {"$set": {"deleting_token": "x", "deleting_until": past}},
    )
    assert categories.find_by_id(category.id) == category
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    database.categories.update_one(
        {"_id": object_id(category.id)}, {"$set": {"deleting_until": future}}
    )
    assert categories.find_by_id(category.id) is None
    assert categories.list_all() == ()


def test_delete_frees_normalized_name_for_reuse(repos):
    _, categories, _ = repos
    first = categories.create(make("Reuse"))
    categories.delete(first.id)
    assert categories.create(make("reuse")).name == "reuse"
