"""Identical Phase2 behavior against real Mongo adapters."""

from zoneinfo import ZoneInfo

import pytest

from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from tests.fakes import FakeClock
from tests.phase2_repository_contracts import Phase2RepositoryContract

pytestmark = pytest.mark.integration


@pytest.fixture
def phase2_repositories(mongo_database):
    db = mongo_database[0]
    return (
        MongoNoteRepository(db),
        MongoCategoryRepository(db),
        MongoSearchRepository(db),
        MongoTrashRepository(db),
        FakeClock(),
        ZoneInfo("UTC"),
    )


class TestMongoPhase2Contract(Phase2RepositoryContract):
    """Production adapters implement the same public port outcomes."""
