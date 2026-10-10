"""Native indexed search/filter and server-side category ordering/keyset pages."""

from datetime import datetime
from typing import Any

from pymongo.database import Database

from noteapp.application.dto.note_filter import CompiledNoteCriteria, SortMode
from noteapp.application.ports.note_repository import NotePage
from noteapp.application.queries.search_notes import validate_compiled
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime
from noteapp.infrastructure.mongo.models import note_from_document, object_id
from noteapp.infrastructure.mongo.query_cursor import decode_seek, encode_seek, fingerprint
from noteapp.infrastructure.mongo.repositories import database_errors


def query_pipeline(
    criteria: CompiledNoteCriteria,
) -> tuple[list[dict[str, Any]], list[tuple[str, int]]]:
    validate_compiled(criteria)
    query: dict[str, Any] = {"is_deleted": False}
    if criteria.text:
        query["$text"] = {
            "$search": criteria.text,
            "$caseSensitive": False,
            "$diacriticSensitive": False,
        }
    if criteria.category_id is not None:
        query["category_id"] = object_id(criteria.category_id)
    if criteria.priority is not None:
        query["priority"] = criteria.priority.value
    bounds = {}
    if criteria.utc_start is not None:
        bounds["$gte"] = criteria.utc_start
    if criteria.utc_end_exclusive is not None:
        bounds["$lt"] = criteria.utc_end_exclusive
    if bounds:
        query[criteria.date_field.value] = bounds
    direction = 1 if criteria.direction.value == "ASC" else -1
    fields = {
        SortMode.UPDATED_AT: [("updated_at", -1), ("_id", -1)],
        SortMode.CREATED_AT: [("created_at", direction), ("_id", direction)],
        SortMode.PRIORITY: [("priority_rank", -1), ("updated_at", -1), ("_id", -1)],
        SortMode.CATEGORY: [("category_sort_key", 1), ("_id", 1)],
    }[criteria.sort]
    pipeline = [{"$match": query}]
    if criteria.sort == SortMode.CATEGORY:
        pipeline += [
            # Join once per category, not once per matching note. A second,
            # indexed lookup retrieves only limit+1 notes from each category.
            {"$group": {"_id": "$category_id"}},
            {
                "$lookup": {
                    "from": "categories",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "_category",
                }
            },
            {
                "$set": {
                    "category_sort_key": {
                        "$ifNull": [{"$arrayElemAt": ["$_category.name_key", 0]}, ""]
                    }
                }
            },
            {"$unset": "_category"},
        ]
    if criteria.cursor is not None:
        values, note_id = decode_seek(criteria.cursor, "active_search", fingerprint(criteria))
        if len(values) != len(fields) - 1:
            raise ValidationError("Cursor sort tuple does not match.")
        converted = []
        for (field, _), value in zip(fields[:-1], values, strict=True):
            if field.endswith("_at"):
                try:
                    if not isinstance(value, str):
                        raise ValueError
                    value = utc_datetime(datetime.fromisoformat(value))
                except (ValueError, TypeError):
                    raise ValidationError("Invalid cursor timestamp.") from None
            elif field == "priority_rank":
                if type(value) is not int or value not in (1, 2, 3):
                    raise ValidationError("Invalid cursor priority.")
            elif not isinstance(value, str):
                raise ValidationError("Invalid cursor category key.")
            converted.append(value)
        converted.append(object_id(note_id))
        branches = []
        for index, (field, sign) in enumerate(fields):
            branch = {fields[i][0]: converted[i] for i in range(index)}
            branch[field] = {"$gt" if sign == 1 else "$lt": converted[index]}
            branches.append(branch)
        if criteria.sort == SortMode.CATEGORY:
            pipeline.append({"$match": {"category_sort_key": {"$gte": converted[0]}}})
        else:
            pipeline.append({"$match": {"$or": branches}})
    if criteria.sort == SortMode.CATEGORY:
        conditions: list[dict[str, Any]] = [
            {"$eq": [{"$ifNull": ["$category_id", None]}, "$$category"]}
        ]
        if criteria.cursor is not None:
            conditions.append(
                {
                    "$or": [
                        {"$gt": ["$$key", converted[0]]},
                        {"$gt": ["$_id", converted[1]]},
                    ]
                }
            )
        note_match = {**query, "$expr": {"$and": conditions}}
        pipeline += [
            {
                "$lookup": {
                    "from": "notes",
                    "let": {"category": "$_id", "key": "$category_sort_key"},
                    "pipeline": [
                        {"$match": note_match},
                        {"$sort": {"_id": 1}},
                        {"$limit": criteria.limit + 1},
                    ],
                    "as": "_notes",
                }
            },
            {"$unwind": "$_notes"},
            {
                "$replaceRoot": {
                    "newRoot": {
                        "$mergeObjects": [
                            "$_notes",
                            {"category_sort_key": "$category_sort_key"},
                        ]
                    }
                }
            },
        ]
    pipeline += [{"$sort": dict(fields)}, {"$limit": criteria.limit + 1}]
    return pipeline, fields


class MongoSearchRepository:
    def __init__(self, database: Database, timeout_ms: int = 3000) -> None:
        self.database, self.timeout_ms = database, timeout_ms

    @database_errors
    def search(self, criteria: CompiledNoteCriteria) -> NotePage:
        pipeline, fields = query_pipeline(criteria)
        documents = list(self.database.notes.aggregate(pipeline, maxTimeMS=self.timeout_ms))
        selected = documents[: criteria.limit]
        items = tuple(note_from_document(document) for document in selected)
        cursor = None
        if len(documents) > criteria.limit:
            last = selected[-1]
            keys = [
                last[field].isoformat() if isinstance(last[field], datetime) else last[field]
                for field, _ in fields[:-1]
            ]
            cursor = encode_seek("active_search", fingerprint(criteria), keys, str(last["_id"]))
        return NotePage(items, cursor)
