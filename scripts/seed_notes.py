"""P1-16: deterministic repeatable demo seeds; no delete/reset behavior."""

import argparse
from secrets import token_hex
from uuid import NAMESPACE_URL, uuid5

from noteapp.application.commands.create import CreateNote
from noteapp.application.dto.note_input import CreateNoteInput
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import DuplicateCategory, NoteAppError
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import SystemClock, create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository


def seed_categories(categories: MongoCategoryRepository, clock: SystemClock) -> None:
    for name, color in (("Học tập", "#2563EB"), ("Công việc", "#D97706"), ("Cá nhân", "#059669")):
        try:
            categories.create(Category(token_hex(12), name, color, clock.now()))
        except DuplicateCategory:
            continue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=0, help="0 seeds categories only; maximum 1000"
    )
    args = parser.parse_args()
    if not 0 <= args.count <= 1000:
        parser.error("--count must be between 0 and 1000")
    try:
        config = Config.from_env()
        with create_client(config) as client:
            ping(client)
            database = client[config.db_name]
            create_indexes(database)
            categories, clock = MongoCategoryRepository(database), SystemClock()
            seed_categories(categories, clock)
            create = CreateNote(MongoNoteRepository(database), categories, clock)
            catalog = categories.list_all()
            for i in range(args.count):
                create.execute(
                    CreateNoteInput(
                        f"Ghi chú mẫu {i + 1:03d}",
                        f"Nội dung tiếng Việt mẫu {i + 1}.",
                        tuple(Priority)[i % 3],
                        catalog[i % len(catalog)].id,
                        str(uuid5(NAMESPACE_URL, f"noteapp-phase1-demo-{i}")),
                    )
                )
        print("Demo seed completed without deleting existing data.")
        return 0
    except NoteAppError:
        print("Seed failed. Check the isolated Mongo configuration and connection.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
