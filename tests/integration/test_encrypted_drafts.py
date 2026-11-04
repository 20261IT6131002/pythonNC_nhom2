"""Real encrypted files and fault injection; native keys are deterministic test-only ports."""

import json
from dataclasses import replace

import pytest

from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.domain.errors import (
    AuthenticationFailed,
    SecureStorageUnavailable,
    ValidationError,
)
from noteapp.infrastructure.local import encrypted_draft_store
from noteapp.infrastructure.local.draft_serializers import (
    decode_draft_payload,
    decode_draft_wrapper,
    encode_draft_payload,
    encode_draft_wrapper,
)
from noteapp.infrastructure.local.encrypted_draft_store import EncryptedLocalDraftStore
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from tests.draft_fakes import draft
from tests.security_fakes import FakeSecretStore


def make_store(directory, secrets):
    return EncryptedLocalDraftStore(
        directory, AesGcmCipher(), DraftKeyProvider(secrets, lambda: bytes(range(32)))
    )


def test_vietnamese_roundtrip_and_file_contains_no_sensitive_plaintext(tmp_path):
    secrets = FakeSecretStore()
    snapshot = draft(title="Tiêu đề riêng tư", content="Nội dung không được lộ trên ổ đĩa")
    store = make_store(tmp_path, secrets)
    try:
        store.save_if_newer(snapshot)
        persisted = (tmp_path / (snapshot.draft_id + ".draft")).read_bytes()
        assert snapshot.title.encode() not in persisted
        assert snapshot.content.encode() not in persisted
        assert snapshot.client_operation_id.encode() not in persisted
        assert set(json.loads(persisted)) == {"format_version", "draft_id", "encrypted_envelope"}
    finally:
        store.close()

    restarted = make_store(tmp_path, secrets)
    try:
        assert restarted.get(snapshot.draft_id) == snapshot
    finally:
        restarted.close()


def test_failed_atomic_replace_keeps_old_good_file_and_cleans_encrypted_temp(tmp_path, monkeypatch):
    store = make_store(tmp_path, FakeSecretStore())
    original = draft()
    try:
        store.save_if_newer(original)
        path = tmp_path / (original.draft_id + ".draft")
        before = path.read_bytes()

        def unavailable(*_args):
            raise OSError("private-file-detail")

        monkeypatch.setattr(encrypted_draft_store.os, "replace", unavailable)
        with pytest.raises(SecureStorageUnavailable) as raised:
            store.save_if_newer(replace(original, revision=2, content="new content"))

        assert "private-file-detail" not in str(raised.value)
        assert path.read_bytes() == before and not list(tmp_path.glob("*.tmp"))
        assert store.get(original.draft_id) == original
    finally:
        store.close()


def test_key_loss_and_tamper_preserve_ciphertext_without_replacement_keys(tmp_path):
    secrets = FakeSecretStore()
    store = make_store(tmp_path, secrets)
    original = draft()
    try:
        store.save_if_newer(original)
        path = tmp_path / (original.draft_id + ".draft")
        before = path.read_bytes()
        secrets.delete("draft-master-key.v1")
        with pytest.raises(SecureStorageUnavailable):
            store.get(original.draft_id)
        with pytest.raises(SecureStorageUnavailable):
            store.save_if_newer(draft())
        assert secrets.get("draft-master-key.v1") is None
        assert path.read_bytes() == before

        secrets.put("draft-master-key.v1", bytes(range(32)))
        wrapper = json.loads(before)
        ciphertext = wrapper["encrypted_envelope"]["ciphertext"]
        wrapper["encrypted_envelope"]["ciphertext"] = (
            "A" if ciphertext[0] != "A" else "B"
        ) + ciphertext[1:]
        path.write_text(json.dumps(wrapper), encoding="utf-8")
        with pytest.raises(AuthenticationFailed):
            store.get(original.draft_id)
        store.delete(original.draft_id)  # deliberate discard needs no successful decrypt
        assert not path.exists()
    finally:
        store.close()


def test_unavailable_keyring_creates_no_draft_or_plaintext_fallback(tmp_path):
    secrets = FakeSecretStore()
    secrets.available = False
    store = make_store(tmp_path, secrets)
    try:
        with pytest.raises(SecureStorageUnavailable):
            store.save_if_newer(draft())
        assert not list(tmp_path.glob("*.draft"))
        assert not list(tmp_path.glob("*.tmp"))
        assert all(path.name == ".profile.lock" for path in tmp_path.iterdir())
    finally:
        store.close()


def test_profile_rejects_a_second_writer_and_releases_after_close(tmp_path):
    secrets = FakeSecretStore()
    first, second = make_store(tmp_path, secrets), make_store(tmp_path, secrets)
    snapshot = draft()
    try:
        first.save_if_newer(snapshot)
        with pytest.raises(SecureStorageUnavailable):
            second.list_recoverable()
        first.close()
        assert second.get(snapshot.draft_id) == snapshot
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("revision", True),
        ("priority", "BAD"),
        ("updated_at", "invalid"),
        ("client_operation_id", "bad"),
        ("source_locked", "false"),
        ("extra", 1),
    ],
)
def test_strict_plaintext_payload_rejects_malformed_values_before_display(field, value):
    payload = json.loads(encode_draft_payload(draft()))
    payload[field] = value
    with pytest.raises(ValidationError):
        decode_draft_payload(json.dumps(payload).encode())


def test_duplicate_and_oversized_payloads_are_rejected():
    payload = encode_draft_payload(draft())
    with pytest.raises(ValidationError):
        decode_draft_payload(payload[:-1] + b',"revision":1}')
    with pytest.raises(ValidationError):
        encode_draft_payload(draft(content="x" * (1024 * 1024)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("format_version", True),
        ("format_version", 2),
        ("draft_id", "../escape"),
        ("encrypted_envelope", {}),
        ("extra", "private"),
    ],
)
def test_wrapper_metadata_is_strict_and_never_used_as_an_arbitrary_path(field, value):
    snapshot = draft()
    envelope = AesGcmCipher().encrypt(b"synthetic", bytes(range(32)), b"test:wrapper")
    wrapper = json.loads(encode_draft_wrapper(snapshot.draft_id, envelope))
    wrapper[field] = value
    with pytest.raises(ValidationError):
        decode_draft_wrapper(json.dumps(wrapper).encode(), snapshot.draft_id)
