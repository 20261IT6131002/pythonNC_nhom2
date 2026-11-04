# R1-01 — FR-12 pin contract

Status: **Proposed for team review**, implemented on the user's instruction to implement
[R1_PLAN_01_PINNED_NOTES](../../../R1_PLAN_01_PINNED_NOTES.md). No PM/M1 approval is inferred.
Base: `develop` at `ea9c557f8c0bbd0233d2dc9067046cad3e06e73a`.
Requirements: FR-12/AC-12a, FR-11, BR-10, BR-14, NFR-MAIN-01, CST-02/03.
Reviewer: M1 with M2/M3/M4; review and remote CI remain merge gates.

| Decision | Implementation basis awaiting review |
| --- | --- |
| PIN-D01 | Strict `bool`, default `False`; numeric/string/null flags rejected. |
| PIN-D02 | `SetPinnedInput(note_id, expected_version, target)` expresses explicit intent. |
| PIN-D03 | Active-only CAS using `expected_version`. |
| PIN-D04 | A changed flag increments version exactly once. |
| PIN-D05 | Pin/unpin preserves `updated_at`. |
| PIN-D06 | Only active notes expose pin actions. |
| PIN-D07 | Trash and restore preserve the flag. Purge accepts this known field. |
| PIN-D08 | Trash ordering/cursors retain their existing semantics. |
| PIN-D09 | Same target with current expected version is a no-op; stale version conflicts. |
| PIN-D10 | Legacy reads default a missing flag to false. |
| PIN-D11 | Explicit idempotent migration fills only missing flags, including trash. |
| PIN-D12 | Active cursors include a strictly boolean partition key; old cursors fail validation. |
| PIN-D13 | Text indicator/action on cards, keyboard P on selected card, editor toolbar action. |
| PIN-D14 | Active list/search sorts by `is_pinned DESC` before the selected tuple. |

Repository port: `set_pinned_if_version(note: Note, expected_version: int) -> bool`.
The write sets only `is_pinned` and increments `version`; content, timestamps, category,
attachment, reminder and internal delivery claims are untouched. A failed CAS is classified
as NOT_FOUND or CONFLICT after an active read. No automatic overwrite retry is performed.

Category ordering keeps the existing server aggregation. Groups are now keyed by both
normalized category (`missing -> null`) and pin flag. Each group retrieves at most limit+1
matching notes; the final server sort uses `(pin DESC, category key ASC, ID ASC)`.
Cursor bounds permit later pin partitions even if their category key sorts earlier.
This is an implementation choice equivalent to the plan's two-partition page builder,
without materializing all matching notes in Python.

Editor pin success adopts version/flag while preserving title, content, priority, category,
revision, phase, attachment and reminder. Save/image/reminder/trash/pin share the mutation
guard. Results for another request or a closed presenter are ignored. Successful pin
invalidates the current list/cursor and requests page one.

Migration and rollback are documented in the [README](../../../README.md).
Evidence and outstanding release gates belong in the
[R1 test report](../../testing/R1_PIN_TEST_REPORT.md).
