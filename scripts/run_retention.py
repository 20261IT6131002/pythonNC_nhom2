"""Inspect eligible text-only trash; --apply explicitly performs one bounded batch."""

import argparse

from noteapp.domain.errors import NoteAppError
from noteapp.domain.policies.delete_policy import retention_cutoff
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import SystemClock, create_client, ping
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from noteapp.infrastructure.scheduler.purge_worker import PurgeWorker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        config, clock = Config.from_env(), SystemClock()
        with create_client(config) as client:
            ping(client)
            repo = MongoTrashRepository(client[config.db_name])
            if args.apply:
                result = PurgeWorker(repo, clock).run_once(args.limit)
                print(
                    f"purged={result.purged} conflicted={result.conflicted} "
                    f"blocked={result.blocked}"
                )
            else:
                count = len(repo.expired_candidates(retention_cutoff(clock.now()), args.limit))
                print(f"eligible={count}; no writes")
        return 0
    except NoteAppError:
        print("Retention could not complete. Check the isolated database and configuration.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
