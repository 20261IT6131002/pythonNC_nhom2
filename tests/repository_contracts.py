"""M5: adapter-neutral behavior reused by fake and real Mongo contract tests."""

import unicodedata
from dataclasses import replace
from datetime import timedelta
from secrets import token_hex
from uuid import uuid4

import pytest

from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import (
    CategoryInUse,
    CategoryNotFound,
    DuplicateCategory,
    ValidationError,
)
from noteapp.domain.value_objects.priority import Priority
from tests.fakes import FakeClock


def note(**changes):
    now = FakeClock().now()
    return replace(
        Note(token_hex(12), "Ghi chú", "Nội dung", Priority.MEDIUM, None, 1, now, now),
        **changes,
    )


class RepositoryContract:
    """Concrete test classes supply fresh notes/categories through repositories."""

    def test_create_and_read_back(self, repositories):
        notes, categories = repositories
        category = Category(token_hex(12), " Study ", "#123456", FakeClock().now())
        categories.create(category)
        original = note(category_id=category.id, priority=Priority.HIGH)
        saved = notes.create(original, str(uuid4()))
        assert saved == original
        assert notes.find_by_id(saved.id) == saved
        assert saved.created_at.utcoffset() == timedelta(0)
        assert categories.find_by_id(category.id) == category
        assert notes.find_by_id(token_hex(12)) is None
        assert categories.find_by_id(token_hex(12)) is None

    def test_create_retry_after_edit_returns_current_persisted_note(self, repositories):
        notes, _ = repositories
        operation_id = str(uuid4())
        saved = notes.create(note(), operation_id)
        edited = saved.edited(
            title="Edited",
            content="Keep this",
            priority=Priority.HIGH,
            category_id=None,
            now=saved.updated_at + timedelta(seconds=1),
        )
        assert notes.update_if_version(edited, saved.version)
        assert notes.create(note(title="Changed retry"), operation_id) == edited
        assert notes.list_recent(30).items == (edited,)

    def test_cas_rejects_stale_write_without_changing_persisted_note(self, repositories):
        notes, _ = repositories
        saved = notes.create(note(), str(uuid4()))
        edited = saved.edited(
            title="Winner",
            content="First write",
            priority=Priority.LOW,
            category_id=None,
            now=saved.updated_at + timedelta(seconds=1),
        )
        assert notes.update_if_version(edited, 1)
        assert not notes.update_if_version(replace(edited, content="Stale overwrite"), 1)
        persisted = notes.find_by_id(saved.id)
        assert persisted == edited
        assert persisted.version == 2
        assert persisted.created_at == saved.created_at

    def test_cas_returns_false_for_missing_note(self, repositories):
        notes, _ = repositories
        assert not notes.update_if_version(note(version=2), 1)
        assert notes.list_recent(30).items == ()

    @pytest.mark.parametrize("expected_version", [0, -1, True])
    def test_cas_rejects_invalid_expected_version(self, repositories, expected_version):
        notes, _ = repositories
        saved = notes.create(note(), str(uuid4()))
        with pytest.raises(ValidationError):
            notes.update_if_version(replace(saved, version=2), expected_version)
        assert notes.find_by_id(saved.id) == saved

    def test_cas_rejects_version_jump(self, repositories):
        notes, _ = repositories
        saved = notes.create(note(), str(uuid4()))
        with pytest.raises(ValidationError):
            notes.update_if_version(replace(saved, version=3), 1)
        assert notes.find_by_id(saved.id) == saved

    @pytest.mark.parametrize("limit", [0, 101, True])
    def test_repository_rejects_unbounded_page_size(self, repositories, limit):
        with pytest.raises(ValidationError):
            repositories[0].list_recent(limit)

    @pytest.mark.parametrize("cursor", ["bad", "[]", {"$where": "unsafe"}])
    def test_repository_rejects_invalid_cursor(self, repositories, cursor):
        with pytest.raises(ValidationError):
            repositories[0].list_recent(30, cursor)

    def test_paging_orders_timestamps_and_breaks_ties_by_id(self, repositories):
        notes, _ = repositories
        saved = [
            notes.create(
                note(updated_at=FakeClock().now() + timedelta(seconds=i % 3)), str(uuid4())
            )
            for i in range(7)
        ]
        expected = sorted(saved, key=lambda item: (item.updated_at, item.id), reverse=True)
        seen, cursor = [], None
        for _ in range(4):
            page = notes.list_recent(2, cursor)
            assert len(page.items) <= 2
            seen.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        assert cursor is None
        assert seen == expected
        assert len({item.id for item in seen}) == 7

    def test_newer_insert_between_pages_does_not_repeat_older_records(self, repositories):
        notes, _ = repositories
        saved = [notes.create(note(), str(uuid4())) for _ in range(4)]
        expected = sorted(saved, key=lambda item: (item.updated_at, item.id), reverse=True)
        first = notes.list_recent(2)
        assert first.items == tuple(expected[:2])
        assert first.next_cursor is not None
        newer = notes.create(
            note(updated_at=FakeClock().now() + timedelta(seconds=1)), str(uuid4())
        )
        second = notes.list_recent(2, first.next_cursor)
        assert second.items == tuple(expected[2:])
        assert second.next_cursor is None
        assert notes.list_recent(2).items[0] == newer

    def test_category_uniqueness_uses_trim_and_unicode_casefold(self, repositories):
        _, categories = repositories
        original = Category(token_hex(12), " Straße ", "#123456", FakeClock().now())
        categories.create(original)
        with pytest.raises(DuplicateCategory):
            categories.create(Category(token_hex(12), "STRASSE", "#654321", FakeClock().now()))
        assert categories.list_all() == (original,)

    def test_category_uniqueness_rejects_canonical_unicode_equivalents(self, repositories):
        _, categories = repositories
        original = Category(token_hex(12), "Học tập", "#123456", FakeClock().now())
        categories.create(original)
        decomposed = unicodedata.normalize("NFD", "Học tập")
        with pytest.raises(DuplicateCategory):
            categories.create(Category(token_hex(12), decomposed, "#654321", FakeClock().now()))
        assert categories.list_all() == (original,)

    def test_category_catalog_is_ordered_by_normalized_name(self, repositories):
        _, categories = repositories
        saved = [
            categories.create(Category(token_hex(12), name, "#123456", FakeClock().now()))
            for name in ("Zebra", " beta ", "Alpha")
        ]
        assert categories.list_all() == tuple(sorted(saved, key=lambda item: item.name_key))

    def _category(self, categories, name="Study", color="#123456"):
        return categories.create(Category(token_hex(12), name, color, FakeClock().now()))

    def test_category_update_keeps_id_and_changes_name_and_color(self, repositories):
        _, categories = repositories
        original = self._category(categories)
        updated = categories.update(original.renamed(" Work ").recolored("#ABCDEF"))
        assert (updated.id, updated.name, updated.color_hex) == (original.id, "Work", "#ABCDEF")
        assert categories.find_by_id(original.id) == updated
        assert categories.list_all() == (updated,)

    def test_category_update_allows_case_only_rename_of_itself(self, repositories):
        _, categories = repositories
        original = self._category(categories, "study")
        assert categories.update(original.renamed("STUDY")).name == "STUDY"

    def test_category_rename_into_duplicate_is_rejected_and_unchanged(self, repositories):
        _, categories = repositories
        first = self._category(categories, "Alpha")
        second = self._category(categories, "Beta")
        with pytest.raises(DuplicateCategory):
            categories.update(second.renamed("ALPHA"))
        assert categories.find_by_id(second.id) == second
        assert categories.find_by_id(first.id) == first

    def test_category_update_missing_is_not_found(self, repositories):
        _, categories = repositories
        ghost = Category(token_hex(12), "Ghost", "#123456", FakeClock().now())
        with pytest.raises(CategoryNotFound):
            categories.update(ghost)

    def test_delete_unused_category_removes_it(self, repositories):
        _, categories = repositories
        category = self._category(categories)
        assert categories.count_notes_by_category(category.id) == 0
        categories.delete(category.id)
        assert categories.find_by_id(category.id) is None
        assert categories.list_all() == ()
        categories.create(Category(token_hex(12), "Study", "#123456", FakeClock().now()))

    def test_delete_referenced_category_is_rejected_and_notes_untouched(self, repositories):
        notes, categories = repositories
        category = self._category(categories)
        saved = notes.create(note(category_id=category.id), str(uuid4()))
        assert categories.count_notes_by_category(category.id) == 1
        with pytest.raises(CategoryInUse):
            categories.delete(category.id)
        assert categories.find_by_id(category.id) == category
        assert notes.find_by_id(saved.id) == saved

    def test_delete_missing_category_is_not_found(self, repositories):
        _, categories = repositories
        with pytest.raises(CategoryNotFound):
            categories.delete(token_hex(12))

    def test_rename_does_not_change_note_reference(self, repositories):
        notes, categories = repositories
        category = self._category(categories)
        saved = notes.create(note(category_id=category.id), str(uuid4()))
        categories.update(category.renamed("Renamed"))
        assert notes.find_by_id(saved.id).category_id == category.id
