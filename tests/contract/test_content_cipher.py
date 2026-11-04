"""SEC-U01..07: the real AES-GCM adapter obeys the reusable AEAD contract."""

import pytest

from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from tests.security_contracts import ContentCipherContract


@pytest.fixture
def cipher():
    return AesGcmCipher()


class TestAesGcmContract(ContentCipherContract):
    """Use the installed authenticated cipher, never a simulated encryption primitive."""
