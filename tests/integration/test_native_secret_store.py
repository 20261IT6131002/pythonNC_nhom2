"""Explicit opt-in OS credential smoke; owns only a freshly generated test credential."""

import os
from secrets import token_bytes
from uuid import uuid4

import pytest

from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.keyring_store import KeyringSecretStore
from noteapp.infrastructure.security.serializers import decode_envelope, encode_envelope

pytestmark = [
    pytest.mark.native_secret_store,
    pytest.mark.skipif(
        os.environ.get("NOTEAPP_TEST_NATIVE_SECRET_STORE") != "1",
        reason="Native credential smoke needs an explicit isolated test-entry opt-in.",
    ),
]


def test_native_secret_persists_across_adapter_instances_and_is_removed():
    name = "test-" + uuid4().hex
    store = KeyringSecretStore()
    key = token_bytes(32)
    aad = ("test:credential-smoke:" + name).encode()
    plaintext = b"synthetic-native-credential-smoke"
    envelope = AesGcmCipher().encrypt(plaintext, key, aad)

    assert store.get(name) is None

    try:
        store.put(name, key)
        recovered_key = KeyringSecretStore().get(name)
        stored_envelope = decode_envelope(encode_envelope(envelope))

        assert recovered_key == key
        assert AesGcmCipher().decrypt(stored_envelope, recovered_key, aad) == plaintext
    finally:
        # Never enumerate the vault or touch another application's credentials.
        store.delete(name)

    assert KeyringSecretStore().get(name) is None
