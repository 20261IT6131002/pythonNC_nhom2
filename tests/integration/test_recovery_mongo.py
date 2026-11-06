"""Recovery-specific remote idempotency/lifecycle guards against real Mongo."""

from uuid import uuid4

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.dto.note_input import CreateNoteInput
from noteapp.domain.errors import Conflict
from noteapp.domain.value_objects.priority import Priority
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository, MongoNoteRepository
from noteapp.infrastructure.mongo.trash_repository import MongoTrashRepository
from tests.draft_fakes import draft
from tests.fakes import FakeClock
from tests.integration.test_encrypted_drafts import make_store
from tests.security_fakes import FakeSecretStore

pytestmark = pytest.mark.integration


def test_ack_loss_retry_for_a_trashed_operation_is_a_conflict_and_keeps_local_draft(
    mongo_database, tmp_path
):
    database = mongo_database[0]
    notes, clock = MongoNoteRepository(database), FakeClock()
    create = CreateNote(notes, MongoCategoryRepository(database), clock)
    command = CreateNoteInput("Title", "Content", Priority.MEDIUM, None, str(uuid4()))
    saved = create.execute(command)
    MongoTrashRepository(database).move_to_trash(saved.note_id, saved.version, clock.now())
    store = make_store(tmp_path / "recovery", FakeSecretStore())
    snapshot = draft(client_operation_id=command.client_operation_id)

    try:
        store.save_if_newer(snapshot)
        with pytest.raises(Conflict):
            create.execute(command)
        assert store.get(snapshot.draft_id) == snapshot
        assert database.notes.count_documents({}) == 1
        assert database.notes.find_one({})["is_deleted"]
    finally:
        store.close()
