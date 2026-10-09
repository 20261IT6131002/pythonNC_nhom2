"""Priority order is explicit, never alphabetical."""

from enum import Enum


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def rank(self) -> int:
        return {Priority.HIGH: 3, Priority.MEDIUM: 2, Priority.LOW: 1}[self]
