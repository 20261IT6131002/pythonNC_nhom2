"""Run pin contracts without DB or GUI dependencies."""

import pytest

from tests.fakes import FakeNotes
from tests.pin_contracts import PinRepositoryContract


@pytest.fixture
def pin_notes():
    return FakeNotes()


class TestFakePinRepository(PinRepositoryContract):
    """Independent in-memory implementation of the public pin port."""
