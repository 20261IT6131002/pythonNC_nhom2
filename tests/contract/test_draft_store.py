"""Same DraftStore semantics with a core-only fake and real AES-GCM encrypted files."""

import pytest

from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.infrastructure.local.encrypted_draft_store import EncryptedLocalDraftStore
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from tests.draft_contracts import DraftStoreContract
from tests.draft_fakes import FakeDraftStore
from tests.security_fakes import FakeSecretStore


@pytest.fixture
def draft_store(request, tmp_path):
    if request.param == "fake":
        yield FakeDraftStore()
        return

    keys = DraftKeyProvider(FakeSecretStore(), lambda: bytes(range(32)))
    store = EncryptedLocalDraftStore(tmp_path / "drafts", AesGcmCipher(), keys)

    try:
        yield store
    finally:
        store.close()


@pytest.mark.parametrize("draft_store", ["fake", "encrypted"], indirect=True)
class TestDraftStore(DraftStoreContract):
    """No Mongo or screen is needed to validate local persistence correctness."""
