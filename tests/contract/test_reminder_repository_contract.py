"""P3B-02: the fake repository obeys the shared ReminderRepository contract."""

from types import SimpleNamespace

import pytest

from noteapp.application.ports.notification_gateway import NotificationGateway
from noteapp.application.ports.reminder_repository import ReminderRepository
from tests.fakes import FakeClock
from tests.reminder_contracts import ReminderRepositoryContract
from tests.reminder_fakes import FakeGateway, FakeReminderNotes


@pytest.fixture
def world():
    notes = FakeReminderNotes()
    return SimpleNamespace(notes=notes, reminders=notes, trash=notes.trash, clock=FakeClock())


class TestFakeReminderRepository(ReminderRepositoryContract):
    """Run the shared behavior against the in-memory port."""


def test_fakes_satisfy_the_runtime_protocols():
    assert isinstance(FakeReminderNotes(), ReminderRepository)
    assert isinstance(FakeGateway(), NotificationGateway)
