"""Bounded text-only retention job invoked by the existing worker pool/CLI."""

from dataclasses import dataclass

from noteapp.application.ports.clock import Clock
from noteapp.domain.errors import Conflict, NotFound, ValidationError
from noteapp.domain.policies.delete_policy import retention_cutoff
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository


@dataclass(frozen=True)
class RetentionReport:
    purged: int = 0
    conflicted: int = 0
    blocked: int = 0


class PurgeWorker:
    def __init__(self, repo: MongoTrashRepository, clock: Clock) -> None:
        self.repo, self.clock = repo, clock

    def run_once(self, limit: int = 100) -> RetentionReport:
        cutoff = retention_cutoff(self.clock.now())
        rows = self.repo.expired_candidates(cutoff, limit)
        purged = conflicted = blocked = 0
        for row in rows:
            try:
                purged += int(self.repo.purge_expired(row.note.id, row.note.version, cutoff))
            except (Conflict, NotFound):
                conflicted += 1
            except ValidationError:
                blocked += 1
        return RetentionReport(purged, conflicted, blocked)
