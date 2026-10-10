"""Category lookup and seed contract."""

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
