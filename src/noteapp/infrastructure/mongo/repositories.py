"""Mongo ports with idempotent insert, bounded pages and atomic CAS."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from noteapp.application.ports.note_repository import NotePage
from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import DuplicateCategory, RepositoryUnavailable, ValidationError
from noteapp.infrastructure.mongo.models import (
    category_from_document,
    category_to_document,
    decode_cursor,
    encode_cursor,
    note_from_document,
    note_to_document,
    object_id,
)

P = ParamSpec("P")
R = TypeVar("R")


def database_errors(method: Callable[P, R]) -> Callable[P, R]:
    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return method(*args, **kwargs)
        except PyMongoError:
            raise RepositoryUnavailable("Database operation was not acknowledged.") from None

    return wrapped


class MongoNoteRepository:
    def __init__(self, database: Database) -> None:
        self.collection = database.notes

    @database_errors
    def create(self, note: Note, operation_id: str) -> Note:
        document = note_to_document(note, operation_id)
        try:
            self.collection.insert_one(document)
        except DuplicateKeyError:
            existing = self.collection.find_one({"client_operation_id": operation_id})
            if existing is None:
                raise RepositoryUnavailable("Create could not be acknowledged.") from None
            return note_from_document(existing)
        # Return the actual persisted representation (BSON timestamp precision).
        persisted = self.collection.find_one({"_id": document["_id"]})
        if persisted is None:
            raise RepositoryUnavailable("Create could not be read back.")
        return note_from_document(persisted)

    @database_errors
    def find_by_id(self, note_id: str) -> Note | None:
        document = self.collection.find_one({"_id": object_id(note_id), "is_deleted": False})
        return note_from_document(document) if document is not None else None

    @database_errors
    def list_recent(self, limit: int, cursor: str | None = None) -> NotePage:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError("Page size must be between 1 and 100.")
        query = {"is_deleted": False}
        if cursor is not None:
            timestamp, note_id = decode_cursor(cursor)
            query["$or"] = [
                {"updated_at": {"$lt": timestamp}},
                {"updated_at": timestamp, "_id": {"$lt": note_id}},
            ]
        documents = list(
            self.collection.find(query)
            .sort([("updated_at", DESCENDING), ("_id", DESCENDING)])
            .limit(limit + 1)
        )
        items = tuple(note_from_document(document) for document in documents[:limit])
        return NotePage(items, encode_cursor(items[-1]) if len(documents) > limit else None)

    @database_errors
    def update_if_version(self, note: Note, expected_version: int) -> bool:
        if type(expected_version) is not int or expected_version < 1:
            raise ValidationError("Expected version must be a positive integer.")
        if note.version != expected_version + 1:
            raise ValidationError("Update must advance version by one.")
        result = self.collection.update_one(
            {"_id": object_id(note.id), "version": expected_version, "is_deleted": False},
            {
                "$set": {
                    "title": note.title,
                    "content_plain": note.content,
                    "priority": note.priority.value,
                    "priority_rank": note.priority.rank,
                    "category_id": object_id(note.category_id) if note.category_id else None,
                    "updated_at": note.updated_at,
                },
                "$inc": {"version": 1},
            },
        )
        return result.matched_count == 1


class MongoCategoryRepository:
    def __init__(self, database: Database) -> None:
        self.collection = database.categories

    @database_errors
    def create(self, category: Category) -> Category:
        try:
            self.collection.insert_one(category_to_document(category))
        except DuplicateKeyError:
            raise DuplicateCategory("Category name already exists.") from None
        return category

    @database_errors
    def find_by_id(self, category_id: str) -> Category | None:
        document = self.collection.find_one({"_id": object_id(category_id)})
        return category_from_document(document) if document is not None else None

    @database_errors
    def list_all(self) -> tuple[Category, ...]:
        return tuple(
            category_from_document(document)
            for document in self.collection.find().sort("name_key", 1)
        )
