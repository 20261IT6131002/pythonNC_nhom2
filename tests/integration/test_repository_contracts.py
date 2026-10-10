"""P1-13/18: same port behavior against a fixture-owned real Mongo database."""

import pytest

from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from tests.repository_contracts import RepositoryContract

pytestmark = pytest.mark.integration


@pytest.fixture
def repositories(mongo_database):
    database = mongo_database[0]
    return MongoNoteRepository(database), MongoCategoryRepository(database)


class TestMongoRepositoryContract(RepositoryContract):
    """Run the shared behavior against the concrete adapter, without mocks."""
