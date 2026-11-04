"""SEC-K02/03: native provider selection and fail-closed secret operations."""

import traceback
from types import SimpleNamespace

import keyring
import pytest

from noteapp.domain.errors import SecureStorageUnavailable
from noteapp.infrastructure.security import keyring_store
from tests.security_fakes import MemoryNativeBackend


@pytest.mark.parametrize("operation", ["get", "put", "delete"])
def test_native_errors_are_sanitized_without_any_file_fallback(
    monkeypatch, tmp_path, caplog, operation
):
    marker = "private-provider-secret-marker"
    backend = MemoryNativeBackend()
    backend.error = RuntimeError(marker)
    monkeypatch.setattr(keyring_store, "_load_native_backend", lambda: backend)
    monkeypatch.chdir(tmp_path)
    store = keyring_store.KeyringSecretStore()

    calls = {
        "get": lambda: store.get("draft-key"),
        "put": lambda: store.put("draft-key", marker.encode()),
        "delete": lambda: store.delete("draft-key"),
    }

    with pytest.raises(SecureStorageUnavailable) as raised:
        calls[operation]()

    assert list(tmp_path.iterdir()) == []
    assert not backend.values
    assert marker not in repr(store)
    assert marker not in repr(raised.value)
    assert marker not in "".join(traceback.format_exception(raised.value))
    assert marker not in caplog.text
    assert raised.value.__cause__ is None


def test_construction_is_lazy_and_loading_failure_is_not_a_missing_key(monkeypatch, tmp_path):
    calls = []

    def unavailable():
        calls.append(True)
        raise ImportError("private-backend-details")

    monkeypatch.setattr(keyring_store, "_load_native_backend", unavailable)
    monkeypatch.chdir(tmp_path)
    store = keyring_store.KeyringSecretStore()
    assert not calls

    with pytest.raises(SecureStorageUnavailable):
        store.get("missing-key")

    assert calls == [True]
    assert list(tmp_path.iterdir()) == []


def test_write_and_delete_must_be_verified(monkeypatch):
    backend = MemoryNativeBackend()
    monkeypatch.setattr(keyring_store, "_load_native_backend", lambda: backend)
    store = keyring_store.KeyringSecretStore()
    backend.write_acknowledged = False

    with pytest.raises(SecureStorageUnavailable):
        store.put("key", b"new-key")

    backend.write_acknowledged = True
    store.put("key", b"existing-key")
    backend.delete_acknowledged = False

    with pytest.raises(SecureStorageUnavailable):
        store.delete("key")

    assert store.get("key") == b"existing-key"


@pytest.mark.parametrize(
    "stored", ["", "plaintext-value", "noteapp-key-v1:!", "noteapp-key-v1:", 1]
)
def test_corrupt_key_is_never_treated_as_missing_or_regenerated(monkeypatch, stored):
    backend = MemoryNativeBackend()
    backend.values[keyring_store.KEYRING_SERVICE, "key"] = stored
    monkeypatch.setattr(keyring_store, "_load_native_backend", lambda: backend)

    with pytest.raises(SecureStorageUnavailable):
        keyring_store.KeyringSecretStore().get("key")

    assert backend.values[keyring_store.KEYRING_SERVICE, "key"] == stored


def test_configured_or_global_backends_are_not_consulted(monkeypatch, tmp_path):
    backend = MemoryNativeBackend()
    monkeypatch.setattr(keyring_store, "_load_native_backend", lambda: backend)
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyrings.alt.file.PlaintextKeyring")
    monkeypatch.chdir(tmp_path)

    def forbidden():
        pytest.fail("The global/configured keyring must never be selected.")

    monkeypatch.setattr(keyring, "get_keyring", forbidden)
    store = keyring_store.KeyringSecretStore()
    store.put("key", b"native-only-key")

    assert store.get("key") == b"native-only-key"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "platform_name,module_name,class_name",
    [
        ("win32", "keyring.backends.Windows", "WinVaultKeyring"),
        ("darwin", "keyring.backends.macOS", "Keyring"),
        ("linux", "keyring.backends.SecretService", "Keyring"),
    ],
)
def test_only_the_native_provider_for_the_os_is_selected(
    monkeypatch, platform_name, module_name, class_name
):
    backend = MemoryNativeBackend()
    imports = []

    def load(name):
        imports.append(name)
        return SimpleNamespace(**{class_name: lambda: backend})

    monkeypatch.setattr(keyring_store.sys, "platform", platform_name)
    monkeypatch.setattr(keyring_store, "import_module", load)

    assert keyring_store._load_native_backend() is backend
    assert imports == [module_name]

    if platform_name == "win32":
        assert backend.persist == "local machine"


def test_unsupported_os_or_unavailable_native_backend_has_no_fallback(monkeypatch):
    monkeypatch.setattr(keyring_store.sys, "platform", "unsupported-os")

    with pytest.raises(SecureStorageUnavailable):
        keyring_store.KeyringSecretStore().get("key")

    backend = MemoryNativeBackend()
    backend.priority = 0
    monkeypatch.setattr(keyring_store.sys, "platform", "linux")
    monkeypatch.setattr(
        keyring_store, "import_module", lambda _: SimpleNamespace(Keyring=lambda: backend)
    )

    with pytest.raises(SecureStorageUnavailable):
        keyring_store.KeyringSecretStore().get("key")
