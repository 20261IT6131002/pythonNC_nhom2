"""QA-owned deterministic ports for core and presenter tests."""

from datetime import datetime, timezone
from threading import Lock

from noteapp.application.ports.note_repository import NotePage
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import DuplicateCategory, ValidationError


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
        items = sorted(self.items.values(), key=lambda n: (n.updated_at, n.id), reverse=True)
        offset = int(cursor or "0")
        page = tuple(items[offset : offset + limit])
        next_cursor = str(offset + limit) if offset + limit < len(items) else None
        return NotePage(page, next_cursor)

    def update_if_version(self, note, expected_version):
        with self.lock:
            current = self.items.get(note.id)
            if current is None or current.version != expected_version:
                return False
            if note.version != expected_version + 1:
                raise ValidationError("Version must advance by one.")
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
