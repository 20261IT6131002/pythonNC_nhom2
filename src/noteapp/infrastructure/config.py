"""Configuration for the isolated Phase 1 development slice."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from noteapp.domain.errors import ValidationError


@dataclass(frozen=True)
class Config:
    mongo_uri: str = field(repr=False)
    db_name: str = "noteapp_dev"
    timeout_ms: int = 3000

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.mongo_uri)
            valid = parsed.scheme == "mongodb" and parsed.hostname in {
                "127.0.0.1",
                "localhost",
                "::1",
            }
            port = parsed.port
            valid = valid and (port is None or 1 <= port <= 65535)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValidationError(
                "Phase 1 requires a loopback Mongo URI configured in the environment."
            )
        if not isinstance(self.db_name, str) or not re.fullmatch(
            r"noteapp_dev(?:_[A-Za-z0-9_]+)?|noteapp_test_[A-Za-z0-9_]+", self.db_name
        ):
            raise ValidationError("Use an isolated noteapp_dev or noteapp_test_* database.")
        if type(self.timeout_ms) is not int or not 100 <= self.timeout_ms <= 30000:
            raise ValidationError("Mongo timeout must be between 100 and 30000 milliseconds.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Config":
        env = os.environ if environ is None else environ
        try:
            timeout = int(env.get("NOTEAPP_MONGO_TIMEOUT_MS", "3000"))
        except ValueError:
            raise ValidationError("Mongo timeout must be an integer.") from None
        return cls(
            env.get("NOTEAPP_MONGO_URI", ""), env.get("NOTEAPP_DB_NAME", "noteapp_dev"), timeout
        )
