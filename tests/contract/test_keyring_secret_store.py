"""SEC-K01: native adapter follows the same contract as the core-only fake."""

import pytest

from noteapp.infrastructure.security import keyring_store
from tests.security_contracts import SecretStoreContract
from tests.security_fakes import MemoryNativeBackend


@pytest.fixture
def secret_store(monkeypatch):
    backend = MemoryNativeBackend()
    monkeypatch.setattr(keyring_store, "_load_native_backend", lambda: backend)
    return keyring_store.KeyringSecretStore()


class TestKeyringSecretStore(SecretStoreContract):
    """Exercise the real byte encoding, validation and verification with native API doubles."""
