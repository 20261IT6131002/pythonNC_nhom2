"""INLINE (BinData, <= 1 MiB) and GridFS (<= 10 MiB) storage behind one port.

Keys are opaque hex strings. Payloads carry owner/created metadata so the reconciler can
find unreferenced ones. Display names are never used as file names or paths.
"""

from collections.abc import Callable
from datetime import datetime, timezone

import gridfs
from bson import Binary, ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from noteapp.application.ports.image_processor import ValidatedImage
from noteapp.domain.errors import AttachmentStoreFailure
from noteapp.domain.policies.attachment_policy import storage_kind_for
from noteapp.domain.value_objects.attachment_ref import AttachmentRef, StorageKind

BLOB_COLLECTION = "attachment_blobs"
BUCKET_NAME = "attachments"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _key(ref: AttachmentRef) -> ObjectId:
    if not ObjectId.is_valid(ref.storage_key):
        raise AttachmentStoreFailure("Attachment reference is not a valid storage key.")
    return ObjectId(ref.storage_key)


class MongoAttachmentStore:
    def __init__(self, database: Database, now: Callable[[], datetime] = _utc_now) -> None:
        self.blobs = database[BLOB_COLLECTION]
        self.bucket = gridfs.GridFSBucket(database, bucket_name=BUCKET_NAME)
        self.now = now

    def put(self, owner_note_id: str, image: ValidatedImage, display_name: str) -> AttachmentRef:
        kind = StorageKind(storage_kind_for(len(image.data)))
        created_at = self.now()
        try:
            if kind is StorageKind.INLINE:
                identifier = ObjectId()
                self.blobs.insert_one(
                    {
                        "_id": identifier,
                        "owner_note_id": owner_note_id,
                        "created_at": created_at,
                        "sha256": image.sha256,
                        "data": Binary(image.data),
                    }
                )
            else:
                identifier = self.bucket.upload_from_stream(
                    "attachment",
                    image.data,
                    metadata={
                        "owner_note_id": owner_note_id,
                        "created_at": created_at,
                        "sha256": image.sha256,
                    },
                )
        except PyMongoError:
            raise AttachmentStoreFailure(
                "Attachment storage did not acknowledge the write."
            ) from None
        return AttachmentRef(
            kind, str(identifier), image.mime_type, len(image.data), image.sha256, display_name
        )

    def get(self, ref: AttachmentRef) -> bytes:
        identifier = _key(ref)
        try:
            if ref.storage_kind is StorageKind.INLINE:
                document = self.blobs.find_one({"_id": identifier})
                if document is None:
                    raise AttachmentStoreFailure("Attachment payload is missing.")
                return bytes(document["data"])
            return self.bucket.open_download_stream(identifier).read()
        except gridfs.errors.NoFile:
            raise AttachmentStoreFailure("Attachment payload is missing.") from None
        except PyMongoError:
            raise AttachmentStoreFailure("Attachment storage could not be read.") from None

    def delete(self, ref: AttachmentRef) -> None:
        identifier = _key(ref)
        try:
            if ref.storage_kind is StorageKind.INLINE:
                self.blobs.delete_one({"_id": identifier})
            else:
                try:
                    self.bucket.delete(identifier)
                except gridfs.errors.NoFile:
                    pass
        except PyMongoError:
            raise AttachmentStoreFailure(
                "Attachment storage could not delete the payload."
            ) from None

    def exists(self, ref: AttachmentRef) -> bool:
        identifier = _key(ref)
        try:
            if ref.storage_kind is StorageKind.INLINE:
                return self.blobs.count_documents({"_id": identifier}, limit=1) == 1
            return any(True for _ in self.bucket.find({"_id": identifier}).limit(1))
        except PyMongoError:
            raise AttachmentStoreFailure("Attachment storage could not be queried.") from None
