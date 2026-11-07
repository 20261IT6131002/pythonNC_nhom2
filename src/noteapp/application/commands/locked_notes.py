"""FR-14 authenticated note lifecycle. Secrets belong to the caller's editor session."""

import json
from dataclasses import replace
from secrets import token_bytes

from noteapp.application.commands.create import CreateNote
from noteapp.application.dto.locked_content import MAX_CONTENT_BYTES, SALT_BYTES, LockedContent
from noteapp.application.dto.note_input import CreateNoteInput, UpdateNoteInput
from noteapp.application.dto.note_view import LOCKED_TITLE, NoteView
from noteapp.application.ports.content_cipher import ContentCipher
from noteapp.application.ports.locked_note_repository import LockedNoteRepository
from noteapp.application.ports.passphrase_kdf import PassphraseKdf
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import AuthenticationFailed, Conflict, NotFound, ValidationError
from noteapp.domain.policies.note_validation import validate_version


def passphrase_bytes(passphrase: str) -> bytes:
    try:
        if isinstance(passphrase, str) and 12 <= len(passphrase) <= 1024:
            value = passphrase.encode("utf-8")
            if len(value) <= 1024:
                return value
    except UnicodeError:
        pass
    raise ValidationError("Use at least 12 characters and at most 1024 UTF-8 bytes.")


class LockedNotes:
    def __init__(
        self,
        repository: LockedNoteRepository,
        create: CreateNote,
        cipher: ContentCipher,
        kdf: PassphraseKdf,
    ) -> None:
        self.repository = repository
        self.create = create
        self.cipher = cipher
        self.kdf = kdf

    @staticmethod
    def _aad(note_id: str) -> bytes:
        return b"noteapp:locked-note:v1:" + note_id.encode("utf-8")

    def _seal(self, note: Note, passphrase: str) -> LockedContent:
        secret = passphrase_bytes(passphrase)
        try:
            if len(note.content.encode("utf-8")) > MAX_CONTENT_BYTES:
                raise ValidationError("Locked content is limited to 1 MiB.")
            plaintext = json.dumps([note.title, note.content], ensure_ascii=False).encode("utf-8")
        except UnicodeError:
            raise ValidationError("Note text must be valid UTF-8.") from None
        salt = token_bytes(SALT_BYTES)
        return LockedContent(
            salt, self.cipher.encrypt(plaintext, self.kdf.derive(secret, salt), self._aad(note.id))
        )

    def _open(self, note_id: str, version: int, passphrase: str) -> Note:
        validate_version(version)
        record = self.repository.find_locked(note_id)
        if record is None or record[0].version != version:
            raise Conflict("The locked note changed. Reload before trying again.")
        note, payload = record
        key = self.kdf.derive(passphrase_bytes(passphrase), payload.salt)
        data = self.cipher.decrypt(payload.envelope, key, self._aad(note_id))
        try:
            fields = json.loads(data.decode("utf-8"))
            if not isinstance(fields, list) or len(fields) != 2:
                raise ValueError
            title, content = fields
            if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
                raise ValueError
            return Note(
                note.id,
                title,
                content,
                note.priority,
                note.category_id,
                note.version,
                note.created_at,
                note.updated_at,
                note.attachment,
                note.reminder,
                note.is_pinned,
            )
        except (ValueError, ValidationError, RecursionError):
            raise AuthenticationFailed("Encrypted note could not be authenticated.") from None

    def create_locked(self, command: CreateNoteInput, passphrase: str) -> NoteView:
        note, operation_id = self.create.prepare(command)
        payload = self._seal(note, passphrase)
        saved = self.repository.create_locked(note, operation_id, payload)
        # An idempotent retry must still authenticate the already-persisted record.
        return self.unlock(saved.id, saved.version, passphrase)

    def _write(self, note: Note, payload: LockedContent | None, *, was_locked: bool) -> NoteView:
        if not self.repository.write_lock(note, payload, was_locked=was_locked):
            raise Conflict("The note changed. Reload before trying again.")
        return replace(NoteView.from_note(note), is_locked=payload is not None)

    def lock(self, note_id: str, version: int, passphrase: str) -> NoteView:
        validate_version(version)
        note = self.create.notes.find_by_id(note_id)
        if note is None:
            raise NotFound("Note not found.")
        if note.is_locked or note.version != version:
            raise Conflict("The note changed. Reload before locking.")
        updated = note.edited(
            title=note.title,
            content=note.content,
            priority=note.priority,
            category_id=note.category_id,
            now=self.create.clock.now(),
        )
        saved = self._write(updated, self._seal(updated, passphrase), was_locked=False)
        return replace(saved, title=LOCKED_TITLE, content=None)

    def unlock(self, note_id: str, version: int, passphrase: str) -> NoteView:
        return replace(NoteView.from_note(self._open(note_id, version, passphrase)), is_locked=True)

    def update(self, command: UpdateNoteInput, passphrase: str) -> NoteView:
        note = self._open(command.note_id, command.expected_version, passphrase)
        updated = note.edited(
            title=command.title,
            content=command.content,
            priority=command.priority,
            category_id=command.category_id,
            now=self.create.clock.now(),
        )
        if updated.category_id and self.create.categories.find_by_id(updated.category_id) is None:
            raise ValidationError("The selected category does not exist.")
        return self._write(updated, self._seal(updated, passphrase), was_locked=True)

    def change_passphrase(
        self, note_id: str, version: int, old_passphrase: str, new_passphrase: str
    ) -> NoteView:
        note = self._open(note_id, version, old_passphrase)
        updated = replace(note, version=version + 1)
        saved = self._write(updated, self._seal(updated, new_passphrase), was_locked=True)
        return replace(saved, title=LOCKED_TITLE, content=None)

    def remove(self, note_id: str, version: int, passphrase: str, *, confirmed: bool) -> NoteView:
        if confirmed is not True:
            raise ValidationError("Confirm storing this note as plaintext.")
        note = self._open(note_id, version, passphrase)
        return self._write(replace(note, version=version + 1), None, was_locked=True)
