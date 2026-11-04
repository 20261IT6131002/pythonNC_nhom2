"""P3A-04: the fake store satisfies the shared AttachmentStore contract."""

import pytest

from tests.attachment_contracts import AttachmentStoreContract
from tests.attachment_fakes import FakeAttachmentStore


@pytest.fixture
def store():
    return FakeAttachmentStore()


class TestFakeAttachmentStore(AttachmentStoreContract):
    """Run the shared behavior against the deterministic in-memory port."""
