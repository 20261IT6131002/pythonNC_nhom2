"""P2-09/10: state/version and irreversible intent without DB/GUI."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock

import pytest

from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.trash import TrashNote
from noteapp.application.dto.note_input import (
    ListTrashInput,
    PurgeNoteInput,
    RestoreNoteInput,
    TrashNoteInput,
)
from noteapp.application.ports.trash_repository import TrashedNote, TrashPage
from noteapp.application.queries.list_trash import ListTrash
from noteapp.domain.errors import Conflict, ValidationError
from noteapp.domain.policies.delete_policy import retention_cutoff, transition_note
from tests.fakes import FakeClock
from tests.repository_contracts import note


def test_transition_preserves_payload_and_rejects_replay():
    current = note()
    now = current.updated_at + timedelta(seconds=1)
    deleted = transition_note(current, 1, False, True, now)
    assert deleted == replace(current, version=2, updated_at=now)
    restored = transition_note(deleted, 2, True, False, now)
    assert (
        restored.id == current.id and restored.content == current.content and restored.version == 3
    )
    for expected, state, target in ((1, True, True), (1, True, False), (2, False, False)):
        with pytest.raises(Conflict):
            transition_note(deleted, expected, state, target, now)
    assert retention_cutoff(now) == now - timedelta(days=30)


def test_use_cases_map_records_after_ack():
    repo, clock, current = Mock(), FakeClock(), note()
    deleted = transition_note(current, 1, False, True, clock.now())
    repo.move_to_trash.return_value = TrashedNote(deleted, clock.now())
    view = TrashNote(repo, clock).execute(TrashNoteInput(current.id, 1))
    assert view.note.version == 2 and view.note.content == current.content
    repo.restore.return_value = replace(deleted, version=3)
    assert RestoreNote(repo, clock).execute(RestoreNoteInput(current.id, 2)).version == 3
    repo.list_trashed.return_value = TrashPage((TrashedNote(deleted, clock.now()),), None)
    assert ListTrash(repo).execute().items == (view,)


@pytest.mark.parametrize("confirmed", [False, None, 1, "yes"])
def test_unconfirmed_purge_has_zero_calls(confirmed):
    repo = Mock()
    with pytest.raises(ValidationError):
        PurgeNote(repo).execute(PurgeNoteInput("existing-id", 1, confirmed))
    assert not repo.mock_calls


def test_confirmed_purge_passes_existing_id_and_version():
    repo = Mock()
    PurgeNote(repo).execute(PurgeNoteInput("existing-id", 2, True))
    repo.purge_confirmed.assert_called_once_with("existing-id", 2)


@pytest.mark.parametrize("limit", [0, True, 101])
def test_invalid_trash_page_never_queries(limit):
    repo = Mock()
    with pytest.raises(ValidationError):
        ListTrash(repo).execute(ListTrashInput(limit=limit))
    assert not repo.mock_calls


def test_raw_command_is_rejected_before_repository_access():
    repo, clock = Mock(), FakeClock()
    for use_case in (
        TrashNote(repo, clock),
        RestoreNote(repo, clock),
        PurgeNote(repo),
        ListTrash(repo),
    ):
        with pytest.raises(ValidationError):
            use_case.execute({"$where": "unsafe"})
    assert not repo.mock_calls
