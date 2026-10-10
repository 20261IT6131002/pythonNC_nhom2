"""Non-mutating schema preflight; tombstones migrate lazily in atomic writes."""

from pymongo.database import Database

from noteapp.infrastructure.mongo.repositories import database_errors


@database_errors
def schema_report(database: Database) -> dict[str, int]:
    return {
        "schema_v1": database.notes.count_documents({"schema_version": 1}),
        "schema_v2": database.notes.count_documents({"schema_version": 2}),
        "invalid_tombstones": database.notes.count_documents(
            {"is_deleted": True, "deleted_at": {"$not": {"$type": "date"}}}
        ),
    }
