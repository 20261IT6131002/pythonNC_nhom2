"""The single composition root. Database initialization runs in a worker."""

from dataclasses import dataclass

from pymongo import MongoClient

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_view import CategoryView
from noteapp.application.queries.list_notes import ListCategories, ListNotes
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import SystemClock, create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.views.app_window import AppWindow


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
    client = create_client(config)
    runner = TaskRunner()
    notes = MongoNoteRepository(client[config.db_name])
    categories = MongoCategoryRepository(client[config.db_name])
    clock = SystemClock()

    def initialize() -> tuple[CategoryView, ...]:
        ping(client)
        create_indexes(client[config.db_name])
        return ListCategories(categories).execute()

    try:
        window = AppWindow(
            CreateNote(notes, categories, clock),
            UpdateNote(notes, categories, clock),
            ListNotes(notes),
            runner,
            initialize,
        )
    except Exception:
        runner.close(wait=True)
        client.close()
        raise
    return Runtime(window, runner, client)
