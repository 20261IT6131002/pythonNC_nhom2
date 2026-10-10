"""Run shared Phase2 contracts with no DB/display."""

from zoneinfo import ZoneInfo

import pytest

from tests.fakes import FakeCategories, FakeClock
from tests.phase2_fakes import FakePhase2
from tests.phase2_repository_contracts import Phase2RepositoryContract


@pytest.fixture
def phase2_repositories():
    categories = FakeCategories()
    repo = FakePhase2(categories)
    return repo, categories, repo, repo, FakeClock(), ZoneInfo("UTC")


class TestFakePhase2Contract(Phase2RepositoryContract):
    """Reference port behavior."""
