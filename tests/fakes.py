"""QA-owned deterministic ports for core and presenter tests."""

import json
from datetime import datetime, timezone
from threading import Lock

from noteapp.application.ports.note_repository import NotePage
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import DuplicateCategory, ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_id


class FakeClock:
    def __init__(self, value=None):
        self.value = value or datetime(2026, 10, 9, 12, tzinfo=timezone.utc)

    def now(self):
        return self.value


class FakeNotes:
    def __init__(self):
        self.items = {}
        self.operations = {}
        self.lock = Lock()

    def create(self, note, operation_id):
        with self.lock:
            if operation_id not in self.operations:
                self.items[note.id] = note
                self.operations[operation_id] = note.id
            return self.items[self.operations[operation_id]]

    def find_by_id(self, note_id):
        return self.items.get(note_id)

    def list_recent(self, limit, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError("Page size must be between 1 and 100.")
        with self.lock:
            items = sorted(self.items.values(), key=lambda n: (n.updated_at, n.id), reverse=True)
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 512:
                    raise ValueError
                payload = json.loads(cursor)
                if not isinstance(payload, list) or len(payload) != 2:
                    raise ValueError
                boundary = (
                    utc_datetime(datetime.fromisoformat(payload[0])),
                    validate_id(payload[1]),
                )
            except (ValueError, TypeError, OverflowError):
                raise ValidationError("Invalid pagination cursor.") from None
            items = [item for item in items if (item.updated_at, item.id) < boundary]
        page = tuple(items[:limit])
        next_cursor = (
            json.dumps([page[-1].updated_at.isoformat(), page[-1].id])
            if len(items) > limit
            else None
        )
        return NotePage(page, next_cursor)

    def update_if_version(self, note, expected_version):
        if type(expected_version) is not int or expected_version < 1:
            raise ValidationError("Expected version must be a positive integer.")
        if note.version != expected_version + 1:
            raise ValidationError("Version must advance by one.")
        with self.lock:
            current = self.items.get(note.id)
            if current is None or current.version != expected_version:
                return False
            self.items[note.id] = note
            return True


class FakeCategories:
    def __init__(self):
        self.items = {}

    def create(self, category: Category):
        if any(item.name_key == category.name_key for item in self.items.values()):
            raise DuplicateCategory("Category already exists.")
        self.items[category.id] = category
        return category

    def find_by_id(self, category_id):
        return self.items.get(category_id)

    def list_all(self):
        return tuple(sorted(self.items.values(), key=lambda item: item.name_key))
