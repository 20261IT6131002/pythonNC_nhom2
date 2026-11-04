"""Revision-aware local persistence; callers never provide paths or raw queries."""

from typing import Protocol, runtime_checkable

from noteapp.application.dto.local_draft import DraftHeader, LocalDraft


@runtime_checkable
class DraftStore(Protocol):
    def save_if_newer(self, draft: LocalDraft) -> bool:
        """Store newer snapshots, acknowledge identical retries and ignore stale writes."""

    def get(self, draft_id: str) -> LocalDraft | None:
        """Authenticate a snapshot; None means the record is absent."""

    def list_recoverable(self) -> tuple[DraftHeader, ...]:
        """Discover opaque identities independently of Mongo and secret availability."""

    def delete_if_revision(self, draft_id: str, revision: int) -> bool:
        """ACK cleanup preserves newer snapshots and fences covered late writes."""

    def delete(self, draft_id: str) -> None:
        """Explicit discard also fences in-flight writes for this identity."""
