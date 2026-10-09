"""FR-01/02/04/05 and P1-AC03/06/07/08 with pure fakes."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_filter import ListNotesInput
from noteapp.application.dto.note_input import CreateNoteInput, UpdateNoteInput
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.ports.category_repository import CategoryRepository
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.application.queries.get_note import GetNote
from noteapp.application.queries.list_notes import ListCategories, ListNotes
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import Conflict, NotFound, RepositoryUnavailable, ValidationError
from noteapp.domain.policies.note_validation import validate_title
from noteapp.domain.value_objects.priority import Priority
from tests.fakes import FakeCategories, FakeClock, FakeNotes


@pytest.fixture
def core():
    notes, categories, clock = FakeNotes(), FakeCategories(), FakeClock()
    return notes, categories, clock, CreateNote(notes, categories, clock)


def input_note(**changes):
    return replace(
        CreateNoteInput(
            " Ghi chĂº ", "Ná»™i dung tiáº¿ng Viá»‡t", Priority.MEDIUM, None, str(uuid4())
        ),
        **changes,
    )


@pytest.mark.parametrize(
    ("title", "valid"),
    [
        ("", False),
        (" \t\n ", False),
        ("a", True),
        ("a" * 250, True),
        ("a" * 251, False),
        ("  a  ", True),
        (None, False),
    ],
)
def test_title_boundaries(title, valid):
    if valid:
        assert validate_title(title) == title.strip()
    else:
        with pytest.raises(ValidationError):
            validate_title(title)


def test_priority_rank():
    assert [priority.rank for priority in Priority] == [3, 2, 1]


def test_create_utc_and_idempotency(core):
    notes, _, clock, create = core
    command = input_note()
    first = create.execute(command)
    clock.value += timedelta(seconds=1)
    second = create.execute(replace(command, title="Different retry text"))
    assert first == second
    assert len(notes.items) == 1
    assert first.title == "Ghi chĂº"
    assert first.created_at.utcoffset() == timedelta(0)
    with pytest.raises(FrozenInstanceError):
        command.title = "mutation"


@pytest.mark.parametrize("operation_id", ["", None, "$where", "not-a-uuid"])
def test_create_invalid_operation_id(core, operation_id):
    with pytest.raises(ValidationError):
        core[3].execute(input_note(client_operation_id=operation_id))
    assert not core[0].items


@pytest.mark.parametrize(
    ("field", "value"), [("priority", "INVALID"), ("content", {}), ("category_id", "missing")]
)
def test_invalid_note_input(core, field, value):
    with pytest.raises(ValidationError):
        core[3].execute(input_note(**{field: value}))


def test_category_lookup_and_normalization(core):
    _, categories, clock, create = core
    category = Category("category-id", " Study ", "#123ABC", clock.now())
    categories.create(category)
    view = create.execute(input_note(category_id=category.id, priority=Priority.HIGH))
    assert view.category_id == category.id
    assert category.name_key == "study"
    assert ListCategories(categories).execute()[0].name == "Study"


def test_update_and_stale_version(core):
    notes, categories, clock, create = core
    view = create.execute(input_note())
    update = UpdateNote(notes, categories, clock)
    command = UpdateNoteInput(view.note_id, "Edited", "New text", Priority.HIGH, None, 1)
    clock.value += timedelta(seconds=1)
    saved = update.execute(command)
    assert saved.version == 2
    assert saved.created_at == view.created_at
    assert saved.updated_at > view.updated_at
    with pytest.raises(Conflict):
        update.execute(replace(command, content="Stale text"))
    assert notes.find_by_id(view.note_id).content == "New text"


def test_update_cas_race(core):
    notes, categories, clock, create = core
    view = create.execute(input_note())
    notes.update_if_version = lambda note, version: False
    with pytest.raises(Conflict):
        UpdateNote(notes, categories, clock).execute(
            UpdateNoteInput(view.note_id, "Edited", "text", Priority.LOW, None, 1)
        )


def test_missing_note(core):
    with pytest.raises(NotFound):
        UpdateNote(*core[:3]).execute(
            UpdateNoteInput("missing", "title", "", Priority.LOW, None, 1)
        )
    with pytest.raises(NotFound):
        GetNote(core[0]).execute("missing")


@pytest.mark.parametrize("limit", [0, -1, 101, True, "30"])
def test_list_page_size_rejected(core, limit):
    with pytest.raises(ValidationError):
        ListNotes(core[0]).execute(ListNotesInput(limit=limit))


def test_bounded_list_and_protocols(core):
    notes, categories, clock, create = core
    for i in range(35):
        create.execute(input_note(title=f"Note {i}"))
    page = ListNotes(notes).execute()
    assert len(page.items) == 30
    next_page = ListNotes(notes).execute(ListNotesInput(cursor=page.next_cursor))
    assert len(next_page.items) == 5
    assert next_page.next_cursor is None
    assert isinstance(notes, NoteRepository)
    assert isinstance(categories, CategoryRepository)
    assert isinstance(clock, Clock)


def test_naive_clock_rejected(core):
    core[2].value = datetime(2026, 10, 9)
    with pytest.raises(ValidationError):
        core[3].execute(input_note())


def test_non_utc_clock_is_normalized(core):
    core[2].value = datetime(2026, 10, 9, 7, tzinfo=timezone(timedelta(hours=7)))
    assert core[3].execute(input_note()).created_at.hour == 0


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (Conflict("secret"), ErrorCode.CONFLICT),
        (RepositoryUnavailable("secret"), ErrorCode.UNAVAILABLE),
        (RuntimeError("secret"), ErrorCode.UNEXPECTED),
    ],
)
def test_errors_do_not_leak_raw_messages(error, code):
    result = OperationResult.failed(error)
    assert result.error == code
    assert "secret" not in repr(result)
