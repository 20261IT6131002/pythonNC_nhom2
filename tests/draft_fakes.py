"""Core-only deterministic draft ports; no filesystem, keyring, Mongo or Tk imports."""

from dataclasses import replace
from threading import RLock
from uuid import uuid4

from noteapp.application.dto.local_draft import DraftHeader, LocalDraft, validate_draft_id
from noteapp.domain.errors import Conflict, ValidationError
from noteapp.domain.value_objects.priority import Priority
from tests.fakes import FakeClock


def draft(**changes):
    return replace(
        LocalDraft(
            str(uuid4()),
            None,
            str(uuid4()),
            0,
            1,
            "Bản nháp tiếng Việt",
            "private-draft-marker",
            Priority.MEDIUM,
            None,
            FakeClock().now(),
        ),
        **changes,
    )


class FakeDraftStore:
    def __init__(self):
        self.items = {}
        self.fences = {}
        self.discarded = set()
        self.lock = RLock()
        self.error = None

    def _check(self):
        if self.error is not None:
            raise self.error

    def save_if_newer(self, incoming):
        self._check()

        with self.lock:
            if incoming.draft_id in self.discarded:
                return False

            if incoming.revision <= self.fences.get(incoming.draft_id, 0):
                return False

            current = self.items.get(incoming.draft_id)

            if current is not None:
                if current.revision > incoming.revision:
                    return False

                if current.revision == incoming.revision:
                    if replace(incoming, updated_at=current.updated_at) != current:
                        raise Conflict("Draft revision collision.")

                    return True

            self.items[incoming.draft_id] = incoming
            return True

    def get(self, draft_id):
        validate_draft_id(draft_id)
        self._check()
        return self.items.get(draft_id)

    def list_recoverable(self):
        self._check()
        return tuple(DraftHeader(key) for key in sorted(self.items))

    def delete_if_revision(self, draft_id, revision):
        validate_draft_id(draft_id)
        self._check()

        if type(revision) is not int or revision < 1:
            raise ValidationError("Invalid acknowledged revision.")

        with self.lock:
            self.fences[draft_id] = max(revision, self.fences.get(draft_id, 0))
            current = self.items.get(draft_id)

            if current is not None and current.revision > revision:
                return False

            self.items.pop(draft_id, None)
            return True

    def delete(self, draft_id):
        validate_draft_id(draft_id)
        self._check()

        with self.lock:
            self.items.pop(draft_id, None)
            self.discarded.add(draft_id)
