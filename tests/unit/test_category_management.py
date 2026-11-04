"""P3A-01: category use cases run without Mongo or a display."""

import pytest

from noteapp.application.commands.category import (
    CreateCategory,
    DeleteCategory,
    RenameCategory,
    UpdateCategoryColor,
)
from noteapp.application.dto.note_input import (
    CreateCategoryInput,
    DeleteCategoryInput,
    RenameCategoryInput,
    UpdateCategoryColorInput,
)
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.queries.list_notes import ListCategories
from noteapp.domain.errors import (
    CategoryInUse,
    CategoryNotFound,
    DuplicateCategory,
    ValidationError,
)
from tests.fakes import FakeCategories, FakeClock, FakeNotes
from tests.repository_contracts import note


@pytest.fixture
def world():
    notes = FakeNotes()
    categories = FakeCategories(notes)
    return notes, categories, FakeClock()


def test_create_trims_validates_and_lists_deterministically(world):
    _, categories, clock = world
    create = CreateCategory(categories, clock)
    view = create.execute(CreateCategoryInput("  Công việc  ", "#abcdef"))
    assert (view.name, view.color_hex) == ("Công việc", "#abcdef")
    create.execute(CreateCategoryInput("An"))
    names = [item.name for item in ListCategories(categories).execute()]
    assert names == ["An", "Công việc"]


@pytest.mark.parametrize("name", ["", "   ", None])
def test_create_rejects_blank_name(world, name):
    _, categories, clock = world
    with pytest.raises(ValidationError):
        CreateCategory(categories, clock).execute(CreateCategoryInput(name))
    assert categories.list_all() == ()


@pytest.mark.parametrize("color", ["red", "#12345", "#GGGGGG", "123456", None])
def test_create_rejects_bad_color(world, color):
    _, categories, clock = world
    with pytest.raises(ValidationError):
        CreateCategory(categories, clock).execute(CreateCategoryInput("X", color))


def test_create_duplicate_normalized_name_is_rejected(world):
    _, categories, clock = world
    create = CreateCategory(categories, clock)
    create.execute(CreateCategoryInput("Straße"))
    with pytest.raises(DuplicateCategory):
        create.execute(CreateCategoryInput(" STRASSE "))


def test_rename_and_recolor_keep_id(world):
    _, categories, clock = world
    created = CreateCategory(categories, clock).execute(CreateCategoryInput("Old"))
    renamed = RenameCategory(categories).execute(RenameCategoryInput(created.category_id, "New"))
    recolored = UpdateCategoryColor(categories).execute(
        UpdateCategoryColorInput(created.category_id, "#000000")
    )
    assert renamed.category_id == recolored.category_id == created.category_id
    assert (recolored.name, recolored.color_hex) == ("New", "#000000")


def test_rename_blank_or_missing_is_rejected(world):
    _, categories, clock = world
    created = CreateCategory(categories, clock).execute(CreateCategoryInput("Old"))
    with pytest.raises(ValidationError):
        RenameCategory(categories).execute(RenameCategoryInput(created.category_id, " "))
    with pytest.raises(CategoryNotFound):
        RenameCategory(categories).execute(RenameCategoryInput("a" * 24, "X"))
    assert categories.find_by_id(created.category_id).name == "Old"


def test_delete_unused_succeeds_and_referenced_is_rejected(world):
    notes, categories, clock = world
    create = CreateCategory(categories, clock)
    used, unused = (create.execute(CreateCategoryInput(n)) for n in ("Used", "Unused"))
    notes.create(note(category_id=used.category_id), "11111111-1111-4111-8111-111111111111")
    delete = DeleteCategory(categories)
    delete.execute(DeleteCategoryInput(unused.category_id))
    with pytest.raises(CategoryInUse):
        delete.execute(DeleteCategoryInput(used.category_id))
    assert [item.name for item in ListCategories(categories).execute()] == ["Used"]


def test_error_codes_are_public_and_specific():
    assert OperationResult.failed(DuplicateCategory()).error == ErrorCode.DUPLICATE
    assert OperationResult.failed(CategoryInUse()).error == ErrorCode.IN_USE
    assert OperationResult.failed(CategoryNotFound()).error == ErrorCode.NOT_FOUND
