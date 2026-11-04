"""The single composition root. Database initialization runs in a worker."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import uuid4

from pymongo import MongoClient

from noteapp.application.commands.category import (
    CategoryTools,
    CreateCategory,
    DeleteCategory,
    RenameCategory,
    UpdateCategoryColor,
)
from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.set_reminder import CancelReminder, ReminderTools, SetReminder
from noteapp.application.commands.trash import TrashNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_view import CategoryView
from noteapp.application.queries.list_notes import ListCategories, ListNotes
from noteapp.application.queries.list_trash import ListTrash
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.application.services.attachment_service import AttachmentService
from noteapp.application.services.reminder_service import DeliveryReport, ReminderDeliveryService
from noteapp.infrastructure.attachment.file_reader import LocalImageFileReader
from noteapp.infrastructure.attachment.hybrid_store import MongoAttachmentStore
from noteapp.infrastructure.attachment.image_validator import PillowImageProcessor
from noteapp.infrastructure.attachment.reconciler import MongoAttachmentReconciler
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.local.timezone import resolve_timezone
from noteapp.infrastructure.mongo.client import SystemClock, create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.note_query_repository import MongoSearchRepository
from noteapp.infrastructure.mongo.repositories import (
    MongoCategoryRepository,
    MongoNoteAttachmentRepository,
    MongoNoteRepository,
    MongoReminderRepository,
)
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.notifications.plyer_gateway import PlyerGateway
from noteapp.infrastructure.scheduler.purge_worker import PurgeWorker
from noteapp.infrastructure.scheduler.reminder_poller import ReminderPoller
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.views.app_window import AppWindow
from noteapp.presentation.tk.views.icons import load_icon_data


@dataclass
class Runtime:
    window: AppWindow
    runner: TaskRunner
    client: MongoClient
    poller: ReminderPoller | None = None

    def close(self) -> None:
        # Stop the poll thread before the window, runner and Mongo client it depends on.
        if self.poller is not None:
            self.poller.stop()
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
    attachment_store = MongoAttachmentStore(client[config.db_name])
    trash = MongoTrashRepository(client[config.db_name], attachment_store)
    attachments = AttachmentService(
        notes,
        MongoNoteAttachmentRepository(client[config.db_name]),
        attachment_store,
        PillowImageProcessor(),
        clock,
        LocalImageFileReader(),
    )
    reconciler = MongoAttachmentReconciler(client[config.db_name])
    reminder_repository = MongoReminderRepository(client[config.db_name])
    set_reminder = SetReminder(notes, reminder_repository, clock)
    delivery = ReminderDeliveryService(reminder_repository, PlyerGateway(), clock)

    def publish_poll(report: DeliveryReport) -> None:
        if report.noteworthy:  # only changes the UI needs to see
            runner.publish("reminder_poll:" + uuid4().hex, "reminder_poll", report)

    poller = ReminderPoller(delivery.deliver_due, config.reminder_poll_seconds, publish_poll)

    def run_maintenance() -> None:
        PurgeWorker(trash, clock).run_once()
        reconciler.run_once(clock.now())

    maintenance = run_maintenance if os.environ.get("NOTEAPP_ENABLE_RETENTION") == "1" else None

    def initialize() -> tuple[CategoryView, ...]:
        ping(client)
        create_indexes(client[config.db_name])
        zone = resolve_timezone()
        search.local_timezone = set_reminder.local_timezone = zone
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
            attachments=attachments,
            categories=CategoryTools(
                CreateCategory(categories, clock),
                RenameCategory(categories),
                UpdateCategoryColor(categories),
                DeleteCategory(categories),
                ListCategories(categories),
            ),
            reminders=ReminderTools(
                set_reminder, CancelReminder(notes, reminder_repository, clock)
            ),
            reminder_scan=delivery.deliver_due,
            reminder_start=poller.start,
            reminder_stop=poller.stop,
        )
    except Exception:
        runner.close(wait=True)
        client.close()
        raise
    return Runtime(window, runner, client, poller)
