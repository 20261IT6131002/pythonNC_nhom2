"""P2-16/18: isolated 10k native-search/real-Tk benchmark, never developer data."""

import argparse
import json
import math
import os
import platform
import random
import sys
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import ttkbootstrap as ttk
from bson import json_util

from noteapp.application.dto.note_filter import SearchNotesCriteria, SortDirection, SortMode
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.models import category_to_document, note_to_document
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository, query_pipeline
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.async_bridge.ui_event_pump import UIEventPump
from noteapp.presentation.tk.state.list_state import ListState
from noteapp.presentation.tk.views.note_list import NoteList

SEED = 20261010


def percentile(samples, fraction):
    return sorted(samples)[max(0, math.ceil(len(samples) * fraction) - 1)]


def metrics(samples):
    return {f"p{int(p * 100)}_ms": round(percentile(samples, p), 3) for p in (0.5, 0.95, 0.99)}


def seed(database):
    rng = random.Random(SEED)
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    categories = [
        Category(f"{i + 20000:024x}", name, "#2563EB", now)
        for i, name in enumerate(("Học tập", "Công việc", "Cá nhân", "Straße"))
    ]
    database.categories.insert_many([category_to_document(c) for c in categories])
    documents = []
    for i in range(10000):
        created = now - timedelta(days=i % 90, seconds=i % 86400)
        updated = created + timedelta(hours=i % 5)
        priority = list(Priority)[i % 3]
        category_id = categories[rng.randrange(len(categories))].id if i % 5 else None
        note = Note(
            f"{i + 1:024x}",
            f"{('Học tập', 'Công việc', 'Kế hoạch', 'Lịch họp')[i % 4]} {i}",
            "Ôn tập Python và tiếng Việt. Ghi lại ý tưởng và tiến độ. " * (1 + i % 4),
            priority,
            category_id,
            1,
            created,
            updated,
        )
        doc = note_to_document(note, f"benchmark-{i}")
        if i % 20 == 0:
            doc.update(is_deleted=True, deleted_at=now - timedelta(days=31), schema_version=2)
        documents.append(doc)
    database.notes.insert_many(documents)
    return categories


def explain_summary(value):
    stages, indexes, totals = set(), set(), []

    def visit(node):
        if isinstance(node, dict):
            if "stage" in node:
                stages.add(node["stage"])
            if "indexName" in node:
                indexes.add(node["indexName"])
            if "executionStats" in node:
                stats = node["executionStats"]
                totals.append(
                    {
                        key: stats.get(key)
                        for key in (
                            "nReturned",
                            "totalKeysExamined",
                            "totalDocsExamined",
                            "executionTimeMillis",
                        )
                    }
                )
            if "indexesUsed" in node:
                indexes.update(node["indexesUsed"])
            if "usedDisk" in node:
                totals.append(
                    {
                        key: node.get(key)
                        for key in (
                            "nReturned",
                            "totalDocsExamined",
                            "totalKeysExamined",
                            "usedDisk",
                        )
                    }
                )
            for key, child in node.items():
                if key != "rejectedPlans":
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return {"stages": sorted(stages), "indexes": sorted(indexes), "execution": totals}


def run(output):
    uri = os.environ.get("NOTEAPP_TEST_MONGO_URI", "")
    owned_name = "noteapp_test_benchmark_" + uuid4().hex
    config = Config(uri, owned_name, 3000)
    with create_client(config) as client:
        ping(client)
        database = client[owned_name]
        root = None
        runner = None
        pump = None
        view = None
        try:
            create_indexes(database)
            categories = seed(database)
            repo = MongoSearchRepository(database)
            query = SearchNotes(repo, ZoneInfo("Asia/Ho_Chi_Minh"))
            cases = {
                "recent": SearchNotesCriteria(),
                "native_text": SearchNotesCriteria(text="học"),
                "category_filter": SearchNotesCriteria(category_id=categories[0].id),
                "priority_sort": SearchNotesCriteria(sort=SortMode.PRIORITY),
                "category_sort": SearchNotesCriteria(
                    sort=SortMode.CATEGORY, direction=SortDirection.ASC
                ),
                "category_text": SearchNotesCriteria(
                    text="học", sort=SortMode.CATEGORY, direction=SortDirection.ASC
                ),
                "combined": SearchNotesCriteria(
                    text="học",
                    category_id=categories[0].id,
                    priority=Priority.HIGH,
                    start_date=date(2026, 8, 1),
                    end_date=date(2026, 10, 10),
                ),
                "rare_text": SearchNotesCriteria(text="9997"),
                "no_match": SearchNotesCriteria(text="nothasnotoken2026"),
            }
            category_first = query.execute(cases["category_text"])
            cases["category_text_page2"] = replace(
                cases["category_text"], cursor=category_first.next_cursor
            )
            for i in range(20):
                query.execute(list(cases.values())[i % len(cases)])
            db_samples = {name: [] for name in cases}
            explanations = {}
            pipelines = {}
            for name, criteria in cases.items():
                for _ in range(10):
                    start = time.perf_counter()
                    query.execute(criteria)
                    db_samples[name].append((time.perf_counter() - start) * 1000)

                class Capture:
                    def search(self, criteria):
                        self.criteria = criteria
                        return repo.search(criteria)

                capture = Capture()
                SearchNotes(capture, query.local_timezone).execute(criteria)
                pipeline, _ = query_pipeline(capture.criteria)
                pipelines[name] = json.loads(json_util.dumps(pipeline))
                explanations[name] = explain_summary(
                    database.command(
                        "explain",
                        {"aggregate": "notes", "pipeline": pipeline, "cursor": {}},
                        verbosity="executionStats",
                    )
                )
            root = ttk.Window(themename="litera")
            root.geometry("1200x760")
            view = NoteList(root, lambda _: True, lambda: None, lambda: None)
            view.pack(fill="both", expand=True)
            root.update()
            runner = TaskRunner(max_workers=1)
            completions = {}

            def dispatch(event):
                if not event.result.ok:
                    raise RuntimeError("Benchmark query failed.")
                view.render(ListState(items=event.result.value.items))
                root.update_idletasks()
                completions[event.request_id] = time.perf_counter()

            pump = UIEventPump(root, runner, dispatch)
            pump.start()
            ui_samples = {name: [] for name in cases}
            for i in range(100):
                name = list(cases)[i % len(cases)]
                request_id = str(i)
                started = time.perf_counter()
                assert runner.submit(
                    request_id, "benchmark", lambda c=cases[name]: query.execute(c)
                )
                deadline = started + 10
                while request_id not in completions and time.perf_counter() < deadline:
                    root.update()
                    time.sleep(0.001)
                if request_id not in completions:
                    raise RuntimeError("Desktop benchmark timed out.")
                ui_samples[name].append((completions[request_id] - started) * 1000)
            result = {
                "seed": SEED,
                "notes": 10000,
                "active": 9500,
                "warmups": 20,
                "db_samples": 100,
                "ui_samples": 100,
                "environment": {
                    "os": platform.platform(),
                    "python": sys.version.split()[0],
                    "processor": platform.processor(),
                    "logical_cpus": os.cpu_count(),
                    "mongo": client.server_info()["version"],
                    "network": "Docker loopback",
                    "tk": str(root.tk.call("info", "patchlevel")),
                },
                "method": "DB=application+Mongo+mapping; UI=worker+50ms pump+30 cards+layout. "
                "300ms input debounce excluded. Synthetic text corpus; visible real Tk.",
                "query_metrics": {name: metrics(values) for name, values in db_samples.items()},
                "ui_metrics": {name: metrics(values) for name, values in ui_samples.items()},
                "raw_db_ms": db_samples,
                "raw_ui_ms": ui_samples,
                "explain": explanations,
                "pipelines_extended_json": pipelines,
                "index_names": sorted(database.notes.index_information()),
            }
            result["db_overall"] = metrics([x for values in db_samples.values() for x in values])
            result["ui_overall"] = metrics([x for values in ui_samples.values() for x in values])
            output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps({key: result[key] for key in ("db_overall", "ui_overall")}))
        finally:
            if pump is not None:
                pump.close()
            if view is not None:
                view.close()
            if runner is not None:
                runner.close(wait=True)
            if root is not None:
                root.destroy()
                ttk.Style.instance = None
            assert owned_name.startswith("noteapp_test_benchmark_") and config.db_name == owned_name
            client.drop_database(owned_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
