"""Typed errors exposed by core contracts; messages never contain private input."""


class NoteAppError(Exception):
    """Base error for the technical slice."""


class ValidationError(NoteAppError):
    """Invalid domain or application input."""


class NotFound(NoteAppError):
    """The requested active record does not exist."""


class Conflict(NoteAppError):
    """The expected version no longer matches."""


class RepositoryUnavailable(NoteAppError):
    """Persistence did not acknowledge the operation."""


class DuplicateCategory(NoteAppError):
    """A normalized category name already exists."""


class CategoryNotFound(NotFound):
    """The requested category does not exist."""


class CategoryInUse(NoteAppError):
    """The category is still referenced by at least one note."""


class AttachmentError(NoteAppError):
    """Base class for image attachment failures."""


class UnsupportedImage(AttachmentError):
    """The payload is not an allowed image format."""


class ImageTooLarge(AttachmentError):
    """The payload exceeds the size or pixel limit."""


class CorruptedImage(AttachmentError):
    """The payload cannot be decoded as an image."""


class AttachmentStoreFailure(RepositoryUnavailable):
    """The attachment store did not acknowledge the operation."""


class NotificationFailure(NoteAppError):
    """The operating system did not accept the notification."""
