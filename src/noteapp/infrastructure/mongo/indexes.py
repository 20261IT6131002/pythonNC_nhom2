"""Idempotent named indexes for the minimal Phase 1 schema."""

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

from noteapp.domain.errors import RepositoryUnavailable


def create_indexes(database: Database) -> None:
    try:
        database.notes.create_index(
            [("client_operation_id", ASCENDING)],
            name="uq_notes_operation",
            unique=True,
            partialFilterExpression={"client_operation_id": {"$type": "string"}},
        )
        database.notes.create_index(
            [("is_deleted", ASCENDING), ("updated_at", DESCENDING), ("_id", DESCENDING)],
            name="idx_notes_recent",
        )
        database.categories.create_index(
            [("name_key", ASCENDING)],
            name="uq_categories_name_key",
            unique=True,
        )
    except PyMongoError:
        raise RepositoryUnavailable("Index setup was not acknowledged.") from None
