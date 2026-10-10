"""Additive named indexes with non-mutating preflight and incompatible-index guard."""

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

from noteapp.domain.errors import RepositoryUnavailable

INDEX_SPECS = (
    (
        "notes",
        "uq_notes_operation",
        [("client_operation_id", ASCENDING)],
        {"unique": True, "partialFilterExpression": {"client_operation_id": {"$type": "string"}}},
    ),
    (
        "notes",
        "idx_notes_recent",
        [("is_deleted", ASCENDING), ("updated_at", DESCENDING), ("_id", DESCENDING)],
        {},
    ),
    ("categories", "uq_categories_name_key", [("name_key", ASCENDING)], {"unique": True}),
    (
        "notes",
        "idx_notes_text",
        [("title", "text"), ("content_plain", "text")],
        {"default_language": "none"},
    ),
    (
        "notes",
        "idx_notes_category_recent",
        [("is_deleted", 1), ("category_id", 1), ("updated_at", -1), ("_id", -1)],
        {},
    ),
    (
        "notes",
        "idx_notes_priority",
        [("is_deleted", 1), ("priority_rank", -1), ("updated_at", -1), ("_id", -1)],
        {},
    ),
    ("notes", "idx_notes_created", [("is_deleted", 1), ("created_at", -1), ("_id", -1)], {}),
)


def plan_indexes(database: Database) -> tuple[tuple[str, str], ...]:
    try:
        report = []
        for collection, name, keys, options in INDEX_SPECS:
            existing = database[collection].index_information()
            found = existing.get(name)
            if found is None:
                status = "missing"
                if name == "idx_notes_text" and any(
                    "weights" in item for item in existing.values()
                ):
                    status = "incompatible"
            else:
                match = found.get("key") == keys
                if name == "idx_notes_text":
                    match = found.get("weights") == {"title": 1, "content_plain": 1}
                match = match and all(found.get(key) == value for key, value in options.items())
                match = (
                    match
                    and not found.get("expireAfterSeconds")
                    and bool(found.get("unique", False)) == bool(options.get("unique", False))
                )
                status = "matching" if match else "incompatible"
            report.append((name, status))
        if any(
            "expireAfterSeconds" in item for item in database.notes.index_information().values()
        ):
            report.append(("notes_ttl", "incompatible"))
        return tuple(report)
    except PyMongoError:
        raise RepositoryUnavailable("Index preflight was not acknowledged.") from None


def create_indexes(database: Database) -> None:
    try:
        if any(status == "incompatible" for _, status in plan_indexes(database)):
            raise RepositoryUnavailable("Existing indexes need independent migration review.")
        for collection, name, keys, options in INDEX_SPECS:
            database[collection].create_index(keys, name=name, **options)
    except PyMongoError:
        raise RepositoryUnavailable("Index setup was not acknowledged.") from None
