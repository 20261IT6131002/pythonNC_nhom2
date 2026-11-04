"""R1-01 pin normalization. Stop other writers, back up, plan, then apply explicitly."""

import argparse
import json

from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.migrations import normalize_pinned, pin_schema_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    config = Config.from_env()
    with create_client(config) as client:
        ping(client)
        database = client[config.db_name]
        print(json.dumps(pin_schema_report(database), sort_keys=True))

        if args.apply:
            print(json.dumps({"modified_count": normalize_pinned(database)}))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
