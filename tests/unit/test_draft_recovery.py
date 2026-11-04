"""FR-17 model, key lifecycle and recovery decisions without Mongo or GUI."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from noteapp.application.dto.local_draft import RecoveryKind
from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.domain.errors import (
    AuthenticationFailed,
    RepositoryUnavailable,
    SecureStorageUnavailable,
    ValidationError,
)
from tests.draft_fakes import FakeDraftStore, draft
from tests.fakes import FakeClock, FakeNotes
from tests.repository_contracts import note
from tests.security_fakes import FakeSecretStore


@pytest.mark.parametrize(
    "changes",
    [
        {"draft_id": "../unsafe"},
        {"client_operation_id": "bad"},
        {"revision": True},
        {"revision": 0},
        {"base_version": 1},
        {"source_locked": 1},
        {"title": None},
        {"priority": "WRONG"},
        {"updated_at": FakeClock().now().replace(tzinfo=None)},
    ],
)
def test_invalid_models_are_rejected(changes):
    with pytest.raises(ValidationError):
        draft(**changes)


def test_draft_preserves_blank_title_and_repr_does_not_expose_content():
    snapshot = draft(title=" ")
    assert snapshot.title == " "
    assert "private-draft-marker" not in repr(snapshot)


def test_key_provisioning_is_serialized_across_provider_instances():
    secrets = FakeSecretStore()
    generated = []

    def generate():
        generated.append(True)
        return bytes(range(32))

    providers = [DraftKeyProvider(secrets, generate) for _ in range(16)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        keys = list(
            pool.map(lambda provider: provider.get_key(existing_ciphertext=False), providers)
        )

    assert len(generated) == 1
    assert keys == [bytes(range(32))] * 16


def test_missing_existing_key_is_never_regenerated_and_backend_error_is_sanitized():
    secrets = FakeSecretStore()
    provider = DraftKeyProvider(secrets, lambda: pytest.fail("Must not generate an existing key"))

    with pytest.raises(SecureStorageUnavailable):
        provider.get_key(existing_ciphertext=True)

    secrets.available = False

    with pytest.raises(SecureStorageUnavailable):
        provider.get_key(existing_ciphertext=False)


@pytest.mark.parametrize(
    "failure,kind",
    [
        (AuthenticationFailed("private"), RecoveryKind.CORRUPT),
        (ValidationError("private"), RecoveryKind.CORRUPT),
        (SecureStorageUnavailable("private"), RecoveryKind.KEY_UNAVAILABLE),
    ],
)
def test_unreadable_drafts_have_safe_classifications(failure, kind):
    store = FakeDraftStore()
    store.error = failure
    service = DraftRecoveryService(store, FakeNotes(), FakeClock())
    decision = service.recover(draft().draft_id)
    assert decision.kind == kind and decision.draft is None
    assert "private" not in repr(decision)


def test_remote_classification_preserves_local_base_version_and_owned_metadata():
    store, notes, clock = FakeDraftStore(), FakeNotes(), FakeClock()
    service = DraftRecoveryService(store, notes, clock)
    saved = notes.create(note(is_pinned=True), "create")
    snapshot = draft(note_id=saved.id, base_version=1)
    store.save_if_newer(snapshot)
    assert service.recover(snapshot.draft_id).kind == RecoveryKind.SAFE_EXISTING
    notes.items[saved.id] = replace(saved, version=2)
    decision = service.recover(snapshot.draft_id)
    assert decision.kind == RecoveryKind.REMOTE_CONFLICT
    assert decision.draft.base_version == 1 and decision.remote.is_pinned
    del notes.items[saved.id]
    assert service.recover(snapshot.draft_id).kind == RecoveryKind.REMOTE_MISSING

    def unavailable(_):
        raise RepositoryUnavailable("offline")

    notes.find_by_id = unavailable
    assert service.recover(snapshot.draft_id).kind == RecoveryKind.REMOTE_UNAVAILABLE
    assert store.get(snapshot.draft_id) == snapshot


def test_locked_drafts_are_reserved_and_never_use_the_plaintext_save_route():
    store = FakeDraftStore()
    snapshot = draft(source_locked=True)
    store.save_if_newer(snapshot)
    service = DraftRecoveryService(store, FakeNotes(), FakeClock())
    assert service.recover(snapshot.draft_id).kind == RecoveryKind.LOCKED_UNSUPPORTED
    with pytest.raises(ValidationError):
        service.autosave.execute(snapshot)


def test_invalid_existing_key_and_unacknowledged_provisioning_fail_closed():
    secrets = FakeSecretStore()
    secrets.put("draft-master-key.v1", b"wrong-size")
    provider = DraftKeyProvider(secrets, lambda: pytest.fail("Never replace an existing key"))
    with pytest.raises(SecureStorageUnavailable):
        provider.get_key(existing_ciphertext=False)

    class WrongReadback(FakeSecretStore):
        def put(self, name, value):
            super().put(name, bytes(reversed(range(32))))

    with pytest.raises(SecureStorageUnavailable):
        DraftKeyProvider(WrongReadback(), lambda: bytes(range(32))).get_key(
            existing_ciphertext=False
        )


def test_random_provider_failure_does_not_expose_details():
    def unavailable():
        raise OSError("private-random-provider-details")

    with pytest.raises(SecureStorageUnavailable) as raised:
        DraftKeyProvider(FakeSecretStore(), unavailable).get_key(existing_ciphertext=False)
    assert "private-random-provider-details" not in str(raised.value)
    assert raised.value.__cause__ is None
