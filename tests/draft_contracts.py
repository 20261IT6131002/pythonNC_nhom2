"""Shared revision/ACK/discard contract, run against fake and real encrypted files."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from noteapp.application.ports.draft_store import DraftStore
from noteapp.domain.errors import Conflict, ValidationError
from tests.draft_fakes import draft


class DraftStoreContract:
    def test_persisted_snapshot_is_exact_and_identical_retry_is_idempotent(self, draft_store):
        snapshot = draft()
        assert isinstance(draft_store, DraftStore)
        assert draft_store.get(snapshot.draft_id) is None
        assert draft_store.save_if_newer(snapshot)
        assert draft_store.save_if_newer(snapshot)
        assert draft_store.get(snapshot.draft_id) == snapshot
        assert [item.draft_id for item in draft_store.list_recoverable()] == [snapshot.draft_id]

    def test_newer_wins_and_equal_revision_cannot_replace_a_different_payload(self, draft_store):
        original = draft()
        newer = replace(original, revision=2, content="newer content")
        assert draft_store.save_if_newer(newer)
        assert not draft_store.save_if_newer(original)

        with pytest.raises(Conflict):
            draft_store.save_if_newer(replace(newer, content="collision"))

        assert draft_store.get(original.draft_id) == newer

    def test_ack_cannot_delete_newer_or_resurrect_covered_writes(self, draft_store):
        original = draft()
        newer = replace(original, revision=2)
        draft_store.save_if_newer(newer)
        assert not draft_store.delete_if_revision(original.draft_id, 1)
        assert draft_store.get(original.draft_id) == newer
        assert draft_store.delete_if_revision(original.draft_id, 2)
        assert draft_store.get(original.draft_id) is None
        assert not draft_store.save_if_newer(original)
        assert not draft_store.save_if_newer(newer)
        assert draft_store.save_if_newer(replace(newer, revision=3))

    def test_ack_before_pending_first_write_and_explicit_discard_fence_the_identity(
        self, draft_store
    ):
        original = draft()
        assert draft_store.delete_if_revision(original.draft_id, 1)
        assert not draft_store.save_if_newer(original)
        draft_store.delete(original.draft_id)
        draft_store.delete(original.draft_id)
        assert not draft_store.save_if_newer(replace(original, revision=2))

    def test_many_identities_and_concurrent_revisions_are_independent(self, draft_store):
        first, second = draft(), draft()
        draft_store.save_if_newer(second)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    draft_store.save_if_newer, [replace(first, revision=i) for i in (5, 3, 7, 1)]
                )
            )

        assert draft_store.get(first.draft_id).revision == 7
        assert draft_store.get(second.draft_id) == second

    @pytest.mark.parametrize("identity", ["../bad", "", None, "not-a-uuid"])
    def test_paths_are_not_public_input(self, draft_store, identity):
        with pytest.raises(ValidationError):
            draft_store.get(identity)

        with pytest.raises(ValidationError):
            draft_store.delete(identity)
