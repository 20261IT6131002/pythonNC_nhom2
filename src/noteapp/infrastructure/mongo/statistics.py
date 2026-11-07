"""Aggregate only active-note metadata and join names after grouping."""

from pymongo.database import Database

from noteapp.application.queries.note_statistics import StatisticsRow
from noteapp.domain.policies.note_validation import validate_priority
from noteapp.infrastructure.mongo.repositories import database_errors


class MongoNoteStatisticsRepository:
    def __init__(self, database: Database, timeout_ms: int = 3000) -> None:
        self.collection = database.notes
        self.timeout_ms = timeout_ms

    @database_errors
    def count_active(self) -> tuple[StatisticsRow, ...]:
        pipeline = [
            {"$match": {"is_deleted": False}},
            {
                "$group": {
                    "_id": {
                        "category": {"$ifNull": ["$category_id", None]},
                        "priority": "$priority",
                    },
                    "count": {"$sum": 1},
                }
            },
            {
                "$lookup": {
                    "from": "categories",
                    "localField": "_id.category",
                    "foreignField": "_id",
                    "as": "category",
                }
            },
            {"$project": {"count": 1, "name": {"$arrayElemAt": ["$category.name", 0]}}},
        ]
        return tuple(
            StatisticsRow(
                str(row["_id"]["category"]) if row["_id"]["category"] is not None else None,
                row.get("name"),
                validate_priority(row["_id"]["priority"]),
                row["count"],
            )
            for row in self.collection.aggregate(pipeline, maxTimeMS=self.timeout_ms)
        )
