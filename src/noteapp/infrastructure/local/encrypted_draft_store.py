"""Authenticated local snapshots, atomic replacement, revision fences and profile ownership."""

import errno
import os
import stat
import tempfile
from dataclasses import replace
from pathlib import Path
from threading import RLock

from noteapp.application.dto.local_draft import DraftHeader, LocalDraft, validate_draft_id
from noteapp.application.ports.content_cipher import ContentCipher
from noteapp.application.services.draft_keys import DraftKeyProvider
from noteapp.domain.errors import Conflict, SecureStorageUnavailable, ValidationError
from noteapp.infrastructure.local.draft_serializers import (
    MAX_DRAFT_FILE_BYTES,
    decode_draft_payload,
    decode_draft_wrapper,
    encode_draft_payload,
    encode_draft_wrapper,
)
from noteapp.infrastructure.local.profile_lock import ProfileLock


class EncryptedLocalDraftStore:
    def __init__(self, directory: Path, cipher: ContentCipher, keys: DraftKeyProvider) -> None:
        self.directory = directory
        self.cipher = cipher
        self.keys = keys
        self._lock = RLock()
        self._profile = ProfileLock(directory)
        self._acknowledged: dict[str, int] = {}
        self._discarded: set[str] = set()
        self._closed = False

    def _prepare(self, *, create: bool = False) -> bool:
        if self._closed:
            raise SecureStorageUnavailable("Draft storage is closed.")

        if not self.directory.is_absolute() or self.directory.is_symlink():
            raise SecureStorageUnavailable("Draft directory requires independent review.")

        if create:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

        if not self.directory.exists():
            return False

        self._profile.acquire()
        return True

    def _path(self, draft_id: str) -> Path:
        return self.directory / (validate_draft_id(draft_id) + ".draft")

    def _has_ciphertext(self) -> bool:
        return any(path.suffix in {".draft", ".tmp"} for path in self.directory.iterdir())

    def _load(self, draft_id: str, key: bytes) -> LocalDraft | None:
        path = self._path(draft_id)

        if path.is_symlink():
            raise ValidationError("A draft file must not be a symbolic link.")

        try:
            descriptor = os.open(
                path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            )
        except FileNotFoundError:
            return None

        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValidationError("A draft must be a regular file.")

            wrapper = handle.read(MAX_DRAFT_FILE_BYTES + 1)

        envelope = decode_draft_wrapper(wrapper, draft_id)
        payload = self.cipher.decrypt(envelope, key, ("noteapp:draft:v1:" + draft_id).encode())
        draft = decode_draft_payload(payload)

        if draft.draft_id != draft_id:
            raise ValidationError("Authenticated draft identity does not match.")

        return draft

    def _atomic_write(self, path: Path, data: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".draft-", suffix=".tmp", dir=self.directory
        )

        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()

                try:
                    os.fsync(handle.fileno())
                except OSError as error:
                    if error.errno not in {errno.EINVAL, errno.ENOTSUP}:
                        raise

            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def save_if_newer(self, draft: LocalDraft) -> bool:
        payload = encode_draft_payload(draft)

        try:
            with self._lock:
                if draft.draft_id in self._discarded or draft.revision <= self._acknowledged.get(
                    draft.draft_id, 0
                ):
                    return False

                self._prepare(create=True)
                key = self.keys.get_key(existing_ciphertext=self._has_ciphertext())
                current = self._load(draft.draft_id, key)

                if current is not None:
                    if draft.revision < current.revision:
                        return False

                    if draft.revision == current.revision:
                        if replace(draft, updated_at=current.updated_at) != current:
                            raise Conflict("A draft revision already contains another snapshot.")

                        return True

                envelope = self.cipher.encrypt(
                    payload, key, ("noteapp:draft:v1:" + draft.draft_id).encode()
                )
                self._atomic_write(
                    self._path(draft.draft_id), encode_draft_wrapper(draft.draft_id, envelope)
                )
                return True
        except OSError:
            raise SecureStorageUnavailable(
                "Encrypted draft storage did not acknowledge the write."
            ) from None

    def get(self, draft_id: str) -> LocalDraft | None:
        validate_draft_id(draft_id)

        try:
            with self._lock:
                if not self._prepare() or not self._path(draft_id).exists():
                    return None

                key = self.keys.get_key(existing_ciphertext=True)
                return self._load(draft_id, key)
        except OSError:
            raise SecureStorageUnavailable("Encrypted draft storage could not be read.") from None

    def list_recoverable(self) -> tuple[DraftHeader, ...]:
        try:
            with self._lock:
                if not self._prepare():
                    return ()

                headers = []

                for path in sorted(self.directory.glob("*.draft")):
                    try:
                        validate_draft_id(path.stem)
                    except ValidationError:
                        continue

                    headers.append(DraftHeader(path.stem))

                return tuple(headers)
        except OSError:
            raise SecureStorageUnavailable("Local drafts could not be discovered.") from None

    def delete_if_revision(self, draft_id: str, revision: int) -> bool:
        validate_draft_id(draft_id)

        if type(revision) is not int or revision < 1:
            raise ValidationError("Acknowledged revision must be positive.")

        try:
            with self._lock:
                current = self.get(draft_id)
                self._acknowledged[draft_id] = max(revision, self._acknowledged.get(draft_id, 0))

                if current is not None and current.revision > revision:
                    return False

                self._path(draft_id).unlink(missing_ok=True)
                return True
        except OSError:
            raise SecureStorageUnavailable("Draft acknowledgement cleanup failed.") from None

    def delete(self, draft_id: str) -> None:
        validate_draft_id(draft_id)

        try:
            with self._lock:
                if self._prepare():
                    self._path(draft_id).unlink(missing_ok=True)

                self._discarded.add(draft_id)
        except OSError:
            raise SecureStorageUnavailable("Draft discard failed.") from None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._profile.close()
