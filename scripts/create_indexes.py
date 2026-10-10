"""Add reviewed indexes, or inspect them without writing using --dry-run."""

import argparse

from noteapp.domain.errors import NoteAppError
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes, plan_indexes
from noteapp.infrastructure.mongo.migrations import schema_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        config = Config.from_env()
        with create_client(config) as client:
            ping(client)
            if args.dry_run:
                report = plan_indexes(client[config.db_name])
                for name, status in report:
                    print(f"{name}: {status}")
                for name, count in schema_report(client[config.db_name]).items():
                    print(f"{name}: {count}")
                return 1 if any(status == "incompatible" for _, status in report) else 0
            create_indexes(client[config.db_name])
        print("NoteApp indexes are ready.")
        return 0
    except NoteAppError:
        print("Index setup failed. Check the isolated Mongo configuration and connection.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
