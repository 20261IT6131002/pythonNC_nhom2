"""The single composition root. Database initialization runs in a worker."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from pymongo import MongoClient

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.trash import TrashNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_view import CategoryView
from noteapp.application.queries.list_notes import ListCategories, ListNotes
from noteapp.application.queries.list_trash import ListTrash
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.local.timezone import resolve_timezone
from noteapp.infrastructure.mongo.client import SystemClock, create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.scheduler.purge_worker import PurgeWorker
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.views.app_window import AppWindow
from noteapp.presentation.tk.views.icons import load_icon_data


@dataclass
class Runtime:
    window: AppWindow
    runner: TaskRunner
    client: MongoClient

    def close(self) -> None:
        self.window.close()
        self.runner.close(wait=True)
        self.client.close()


def build_runtime(config: Config | None = None) -> Runtime:
    config = config if config is not None else Config.from_env()
    with ThreadPoolExecutor(max_workers=1) as startup_pool:
        icon_data = startup_pool.submit(load_icon_data).result()
    client = create_client(config)
    runner = TaskRunner()
    notes = MongoNoteRepository(client[config.db_name])
    categories = MongoCategoryRepository(client[config.db_name])
    clock = SystemClock()
    search = SearchNotes(MongoSearchRepository(client[config.db_name], config.timeout_ms), None)
    trash = MongoTrashRepository(client[config.db_name])
    maintenance = (
        PurgeWorker(trash, clock).run_once
        if os.environ.get("NOTEAPP_ENABLE_RETENTION") == "1"
        else None
    )

    def initialize() -> tuple[CategoryView, ...]:
        ping(client)
        create_indexes(client[config.db_name])
        search.local_timezone = resolve_timezone()
        return ListCategories(categories).execute()

    try:
        window = AppWindow(
            CreateNote(notes, categories, clock),
            UpdateNote(notes, categories, clock),
            ListNotes(notes),
            runner,
            initialize,
            search=search,
            trash=TrashNote(trash, clock),
            restore=RestoreNote(trash, clock),
            purge=PurgeNote(trash),
            list_trash=ListTrash(trash),
            icon_data=icon_data,
            maintenance=maintenance,
        )
    except Exception:
        runner.close(wait=True)
        client.close()
        raise
    return Runtime(window, runner, client)
