"""Pure fake contract: core consumers can test without OS credentials or a display."""

import pytest

from noteapp.domain.errors import SecureStorageUnavailable
from tests.security_contracts import SecretStoreContract
from tests.security_fakes import FakeSecretStore


@pytest.fixture
def secret_store():
    return FakeSecretStore()


class TestFakeSecretStore(SecretStoreContract):
    """Run the same secret-store behavior as the native adapter tests."""


def test_unavailable_is_distinct_from_a_successfully_missing_key(secret_store):
    secret_store.put("key", b"existing-key")
    secret_store.available = False

    for operation in (
        lambda: secret_store.get("key"),
        lambda: secret_store.put("key", b"replacement-key"),
        lambda: secret_store.delete("key"),
    ):
        with pytest.raises(SecureStorageUnavailable):
            operation()

    secret_store.available = True
    assert secret_store.get("key") == b"existing-key"
