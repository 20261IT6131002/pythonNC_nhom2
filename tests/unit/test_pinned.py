"""R1-01 PIN-U/A: strict flags, metadata-only transitions and application CAS failures."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from noteapp.application.commands.set_pinned import SetPinned
from noteapp.application.dto.note_input import SetPinnedInput
from noteapp.domain.entities.reminder import Reminder
from noteapp.domain.errors import Conflict, NotFound, RepositoryUnavailable, ValidationError
from noteapp.domain.value_objects.attachment_ref import AttachmentRef
from tests.fakes import FakeNotes
from tests.repository_contracts import note


def test_pin_and_unpin_only_change_flag_and_version():
    original = note()
    original = replace(
        original,
        attachment=AttachmentRef("INLINE", "opaque-image", "image/png", 42, "a" * 64, "image.png"),
        reminder=Reminder.schedule(original.updated_at.replace(year=2027), original.updated_at),
    )
    assert original.is_pinned is False

    pinned = original.with_pinned(True)
    assert pinned == replace(original, is_pinned=True, version=2)
    assert pinned.with_pinned(True) is pinned

    unpinned = pinned.with_pinned(False)
    assert unpinned == replace(original, version=3)


@pytest.mark.parametrize("target", [0, 1, "true", None, [], {}])
def test_pin_rejects_non_boolean_at_every_boundary(target):
    original = note()
    notes = FakeNotes()
    notes.create(original, "create")

    with pytest.raises(ValidationError):
        replace(original, is_pinned=target)
    with pytest.raises(ValidationError):
        original.with_pinned(target)
    with pytest.raises(ValidationError):
        SetPinned(notes).execute(SetPinnedInput(original.id, 1, target))

    assert notes.find_by_id(original.id) == original


def test_command_pin_noop_unpin_and_stale_intent():
    notes = FakeNotes()
    original = notes.create(note(version=4), "create")
    command = SetPinned(notes)

    pinned = command.execute(SetPinnedInput(original.id, 4, True))
    assert pinned.is_pinned and pinned.version == 5
    assert command.execute(SetPinnedInput(original.id, 5, True)) == pinned

    with pytest.raises(Conflict):
        command.execute(SetPinnedInput(original.id, 4, True))

    unpinned = command.execute(SetPinnedInput(original.id, 5, False))
    assert not unpinned.is_pinned and unpinned.version == 6
    assert unpinned.updated_at == original.updated_at


@pytest.mark.parametrize("version", [0, -1, True, "1", None])
def test_command_validates_expected_version(version):
    with pytest.raises(ValidationError):
        SetPinned(FakeNotes()).execute(SetPinnedInput("note", version, True))


def test_command_missing_and_failed_cas_distinguish_not_found_from_conflict():
    notes = Mock()
    command = SetPinned(notes)
    original = note()
    request = SetPinnedInput(original.id, 1, True)
    notes.find_by_id.return_value = None

    with pytest.raises(NotFound):
        command.execute(request)

    notes.set_pinned_if_version.return_value = False
    notes.find_by_id.side_effect = [original, original]
    with pytest.raises(Conflict):
        command.execute(request)

    notes.find_by_id.side_effect = [original, None]
    with pytest.raises(NotFound):
        command.execute(request)

    notes.find_by_id.side_effect = RepositoryUnavailable("Unavailable")
    with pytest.raises(RepositoryUnavailable):
        command.execute(request)
