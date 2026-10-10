"""P1-08: add indexes to the configured isolated DB, never migrate or delete."""

from noteapp.domain.errors import NoteAppError
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes


def main() -> int:
    try:
        config = Config.from_env()
        with create_client(config) as client:
            ping(client)
            create_indexes(client[config.db_name])
        print("Phase 1 indexes are ready.")
        return 0
    except NoteAppError:
        print("Index setup failed. Check the isolated Mongo configuration and connection.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
