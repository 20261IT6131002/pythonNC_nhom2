"""Remove attachment payloads that no note references once a grace period has passed.

Covers the compensating-cleanup gaps: a failed delete after a swap or purge, and a process
that died between upload and the note update. Notes in the trash still reference their image,
so they protect it. The grace period keeps in-flight uploads safe.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from noteapp.domain.errors import RepositoryUnavailable
from noteapp.domain.policies.note_validation import utc_datetime
from noteapp.infrastructure.attachment.hybrid_store import BLOB_COLLECTION, BUCKET_NAME

DEFAULT_GRACE = timedelta(minutes=15)


@dataclass(frozen=True)
class ReconcileReport:
    removed_inline: int = 0
    removed_gridfs: int = 0

    @property
    def removed(self) -> int:
        return self.removed_inline + self.removed_gridfs


class MongoAttachmentReconciler:
    def __init__(self, database: Database, grace: timedelta = DEFAULT_GRACE) -> None:
        self.notes = database.notes
        self.blobs = database[BLOB_COLLECTION]
        self.files = database[BUCKET_NAME + ".files"]
        self.chunks = database[BUCKET_NAME + ".chunks"]
        self.grace = grace

    def _referenced(self, identifier: ObjectId) -> bool:
        return self.notes.count_documents({"attachment.storage_key": str(identifier)}, limit=1) > 0

    def run_once(self, now: datetime, limit: int = 100) -> ReconcileReport:
        """Delete up to `limit` unreferenced payloads older than the grace period."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise RepositoryUnavailable("Reconcile batch must be between 1 and 1000.")
        cutoff = utc_datetime(now) - self.grace
        inline = gridfs_removed = 0
        try:
            for document in self.blobs.find({"created_at": {"$lte": cutoff}}, {"_id": 1}).sort(
                "_id", 1
            ):
                if inline + gridfs_removed >= limit:
                    break
                if not self._referenced(document["_id"]):
                    inline += self.blobs.delete_one({"_id": document["_id"]}).deleted_count
            for document in self.files.find(
                {"metadata.created_at": {"$lte": cutoff}}, {"_id": 1}
            ).sort("_id", 1):
                if inline + gridfs_removed >= limit:
                    break
                if not self._referenced(document["_id"]):
                    self.chunks.delete_many({"files_id": document["_id"]})
                    gridfs_removed += self.files.delete_one({"_id": document["_id"]}).deleted_count
        except PyMongoError:
            raise RepositoryUnavailable("Attachment reconciliation was not acknowledged.") from None
        return ReconcileReport(inline, gridfs_removed)
