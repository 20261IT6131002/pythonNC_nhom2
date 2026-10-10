"""Adapter-neutral search/trash behavior, exercised unchanged by fake and Mongo."""

from dataclasses import replace
from datetime import date, timedelta
from secrets import token_hex
from uuid import uuid4

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.trash import TrashNote
from noteapp.application.dto.note_filter import SearchNotesCriteria, SortDirection, SortMode
from noteapp.application.dto.note_input import (
    CreateNoteInput,
    ListTrashInput,
    PurgeNoteInput,
    RestoreNoteInput,
    TrashNoteInput,
)
from noteapp.application.queries.list_trash import ListTrash
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.entities.category import Category
from noteapp.domain.errors import Conflict, NotFound, ValidationError
from noteapp.domain.value_objects.priority import Priority


class Phase2RepositoryContract:
    @pytest.mark.parametrize(
        ("sort", "direction"),
        [
            (SortMode.UPDATED_AT, SortDirection.DESC),
            (SortMode.CREATED_AT, SortDirection.ASC),
            (SortMode.CREATED_AT, SortDirection.DESC),
            (SortMode.PRIORITY, SortDirection.DESC),
            (SortMode.CATEGORY, SortDirection.ASC),
        ],
    )
    def test_ordered_pages_and_query_binding(self, phase2_repositories, sort, direction):
        notes, categories, search_repo, _, clock, zone = phase2_repositories
        create, query = CreateNote(notes, categories, clock), SearchNotes(search_repo, zone)
        catalog = [
            categories.create(Category(token_hex(12), name, "#123456", clock.now()))
            for name in ("Zebra", "Alpha")
        ]
        names = {n.id: n.name_key for n in catalog}
        saved = []
        for i in range(7):
            clock.value += timedelta(seconds=i % 2)
            saved.append(
                create.execute(
                    CreateNoteInput(
                        f"Contract {i}",
                        "Payload",
                        list(Priority)[i % 3],
                        catalog[i % 2].id if i % 3 else None,
                        str(uuid4()),
                    )
                )
            )
        keys = {
            SortMode.UPDATED_AT: lambda n: (n.updated_at, n.note_id),
            SortMode.CREATED_AT: lambda n: (n.created_at, n.note_id),
            SortMode.PRIORITY: lambda n: (n.priority.rank, n.updated_at, n.note_id),
            SortMode.CATEGORY: lambda n: (names.get(n.category_id, ""), n.note_id),
        }
        expected = sorted(saved, key=keys[sort], reverse=direction == SortDirection.DESC)
        command = SearchNotesCriteria(sort=sort, direction=direction, limit=2)
        first = query.execute(command)
        with pytest.raises(ValidationError):
            query.execute(replace(command, cursor=first.next_cursor, priority=Priority.LOW))
        seen = list(first.items)
        cursor = first.next_cursor
        while cursor is not None:
            page = query.execute(replace(command, cursor=cursor))
            seen.extend(page.items)
            cursor = page.next_cursor
        assert seen == expected

    def test_date_intersection_and_lifecycle(self, phase2_repositories):
        notes, categories, search_repo, trash_repo, clock, zone = phase2_repositories
        create, query = CreateNote(notes, categories, clock), SearchNotes(search_repo, zone)
        category = categories.create(Category(token_hex(12), "Study", "#123456", clock.now()))
        original = create.execute(
            CreateNoteInput(
                "Contract",
                "Exact payload",
                Priority.HIGH,
                category.id,
                str(uuid4()),
            )
        )
        criteria = SearchNotesCriteria(
            category_id=category.id,
            priority=Priority.HIGH,
            start_date=date(2026, 10, 9),
            end_date=date(2026, 10, 9),
        )
        assert query.execute(criteria).items == (original,)
        assert not query.execute(replace(criteria, priority=Priority.LOW)).items
        trash = TrashNote(trash_repo, clock)
        trash.execute(TrashNoteInput(original.note_id, 1))
        assert not query.execute(criteria).items
        deleted = ListTrash(trash_repo).execute(ListTrashInput()).items[0]
        assert deleted.note.version == 2 and deleted.note.content == original.content
        with pytest.raises(Conflict):
            trash.execute(TrashNoteInput(original.note_id, 1))
        restored = RestoreNote(trash_repo, clock).execute(RestoreNoteInput(original.note_id, 2))
        assert restored.note_id == original.note_id and restored.version == 3
        assert query.execute(criteria).items == (restored,)
        trash.execute(TrashNoteInput(original.note_id, 3))
        purge = PurgeNote(trash_repo)
        with pytest.raises(ValidationError):
            purge.execute(PurgeNoteInput(original.note_id, 4, False))
        assert len(ListTrash(trash_repo).execute().items) == 1
        purge.execute(PurgeNoteInput(original.note_id, 4, True))
        assert not ListTrash(trash_repo).execute().items
        with pytest.raises(NotFound):
            RestoreNote(trash_repo, clock).execute(RestoreNoteInput(original.note_id, 4))
