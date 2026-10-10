"""Test-only independent reference model; native Mongo text semantics tested separately."""

import hashlib
import json
from dataclasses import asdict

from noteapp.application.dto.note_filter import SortMode
from noteapp.application.ports.note_repository import NotePage
from noteapp.application.ports.trash_repository import TrashedNote, TrashPage
from noteapp.application.queries.search_notes import validate_compiled
from noteapp.domain.errors import Conflict, NotFound, ValidationError
from noteapp.domain.policies.delete_policy import transition_note
from tests.fakes import FakeNotes


class FakePhase2(FakeNotes):
    def __init__(self, categories):
        super().__init__()
        self.categories = categories
        self.deleted = {}

    def search(self, criteria):
        validate_compiled(criteria)
        items = [n for n in self.items.values() if n.id not in self.deleted]
        items = [
            n
            for n in items
            if (criteria.category_id is None or n.category_id == criteria.category_id)
            and (criteria.priority is None or n.priority == criteria.priority)
            and (
                criteria.utc_start is None
                or getattr(n, criteria.date_field.value) >= criteria.utc_start
            )
            and (
                criteria.utc_end_exclusive is None
                or getattr(n, criteria.date_field.value) < criteria.utc_end_exclusive
            )
        ]
        if criteria.text:
            items = [
                n
                for n in items
                if criteria.text.casefold() in (n.title + " " + n.content).casefold()
            ]
        keys = {
            SortMode.UPDATED_AT: lambda n: (n.updated_at, n.id),
            SortMode.CREATED_AT: lambda n: (n.created_at, n.id),
            SortMode.PRIORITY: lambda n: (n.priority.rank, n.updated_at, n.id),
            SortMode.CATEGORY: lambda n: (
                self.categories.items[n.category_id].name_key
                if n.category_id in self.categories.items
                else "",
                n.id,
            ),
        }
        key = keys[criteria.sort]
        reverse = criteria.direction.value == "DESC"
        items.sort(key=key, reverse=reverse)
        values = asdict(criteria)
        values.pop("cursor")
        signature = hashlib.sha256(
            json.dumps(values, default=str, sort_keys=True).encode()
        ).hexdigest()
        if criteria.cursor:
            try:
                payload = json.loads(criteria.cursor)
                if payload["q"] != signature:
                    raise ValueError
                index = next(i for i, n in enumerate(items) if n.id == payload["id"])
                items = items[index + 1 :]
            except (ValueError, TypeError, KeyError, StopIteration):
                raise ValidationError("Invalid fake cursor.") from None
        page = tuple(items[: criteria.limit])
        cursor = (
            json.dumps({"q": signature, "id": page[-1].id}) if len(items) > criteria.limit else None
        )
        return NotePage(page, cursor)

    def _transition(self, note_id, version, target, now):
        with self.lock:
            note = self.items.get(note_id)
            if note is None:
                raise NotFound("Missing note.")
            moved = transition_note(note, version, note_id in self.deleted, target, now)
            self.items[note_id] = moved
            if target:
                self.deleted[note_id] = now
                return TrashedNote(moved, now)
            del self.deleted[note_id]
            return moved

    def move_to_trash(self, note_id, expected_version, now):
        return self._transition(note_id, expected_version, True, now)

    def restore(self, note_id, expected_version, now):
        return self._transition(note_id, expected_version, False, now)

    def list_trashed(self, limit, cursor=None):
        if cursor is not None:
            raise ValidationError("Reference fixture uses a single trash page.")
        rows = [TrashedNote(self.items[key], at) for key, at in self.deleted.items()]
        rows.sort(key=lambda row: (row.deleted_at, row.note.id), reverse=True)
        return TrashPage(tuple(rows[:limit]), None)

    def purge_confirmed(self, note_id, expected_version):
        with self.lock:
            note = self.items.get(note_id)
            if note is None:
                raise NotFound("Missing note.")
            if note.version != expected_version or note_id not in self.deleted:
                raise Conflict("State changed.")
            del self.items[note_id]
            del self.deleted[note_id]
