"""Non-mutating schema preflight; tombstones migrate lazily in atomic writes."""

from pymongo.database import Database

from noteapp.domain.errors import ValidationError
from noteapp.infrastructure.mongo.models import note_from_document
from noteapp.infrastructure.mongo.repositories import database_errors


@database_errors
def locked_schema_report(database: Database) -> dict[str, int]:
    invalid = 0
    candidates = database.notes.find(
        {
            "$or": [
                {"schema_version": {"$nin": [1, 2]}},
                {"content_encrypted": {"$exists": True}},
                {"is_locked": {"$exists": True}},
                {"content_plain": {"$exists": False}},
            ]
        }
    )
    for document in candidates:
        try:
            note_from_document(document)
        except (ValidationError, TypeError, KeyError):
            invalid += 1
    return {
        "invalid_note_representation": invalid,
        "schema_v3": database.notes.count_documents({"schema_version": 3}),
    }


@database_errors
def schema_report(database: Database) -> dict[str, int]:
    return {
        "schema_v1": database.notes.count_documents({"schema_version": 1}),
        "schema_v2": database.notes.count_documents({"schema_version": 2}),
        **pin_schema_report(database),
        "invalid_tombstones": database.notes.count_documents(
            {"is_deleted": True, "deleted_at": {"$not": {"$type": "date"}}}
        ),
    }


@database_errors
def pin_schema_report(database: Database) -> dict[str, int]:
    """Report exact BSON types; arrays containing booleans are invalid too."""
    return {
        "missing_is_pinned": database.notes.count_documents({"is_pinned": {"$exists": False}}),
        "invalid_is_pinned": database.notes.count_documents(
            {
                "is_pinned": {"$exists": True},
                "$expr": {"$ne": [{"$type": "$is_pinned"}, "bool"]},
            }
        ),
        "pinned_true": database.notes.count_documents({"is_pinned": True}),
        "pinned_false": database.notes.count_documents({"is_pinned": False}),
    }


@database_errors
def normalize_pinned(database: Database) -> int:
    """R1-01: fill missing flags only; refuse invalid existing values without writes."""
    if pin_schema_report(database)["invalid_is_pinned"]:
        raise ValidationError("Invalid is_pinned values require manual data review.")

    result = database.notes.update_many(
        {"is_pinned": {"$exists": False}},
        {"$set": {"is_pinned": False}},
    )
    return result.modified_count


def require_pinned_schema(database: Database) -> None:
    report = pin_schema_report(database)
    if report["missing_is_pinned"] or report["invalid_is_pinned"]:
        raise ValidationError("Run the R1 pin migration before opening active lists.")
