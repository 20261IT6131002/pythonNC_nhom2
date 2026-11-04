"""Category lookup, seed and management contract."""

from typing import Protocol, runtime_checkable

from noteapp.domain.entities.category import Category


@runtime_checkable
class CategoryRepository(Protocol):
    def create(self, category: Category) -> Category:
        """Persist a category or raise DuplicateCategory for a duplicate name_key."""

    def find_by_id(self, category_id: str) -> Category | None:
        """Return a category or None."""

    def list_all(self) -> tuple[Category, ...]:
        """Return the small category catalog ordered by normalized name."""

    def update(self, category: Category) -> Category:
        """Replace name/color of an existing category (ID never changes).

        Raises CategoryNotFound or DuplicateCategory for a colliding name_key.
        """

    def delete(self, category_id: str) -> None:
        """Delete an unreferenced category.

        Raises CategoryNotFound, or CategoryInUse while any note (active or trashed)
        still references it. Never rewrites notes.
        """

    def count_notes_by_category(self, category_id: str) -> int:
        """Return how many notes, including trashed ones, reference the category."""
