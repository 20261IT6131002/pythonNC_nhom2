"""R1 query benchmark: 10k synthetic notes, pinned metadata, isolated test DB only."""

import argparse
import json
import os
import platform
import time
from dataclasses import replace
from datetime import timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId

from noteapp.application.dto.note_filter import SearchNotesCriteria, SortDirection, SortMode
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository, query_pipeline
from scripts.benchmark_phase2 import explain_summary, metrics, seed


def run(output: Path) -> None:
    owned_name = "noteapp_test_pin_benchmark_" + uuid4().hex
    config = Config(os.environ.get("NOTEAPP_TEST_MONGO_URI", ""), owned_name, 10000)

    with create_client(config) as client:
        ping(client)
        database = client[owned_name]

        try:
            create_indexes(database)
            categories = seed(database)
            database.notes.update_many(
                {"_id": {"$in": [ObjectId(f"{index + 1:024x}") for index in range(1, 10000, 10)]}},
                {"$set": {"is_pinned": True}},
            )
            repository = MongoSearchRepository(database, timeout_ms=10000)
            query = SearchNotes(repository, timezone.utc)
            cases = {
                "recent": SearchNotesCriteria(),
                "created_desc": SearchNotesCriteria(sort=SortMode.CREATED_AT),
                "created_asc": SearchNotesCriteria(
                    sort=SortMode.CREATED_AT, direction=SortDirection.ASC
                ),
                "priority": SearchNotesCriteria(sort=SortMode.PRIORITY),
                "category": SearchNotesCriteria(
                    sort=SortMode.CATEGORY, direction=SortDirection.ASC
                ),
                "text": SearchNotesCriteria(text="học"),
                "combined": SearchNotesCriteria(text="học", category_id=categories[0].id),
            }
            cases["recent_page2"] = replace(
                cases["recent"], cursor=query.execute(cases["recent"]).next_cursor
            )
            cases["category_page2"] = replace(
                cases["category"], cursor=query.execute(cases["category"]).next_cursor
            )
            results = {}

            for name, criteria in cases.items():
                for _ in range(5):
                    query.execute(criteria)

                samples = []
                for _ in range(20):
                    started = time.perf_counter()
                    query.execute(criteria)
                    samples.append((time.perf_counter() - started) * 1000)

                class CaptureCriteria:
                    def search(self, compiled):
                        self.compiled = compiled
                        return repository.search(compiled)

                capture = CaptureCriteria()
                SearchNotes(capture, timezone.utc).execute(criteria)
                pipeline, _ = query_pipeline(capture.compiled)
                explanation = database.command(
                    "explain",
                    {"aggregate": "notes", "pipeline": pipeline, "cursor": {}},
                    verbosity="executionStats",
                )
                results[name] = {
                    **metrics(samples),
                    "samples_ms": samples,
                    "explain": explain_summary(explanation),
                }

            report = {
                "environment": {
                    "os": platform.platform(),
                    "python": platform.python_version(),
                    "mongo": client.server_info()["version"],
                    "network": "Docker loopback",
                },
                "notes": database.notes.count_documents({}),
                "active": database.notes.count_documents({"is_deleted": False}),
                "pinned_active": database.notes.count_documents(
                    {"is_deleted": False, "is_pinned": True}
                ),
                "method": "5 warmups + 20 application/Mongo/mapping samples per query; no UI.",
                "results": results,
            }
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({name: values["p95_ms"] for name, values in results.items()}))
        finally:
            assert owned_name.startswith("noteapp_test_pin_benchmark_")
            client.drop_database(owned_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
