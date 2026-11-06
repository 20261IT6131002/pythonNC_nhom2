"""Install a built wheel in an isolated target and smoke-test its security boundary."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SMOKE_SOURCE = """
import sys
from pathlib import Path
from secrets import token_bytes

target = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))

import noteapp
from noteapp.application.ports.content_cipher import ContentCipher
from noteapp.application.ports.secret_store import SecretStore
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.keyring_store import KeyringSecretStore
from noteapp.infrastructure.security.serializers import decode_envelope, encode_envelope

assert target in Path(noteapp.__file__).resolve().parents, "Imported editable checkout."
cipher = AesGcmCipher()
assert isinstance(cipher, ContentCipher)
assert isinstance(KeyringSecretStore(), SecretStore)
key, aad, plaintext = token_bytes(32), b"test:packaged-security", b"synthetic-package-smoke"
envelope = decode_envelope(encode_envelope(cipher.encrypt(plaintext, key, aad)))
assert cipher.decrypt(envelope, key, aad) == plaintext
assert plaintext not in encode_envelope(envelope)
assert (target / "noteapp/presentation/tk/assets/icons/save.png").is_file()
print("PACKAGED SECURITY SMOKE PASSED")

from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from uuid import uuid4
from noteapp.application.dto.local_draft import LocalDraft
from noteapp.application.dto.note_input import Priority
from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.infrastructure.local.encrypted_draft_store import EncryptedLocalDraftStore

class TestOnlySecrets:
    def __init__(self):
        self.values = {}
    def get(self, name):
        return self.values.get(name)
    def put(self, name, value):
        self.values[name] = value
    def delete(self, name):
        self.values.pop(name, None)

with TemporaryDirectory(prefix="noteapp_packaged_drafts_") as folder:
    local = EncryptedLocalDraftStore(
        Path(folder), cipher, DraftKeyProvider(TestOnlySecrets(), lambda: token_bytes(32))
    )
    snapshot = LocalDraft(str(uuid4()), None, str(uuid4()), 0, 1, "Title",
                          "synthetic-packaged-draft", Priority.MEDIUM, None,
                          datetime.now(timezone.utc))
    try:
        assert local.save_if_newer(snapshot)
        assert local.get(snapshot.draft_id) == snapshot
        assert b"synthetic-packaged-draft" not in next(Path(folder).glob("*.draft")).read_bytes()
        assert local.delete_if_revision(snapshot.draft_id, snapshot.revision)
    finally:
        local.close()
print("PACKAGED DRAFT RECOVERY SMOKE PASSED")
"""


def verify_package(wheel_dir: Path) -> None:
    wheels = list(wheel_dir.glob("noteapp-*.whl"))

    if len(wheels) != 1:
        raise ValueError("Expected exactly one built NoteApp wheel.")

    with tempfile.TemporaryDirectory(prefix="noteapp_secure_wheel_") as temporary:
        installed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                "--target",
                temporary,
                str(wheels[0].resolve()),
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )

        if installed.returncode:
            raise RuntimeError("Wheel installation failed.\n" + installed.stderr)

        result = subprocess.run(
            [sys.executable, "-I", "-c", SMOKE_SOURCE, temporary],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode:
            raise RuntimeError("Installed wheel smoke failed.\n" + result.stderr)

        print(result.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_dir", type=Path)
    args = parser.parse_args()
    verify_package(args.wheel_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
