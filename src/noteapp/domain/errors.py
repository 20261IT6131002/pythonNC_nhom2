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
