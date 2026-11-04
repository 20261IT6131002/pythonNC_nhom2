"""R1-02 shared native-secret behavior, independent of storage implementation."""

from dataclasses import replace

import pytest

from noteapp.application.ports.content_cipher import ContentCipher
from noteapp.application.ports.secret_store import SecretStore
from noteapp.domain.errors import AuthenticationFailed, ValidationError


class ContentCipherContract:
    def test_roundtrip_authenticates_binary_and_empty_plaintext(self, cipher):
        assert isinstance(cipher, ContentCipher)
        key = bytes(range(32))
        aad = b"test:draft:record-1"

        for plaintext in (b"", b"\x00\xffbinary", "Nội dung riêng tư".encode()):
            envelope = cipher.encrypt(plaintext, key, aad)

            assert envelope.algorithm == "AES-256-GCM"
            assert len(envelope.nonce) == 12
            assert len(envelope.ciphertext) == len(plaintext) + 16
            assert cipher.decrypt(envelope, key, aad) == plaintext

    def test_same_content_uses_fresh_nonces_and_ciphertexts(self, cipher):
        key, plaintext, aad = bytes(range(32)), b"private-content-marker", b"test:context"
        encrypted = [cipher.encrypt(plaintext, key, aad) for _ in range(32)]

        assert len({item.nonce for item in encrypted}) == 32
        assert len({item.ciphertext for item in encrypted}) == 32
        assert all(plaintext not in item.ciphertext for item in encrypted)

    @pytest.mark.parametrize("part", ["body", "tag", "nonce", "key", "aad"])
    def test_tamper_wrong_key_or_context_returns_no_plaintext(self, cipher, part):
        key, aad = bytes(range(32)), b"test:draft:record-1"
        envelope = cipher.encrypt(b"private-content-marker", key, aad)

        if part in ("body", "tag"):
            corrupted = bytearray(envelope.ciphertext)
            corrupted[0 if part == "body" else -1] ^= 1
            envelope = replace(envelope, ciphertext=bytes(corrupted))
        elif part == "nonce":
            envelope = replace(envelope, nonce=bytes(value ^ 1 for value in envelope.nonce))
        elif part == "key":
            key = bytes(reversed(range(32)))
        else:
            aad = b"test:locked-note:record-1"

        with pytest.raises(AuthenticationFailed) as raised:
            cipher.decrypt(envelope, key, aad)

        assert str(raised.value) == "Encrypted data could not be authenticated."
        assert raised.value.__cause__ is None

    @pytest.mark.parametrize("key", [b"", b"x" * 16, b"x" * 24, b"x" * 31, b"x" * 33, "x" * 32])
    def test_invalid_key_cannot_encrypt_or_decrypt(self, cipher, key):
        valid = cipher.encrypt(b"content", bytes(range(32)), b"context")

        with pytest.raises(ValidationError):
            cipher.encrypt(b"content", key, b"context")

        with pytest.raises(ValidationError):
            cipher.decrypt(valid, key, b"context")

    @pytest.mark.parametrize("aad", [b"", "context", None, bytearray(b"context")])
    def test_context_is_explicit_nonempty_bytes(self, cipher, aad):
        key = bytes(range(32))
        valid = cipher.encrypt(b"content", key, b"context")

        with pytest.raises(ValidationError):
            cipher.encrypt(b"content", key, aad)

        with pytest.raises(ValidationError):
            cipher.decrypt(valid, key, aad)


class SecretStoreContract:
    def test_missing_put_replace_get_and_idempotent_delete(self, secret_store):
        assert isinstance(secret_store, SecretStore)
        assert secret_store.get("draft-key.v1") is None

        original = bytes(range(32))
        replacement = bytes(reversed(range(32)))
        secret_store.put("draft-key.v1", original)
        assert secret_store.get("draft-key.v1") == original

        secret_store.put("draft-key.v1", replacement)
        secret_store.put("other-key", b"other-key-material")
        assert secret_store.get("draft-key.v1") == replacement

        secret_store.delete("draft-key.v1")
        secret_store.delete("draft-key.v1")
        assert secret_store.get("draft-key.v1") is None
        assert secret_store.get("other-key") == b"other-key-material"

    @pytest.mark.parametrize("secret", [b"", b"x" * 513, None, "secret", bytearray(32)])
    def test_invalid_values_do_not_replace_an_existing_key(self, secret_store, secret):
        secret_store.put("stable-key", b"keep-existing-key")

        with pytest.raises(ValidationError):
            secret_store.put("stable-key", secret)

        assert secret_store.get("stable-key") == b"keep-existing-key"

    @pytest.mark.parametrize("name", ["", "../key", "contains space", "x" * 129, None, 1])
    def test_invalid_names_cannot_access_or_mutate_storage(self, secret_store, name):
        for operation in (
            lambda: secret_store.get(name),
            lambda: secret_store.put(name, b"synthetic-key"),
            lambda: secret_store.delete(name),
        ):
            with pytest.raises(ValidationError):
                operation()

    def test_binary_boundaries_roundtrip(self, secret_store):
        for length in (1, 32, 512):
            value = bytes(index % 256 for index in range(length))
            secret_store.put("binary-key", value)
            assert secret_store.get("binary-key") == value
