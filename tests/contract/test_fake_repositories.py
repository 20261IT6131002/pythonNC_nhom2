"""P1-06/17: ports behave correctly without Mongo or a display."""

import pytest

from tests.fakes import FakeCategories, FakeNotes
from tests.repository_contracts import RepositoryContract


@pytest.fixture
def repositories():
    return FakeNotes(), FakeCategories()


class TestFakeRepositoryContract(RepositoryContract):
    """Run the shared behavior against deterministic in-memory ports."""
