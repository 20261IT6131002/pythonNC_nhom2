"""FR-04: category management; names are normalized and uniqueness lives in the repository."""

from dataclasses import dataclass
from secrets import token_hex

from noteapp.application.dto.note_input import (
    CreateCategoryInput,
    DeleteCategoryInput,
    RenameCategoryInput,
    UpdateCategoryColorInput,
)
from noteapp.application.dto.note_view import CategoryView
from noteapp.application.ports.category_repository import CategoryRepository
from noteapp.application.ports.clock import Clock
from noteapp.application.queries.list_notes import ListCategories
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import CategoryNotFound
from noteapp.domain.policies.note_validation import validate_id


class CreateCategory:
    def __init__(self, categories: CategoryRepository, clock: Clock) -> None:
        self.categories, self.clock = categories, clock

    def execute(self, command: CreateCategoryInput) -> CategoryView:
        category = Category(token_hex(12), command.name, command.color_hex, self.clock.now())
        return CategoryView.from_category(self.categories.create(category))


class RenameCategory:
    def __init__(self, categories: CategoryRepository) -> None:
        self.categories = categories

    def execute(self, command: RenameCategoryInput) -> CategoryView:
        validate_id(command.category_id)
        current = self.categories.find_by_id(command.category_id)
        if current is None:
            raise CategoryNotFound("Category not found.")
        return CategoryView.from_category(self.categories.update(current.renamed(command.name)))


class UpdateCategoryColor:
    def __init__(self, categories: CategoryRepository) -> None:
        self.categories = categories

    def execute(self, command: UpdateCategoryColorInput) -> CategoryView:
        validate_id(command.category_id)
        current = self.categories.find_by_id(command.category_id)
        if current is None:
            raise CategoryNotFound("Category not found.")
        return CategoryView.from_category(
            self.categories.update(current.recolored(command.color_hex))
        )


class DeleteCategory:
    def __init__(self, categories: CategoryRepository) -> None:
        self.categories = categories

    def execute(self, command: DeleteCategoryInput) -> None:
        validate_id(command.category_id)
        self.categories.delete(command.category_id)


@dataclass(frozen=True)
class CategoryTools:
    """The category use cases a presenter may drive; no repository is exposed."""

    create: CreateCategory
    rename: RenameCategory
    recolor: UpdateCategoryColor
    delete: DeleteCategory
    list: ListCategories
