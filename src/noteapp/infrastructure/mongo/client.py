"""Lazy Mongo construction and infrastructure time implementation."""

from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from noteapp.domain.errors import RepositoryUnavailable
from noteapp.infrastructure.config import Config


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def create_client(config: Config) -> MongoClient:
    return MongoClient(
        config.mongo_uri,
        connect=False,
        tz_aware=True,
        tzinfo=timezone.utc,
        serverSelectionTimeoutMS=config.timeout_ms,
        connectTimeoutMS=config.timeout_ms,
        socketTimeoutMS=config.timeout_ms,
        timeoutMS=config.timeout_ms,
    )


def ping(client: MongoClient) -> None:
    try:
        client.admin.command("ping")
    except PyMongoError:
        raise RepositoryUnavailable("MongoDB is not available.") from None
