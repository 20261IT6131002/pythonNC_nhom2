"""Checklist probes: valid PNG bytes at exact boundaries and real operation log canaries."""
import io
import logging
import struct
import time
import zlib
from uuid import uuid4

import pytest

from noteapp.application.commands.locked_notes import LockedNotes
from noteapp.application.dto.note_input import AttachImageInput, CreateNoteInput, Priority
from noteapp.domain.errors import ImageTooLarge, UnsupportedImage
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.passphrase_kdf import Pbkdf2PassphraseKdf
from noteapp.infrastructure.telemetry.logging import OperationFormatter
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from tests.integration.test_attachment_lifecycle import World, png


@pytest.fixture
def world():
    name = 'noteapp_test_qa_probe_' + uuid4().hex
    with create_client(Config('mongodb://127.0.0.1:27028', name, 10000)) as client:
        ping(client)
        try:
            create_indexes(client[name])
            yield World(client[name])
        finally:
            assert name.startswith('noteapp_test_qa_probe_')
            client.drop_database(name)


def exact_png(size):
    original = png()
    kind = b'npAd'  # private ancillary PNG padding, valid CRC and unchanged image pixels
    payload = b'Q' * (size - len(original) - 12)
    chunk = struct.pack('>I', len(payload)) + kind + payload
    chunk += struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    result = original[:-12] + chunk + original[-12:]
    assert len(result) == size
    return result


@pytest.mark.parametrize('size,kind', [(1048576, 'INLINE'), (1048577, 'GRIDFS'),
                                      (10485760, 'GRIDFS'), (10485761, None)])
def test_actual_valid_png_boundaries_keep_old_on_failure(world, size, kind):
    note = world.note()
    old = world.service.attach(AttachImageInput(note.note_id, 1, png(), 'old.png'))
    old_ref = world.notes.find_by_id(note.note_id).attachment
    before = world.payloads()
    command = AttachImageInput(note.note_id, old.version, exact_png(size), 'actual.png')
    if kind is None:
        with pytest.raises(ImageTooLarge):
            world.service.attach(command)
        unchanged = world.notes.find_by_id(note.note_id)
        assert unchanged.attachment == old_ref and world.payloads() == before
    else:
        updated = world.service.attach(command)
        assert updated.attachment.kind == kind and updated.attachment.size_bytes == size
        ref = world.notes.find_by_id(note.note_id).attachment
        assert world.store.get(ref) == command.data


def test_forged_mime_keeps_old_image(world):
    note = world.note()
    old = world.service.attach(AttachImageInput(note.note_id, 1, png(), 'old.png'))
    old_ref = world.notes.find_by_id(note.note_id).attachment
    with pytest.raises(UnsupportedImage):
        world.service.attach(AttachImageInput(note.note_id, old.version,
                             b'%PDF-1.7 synthetic image forgery', 'pretend.png'))
    assert world.notes.find_by_id(note.note_id).attachment == old_ref
    assert world.payloads() == 1


def test_real_locked_operation_logs_never_emit_canary_text(world):
    marker = 'QA_PRIVATE_BODY_' + uuid4().hex
    title = 'QA_PRIVATE_TITLE_' + uuid4().hex
    phrase = 'QA_PRIVATE_PHRASE_' + uuid4().hex
    locked = LockedNotes(world.notes, world.create, AesGcmCipher(), Pbkdf2PassphraseKdf())
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(OperationFormatter())
    logger = logging.getLogger('noteapp.operations')
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    runner = TaskRunner()
    try:
        command = CreateNoteInput(title, marker, Priority.HIGH, None, str(uuid4()))
        assert runner.submit('qa-lock', 'lock', lambda: locked.create_locked(command, phrase))
        deadline = time.monotonic() + 10
        events = []
        while not events and time.monotonic() < deadline:
            events = runner.drain()
            time.sleep(.005)
        assert events and events[0].result.ok
        saved = events[0].result.value
        assert runner.submit('qa-wrong-phrase', 'unlock',
                             lambda: locked.unlock(saved.note_id, saved.version, 'wrong synthetic phrase'))
        events = []
        while not events and time.monotonic() < deadline:
            events = runner.drain()
            time.sleep(.005)
        assert events and not events[0].result.ok
        rendered = stream.getvalue()
        assert 'qa-lock' in rendered and 'qa-wrong-phrase' in rendered
        assert all(canary not in rendered for canary in (marker, title, phrase))
        assert all(canary.encode() not in str(world.database.notes.find_one()).encode()
                   for canary in (marker, title, phrase))
    finally:
        runner.close(wait=True)
        logger.removeHandler(handler)
        logger.setLevel(old_level)
