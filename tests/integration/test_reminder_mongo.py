"""P3B-02/05/08/09 on real Mongo: contract, atomic claim, races, lifecycle and outage."""

import threading
from datetime import timedelta
from uuid import uuid4

import pytest
from bson import ObjectId
from pymongo import MongoClient

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.set_reminder import CancelReminder, SetReminder
from noteapp.application.commands.trash import TrashNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_input import (
    CancelReminderInput,
    CreateNoteInput,
    Priority,
    PurgeNoteInput,
    RestoreNoteInput,
    SetReminderInput,
    TrashNoteInput,
    UpdateNoteInput,
)
from noteapp.application.services.reminder_service import ReminderDeliveryService
from noteapp.domain.entities.reminder import ReminderStatus
from noteapp.domain.errors import RepositoryUnavailable, ValidationError
from noteapp.infrastructure.mongo.indexes import plan_indexes
from noteapp.infrastructure.mongo.repositories import (
    MongoCategoryRepository,
    MongoNoteRepository,
    MongoReminderRepository,
)
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.scheduler.reminder_poller import ReminderPoller
from tests.fakes import FakeClock
from tests.reminder_contracts import ReminderRepositoryContract
from tests.reminder_fakes import FakeGateway

pytestmark = pytest.mark.integration


class World:
    def __init__(self, database):
        self.database = database
        self.clock = FakeClock()
        self.notes = MongoNoteRepository(database)
        self.reminders = MongoReminderRepository(database)
        self.trash_repo = MongoTrashRepository(database)
        self.gateway = FakeGateway()
        self.delivery = ReminderDeliveryService(self.reminders, self.gateway, self.clock)
        self.set = SetReminder(self.notes, self.reminders, self.clock)
        self.cancel = CancelReminder(self.notes, self.reminders, self.clock)
        self.create = CreateNote(self.notes, MongoCategoryRepository(database), self.clock)

    def trash(self, note_id):
        current = self.notes.find_by_id(note_id)
        self.trash_repo.move_to_trash(note_id, current.version, self.clock.now())

    def new_note(self, title="Họp nhóm"):
        return self.create.execute(
            CreateNoteInput(title, "nội dung", Priority.MEDIUM, None, str(uuid4()))
        )

    def remind(self, title="Họp nhóm", due_in=timedelta(minutes=5)):
        saved = self.new_note(title)
        view = self.set.execute(SetReminderInput(saved.note_id, 1, self.clock.now() + due_in))
        return view

    def advance(self, **delta):
        self.clock.value += timedelta(**delta)


@pytest.fixture
def world(mongo_database):
    return World(mongo_database[0])


class TestMongoReminderRepository(ReminderRepositoryContract):
    """Shared contract against the real adapter."""


def test_schema_is_embedded_utc_and_hides_internal_claim_fields(world):
    view = world.remind()
    document = world.database.notes.find_one({"title": "Họp nhóm"})
    assert set(document["reminder"]) == {"due_at", "status", "updated_at"}
    assert document["reminder"]["due_at"].tzinfo is not None
    world.advance(minutes=5)
    world.delivery.deliver_due()
    delivered = world.database.notes.find_one({"title": "Họp nhóm"})["reminder"]
    assert set(delivered) == {"due_at", "status", "updated_at", "delivered_at"}
    assert world.notes.find_by_id(view.note_id).reminder.status is ReminderStatus.DELIVERED


def test_due_index_exists_matches_plan_and_serves_the_claim_query(world):
    assert dict(plan_indexes(world.database))["idx_notes_reminder_due"] == "matching"
    world.remind()
    now = world.clock.now()
    plan = world.database.notes.find(
        {"is_deleted": False, "reminder.status": "ACTIVE", "reminder.due_at": {"$lte": now}}
    ).explain()
    assert "idx_notes_reminder_due" in str(plan["queryPlanner"]["winningPlan"])


def test_only_one_of_many_concurrent_claimers_wins(world):
    world.remind()
    world.advance(minutes=5)
    barrier, claims = threading.Barrier(12), []

    def worker(n):
        barrier.wait()
        now = world.clock.now()
        claims.append(world.reminders.claim_next_due(now, now + timedelta(minutes=2), f"t{n}", 3))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(12)]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    assert sum(claim is not None for claim in claims) == 1


def test_concurrent_pollers_deliver_each_reminder_exactly_once(world):
    ids = {world.remind(f"Nhắc {n}").note_id for n in range(6)}
    world.advance(minutes=10)
    services = [
        ReminderDeliveryService(world.reminders, gateway, world.clock)
        for gateway in (FakeGateway() for _ in range(4))
    ]
    barrier, reports = threading.Barrier(4), []

    def worker(service):
        barrier.wait()
        reports.append(service.deliver_due())

    threads = [threading.Thread(target=worker, args=(s,)) for s in services]
    [t.start() for t in threads]
    [t.join(20) for t in threads]
    delivered = [item.note_id for report in reports for item in report.delivered]
    assert sorted(delivered) == sorted(ids)
    assert sum(len(s.gateway.sent) for s in services) == 6


def race_cancel_against_poll(world, title):
    view = world.remind(title)
    world.advance(minutes=5)
    barrier, outcome = threading.Barrier(2), {}

    def cancel():
        barrier.wait()
        outcome["cancel"] = world.cancel.execute(CancelReminderInput(view.note_id, view.version))

    def poll():
        barrier.wait()
        outcome["report"] = world.delivery.deliver_due()

    threads = [threading.Thread(target=cancel), threading.Thread(target=poll)]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    return view, outcome


def test_cancel_versus_poll_race_has_a_clear_winner(world):
    """Repeated on one database: each round races a user cancel against a poll."""
    for round_ in range(15):
        sent_before = len(world.gateway.sent)
        view, outcome = race_cancel_against_poll(world, f"Đua {round_}")
        final = world.notes.find_by_id(view.note_id).reminder.status
        if final is ReminderStatus.CANCELLED:
            # cancel committed: a poll that lost must not have marked anything delivered
            delivered = outcome["report"].delivered
            assert not any(item.note_id == view.note_id for item in delivered)
        else:
            # the poll won completely, so cancel became a no-op on the delivered reminder
            assert final is ReminderStatus.DELIVERED
            assert outcome["cancel"].reminder.status == "DELIVERED"
            assert len(world.gateway.sent) == sent_before + 1


def test_reschedule_during_delivery_never_marks_the_old_due_time(world):
    view = world.remind()
    world.advance(minutes=5)
    now = world.clock.now()
    claimed = world.reminders.claim_next_due(now, now + timedelta(minutes=2), "tok", 3)
    world.set.execute(SetReminderInput(view.note_id, view.version, now + timedelta(hours=2)))
    assert not world.reminders.mark_delivered(view.note_id, claimed.claim_token, now)
    world.advance(minutes=30)
    assert world.delivery.deliver_due().delivered == ()
    world.advance(hours=2)
    assert len(world.delivery.deliver_due().delivered) == 1


def test_full_journey_trash_restore_missed_delivery_and_purge(world):
    view = world.remind("Hành trình")
    world.advance(minutes=10)
    world.trash(view.note_id)
    assert world.delivery.deliver_due().delivered == () and world.gateway.sent == []
    restored = RestoreNote(world.trash_repo, world.clock).execute(
        RestoreNoteInput(view.note_id, world.trash_repo.collection.find_one()["version"])
    )
    assert restored.reminder.status == "ACTIVE"  # overdue ACTIVE survives restore
    restarted = ReminderDeliveryService(world.reminders, world.gateway, world.clock)  # new process
    assert [i.note_id for i in restarted.deliver_due().delivered] == [view.note_id]
    assert restarted.deliver_due().delivered == ()
    assert len(world.gateway.sent) == 1
    current = world.notes.find_by_id(view.note_id)
    TrashNote(world.trash_repo, world.clock).execute(TrashNoteInput(view.note_id, current.version))
    trashed = world.database.notes.find_one({"_id": world.trash_repo.collection.find_one()["_id"]})
    PurgeNote(world.trash_repo).execute(PurgeNoteInput(view.note_id, trashed["version"], True))
    assert world.database.notes.count_documents({}) == 0


def test_list_returns_the_reminder_and_text_edits_keep_it(world):
    view = world.remind("Tìm thấy")
    assert world.notes.list_recent(10).items[0].reminder.status is ReminderStatus.ACTIVE
    categories = MongoCategoryRepository(world.database)
    edited = UpdateNote(world.notes, categories, world.clock).execute(
        UpdateNoteInput(
            view.note_id, "Tiêu đề mới", "nội dung mới", Priority.HIGH, None, view.version
        )
    )
    assert edited.reminder == view.reminder
    assert world.notes.find_by_id(view.note_id).reminder.due_at == view.reminder.due_at


def test_database_outage_is_contained_by_service_and_poller(world):
    bad = MongoClient(
        "mongodb://127.0.0.1:1", serverSelectionTimeoutMS=150, connectTimeoutMS=150, tz_aware=True
    )
    try:
        repository = MongoReminderRepository(bad["noteapp_test_unreachable"])
        with pytest.raises(RepositoryUnavailable):
            repository.claim_next_due(
                world.clock.now(), world.clock.now() + timedelta(minutes=1), "t", 3
            )
        service = ReminderDeliveryService(repository, world.gateway, world.clock)
        results = []
        poller = ReminderPoller(service.deliver_due, 0.05, results.append)
        poller.start()
        assert threading.Event().wait(0.6) is False
        assert poller.stop() and poller.running is False
        assert service.deliver_due().unavailable
        assert world.gateway.sent == []
    finally:
        bad.close()


def test_invalid_attempt_limit_is_rejected(world):
    with pytest.raises(ValidationError):
        world.reminders.claim_next_due(world.clock.now(), world.clock.now(), "t", 0)


def test_phase3_journey_image_and_reminder_survive_trash_restore_and_purge_cleans_both(world):
    from io import BytesIO

    from PIL import Image

    from noteapp.application.dto.note_input import AttachImageInput
    from noteapp.application.services.attachment_service import AttachmentService
    from noteapp.infrastructure.attachment.hybrid_store import MongoAttachmentStore
    from noteapp.infrastructure.attachment.image_validator import PillowImageProcessor
    from noteapp.infrastructure.mongo.repositories import MongoNoteAttachmentRepository

    store = MongoAttachmentStore(world.database, now=world.clock.now)
    trash = MongoTrashRepository(world.database, store)
    images = AttachmentService(
        world.notes,
        MongoNoteAttachmentRepository(world.database),
        store,
        PillowImageProcessor(),
        world.clock,
    )
    out = BytesIO()
    Image.new("RGB", (40, 20), (1, 2, 3)).save(out, format="PNG")
    view = world.remind("Hành trình đủ bộ", due_in=timedelta(minutes=5))
    with_image = images.attach(
        AttachImageInput(view.note_id, view.version, out.getvalue(), "a.png")
    )
    assert with_image.reminder == view.reminder and with_image.version == view.version + 1

    TrashNote(trash, world.clock).execute(TrashNoteInput(view.note_id, with_image.version))
    world.advance(minutes=10)
    assert world.delivery.deliver_due().delivered == ()  # trashed notes stay silent
    trashed = world.database.notes.find_one({"_id": ObjectId(view.note_id)})
    restored = RestoreNote(trash, world.clock).execute(
        RestoreNoteInput(view.note_id, trashed["version"])
    )
    assert restored.attachment == with_image.attachment and restored.reminder.status == "ACTIVE"
    assert [i.note_id for i in world.delivery.deliver_due().delivered] == [view.note_id]
    assert world.database.attachment_blobs.count_documents({}) == 1

    current = world.notes.find_by_id(view.note_id)
    TrashNote(trash, world.clock).execute(TrashNoteInput(view.note_id, current.version))
    trashed = world.database.notes.find_one({"_id": ObjectId(view.note_id)})
    PurgeNote(trash).execute(PurgeNoteInput(view.note_id, trashed["version"], True))
    assert world.database.notes.count_documents({}) == 0
    assert world.database.attachment_blobs.count_documents({}) == 0
