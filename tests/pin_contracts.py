"""Shared fake/Mongo FR-12 CAS and recent-page behavior."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from noteapp.domain.errors import ValidationError
from tests.repository_contracts import note


class PinRepositoryContract:
    def test_pin_and_text_mutation_race_has_exactly_one_winner(self, pin_notes):
        original = pin_notes.create(note(), "race")
        pinned = original.with_pinned(True)
        edited = original.edited(
            title="Edited",
            content="Edited",
            priority=original.priority,
            category_id=None,
            now=original.updated_at,
        )

        with ThreadPoolExecutor(max_workers=2) as pool:
            pin_result = pool.submit(pin_notes.set_pinned_if_version, pinned, original.version)
            text_result = pool.submit(pin_notes.update_if_version, edited, original.version)
            outcomes = (pin_result.result(), text_result.result())

        assert sorted(outcomes) == [False, True]
        saved = pin_notes.find_by_id(original.id)
        assert saved == (pinned if outcomes[0] else edited)

    def test_pin_cas_preserves_every_unrelated_field(self, pin_notes):
        original = pin_notes.create(note(), "original")
        pinned = original.with_pinned(True)

        assert pin_notes.set_pinned_if_version(pinned, 1)
        assert pin_notes.find_by_id(original.id) == pinned
        assert not pin_notes.set_pinned_if_version(original.with_pinned(True), 1)
        assert pin_notes.find_by_id(original.id) == pinned

        unpinned = pinned.with_pinned(False)
        assert pin_notes.set_pinned_if_version(unpinned, 2)
        assert pin_notes.find_by_id(original.id) == replace(original, version=3)

    @pytest.mark.parametrize("expected", [0, -1, True])
    def test_pin_cas_invalid_version(self, pin_notes, expected):
        with pytest.raises(ValidationError):
            pin_notes.set_pinned_if_version(note(version=2), expected)

    def test_pin_cas_missing_and_version_jump(self, pin_notes):
        assert not pin_notes.set_pinned_if_version(note(version=2, is_pinned=True), 1)
        with pytest.raises(ValidationError):
            pin_notes.set_pinned_if_version(note(version=3, is_pinned=True), 1)

    @pytest.mark.parametrize("pinned_count", [0, 20, 50])
    def test_recent_pages_cross_pin_partition_without_missing_or_duplicate(
        self, pin_notes, pinned_count
    ):
        originals = [pin_notes.create(note(is_pinned=i < pinned_count), str(i)) for i in range(60)]
        expected = sorted(
            originals, key=lambda item: (item.is_pinned, item.updated_at, item.id), reverse=True
        )

        seen = []
        cursor = None
        for _ in range(3):
            page = pin_notes.list_recent(30, cursor)
            seen.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                break

        assert cursor is None
        assert seen == expected
