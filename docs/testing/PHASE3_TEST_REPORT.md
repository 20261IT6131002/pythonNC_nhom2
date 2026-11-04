# Phase 3 implementation and validation (3A: FR-04, FR-08 · 3B: FR-09, FR-10)

Branch `feat/phase3_plan1`, 2026-10-22. Plan: `PHASE3_PLAN_01_CATEGORY_IMAGE.md`.
Contract: [freeze](../srs/phase%203/01_PHASE3_CONTRACT_FREEZE.md), [ADR](../adr/ADR_PHASE3_CATEGORY_ATTACHMENT.md)
(both **Proposed**, not Accepted). Category-delete refusal and one image per note are
assumptions (SRS AC-04b and DEC-06 still open).

## Slices

| Task | Result |
|---|---|
| P3A-00 | Contract freeze + ADR written |
| P3A-01 | `CreateCategory/RenameCategory/UpdateCategoryColor/DeleteCategory/ListCategories`, `CategoryRepository.update/delete/count_notes_by_category`, `CategoryNotFound`, `CategoryInUse`, `ErrorCode.DUPLICATE/IN_USE` |
| P3A-02 | Mongo update/delete/count; delete = expiring marker -> count (active + trashed) -> conditional delete; unique index maps to `DuplicateCategory` |
| P3A-03 | Category window, presenter in workers, editor/sidebar choices refreshed by ID without restart |
| P3A-04 | `AttachmentRef`, `Note.attachment`, size policy, `AttachmentStore`/`ImageProcessor`/`NoteAttachmentRepository`/`ImageFileReader` ports |
| P3A-05 | Pillow validation (decode, format allowlist, pixel/side guard, 10 MiB) and 400 px PNG thumbnail |
| P3A-06 | `attachment_blobs` BinData (<= 1 MiB) and GridFS bucket `attachments`; orphan reconciler |
| P3A-07 | `AttachmentService` attach/replace/remove/get with compensating cleanup and CAS |
| P3A-08 | Editor image section, `AttachmentPresenter`, stale-result discard, save/trash blocked while an image change is in flight |
| P3A-09 | Purge and retention clean images when the trash repository has a store; fail-closed otherwise |

## Known limits and risks

- No cross-collection transaction: a note saved in the instant between a writer's category
  lookup and insert can still reference a category being deleted (dangling refs already render
  as uncategorized).
- A failed blob delete leaves an unreferenced payload until the reconciler runs (grace 15 min;
  runs with `NOTEAPP_ENABLE_RETENTION=1` or `scripts/run_retention.py --apply`).
- Previews are available for active notes only; trash shows image metadata.
- Pillow is a new runtime dependency (`pillow>=10.3,<13`), imported only in infrastructure.
- Not run: Windows/macOS, a performance benchmark with large images, CI (the workflow was not
  triggered), RTM spreadsheet update.

## Rollback
Additive schema, no migration: remove the Phase 3 code; notes keep an ignored `attachment`
field and Phase 2 purge refuses to delete them (fail-closed). Drop `attachment_blobs`,
`attachments.*` and index `idx_notes_attachment_key` only after confirming no note references
them.


---

# Phase 3B — reminders (FR-09, FR-10)

Plan: `PHASE3_PLAN_02_REMINDER_DELIVERY.md` · contract:
[freeze](../srs/phase%203/02_PHASE3_REMINDER_CONTRACT_FREEZE.md) · ADR:
[ADR_PHASE3_REMINDER_DELIVERY](../adr/ADR_PHASE3_REMINDER_DELIVERY.md) (both **Proposed**).
Reschedule-from-DELIVERED (R5) and the missed-reminder rule (R8) are assumptions: SRS DEC-05
is still open.

## Slices

| Task | Result |
|---|---|
| P3B-00 | Contract freeze + ADR |
| P3B-01 | `Reminder` entity/state machine (`ACTIVE/DELIVERED/CANCELLED`), `Note.reminder`, `with_reminder`, `reminder_policy` (DST-safe local→UTC, retry/lease constants) |
| P3B-02 | `ReminderRepository` port; `MongoReminderRepository` (embedded `notes.reminder`, CAS config, lease claim); partial index `idx_notes_reminder_due` |
| P3B-03 | `SetReminder` (set + reschedule), `CancelReminder`, `ReminderTools` |
| P3B-04 | Editor reminder section, `ReminderDialog`, `ReminderPresenter`, stale-result discard, save/trash blocked while a change is in flight |
| P3B-05 | `claim_next_due` / `mark_delivered` / `release_claim`; trashed notes excluded |
| P3B-06 | `NotificationGateway` port, `PlyerGateway` (lazy import, sanitized `NotificationFailure`) |
| P3B-07 | `ReminderPoller` (single non-daemon thread, `stop()` joins), results to UI via `TaskRunner.publish` |
| P3B-08 | Startup scan delivers missed reminders before the poller starts |
| P3B-09 | Outage / provider failure / race / shutdown handling and tests |
| P3B-10 | Full regression below |

## Evidence (2026-10-22, Linux, Python 3.14.4, Mongo 7.0 in a throwaway container)

```text
ruff check .            -> All checks passed
ruff format --check .   -> 181 files already formatted
pytest (whole suite)    -> 536 passed, 0 failed, 0 errors in 157 s
  unit 292 · contract 99 · integration 140 · ui 5
```

Integration ran against a throwaway `mongo:7.0` container with a raised file-descriptor limit
(`--ulimit nofile=65536:65536`) on a non-default port, using `NOTEAPP_TEST_MONGO_URI` and
`NOTEAPP_REQUIRE_MONGO=1`; the suite only creates and drops `noteapp_test_*` databases.
Reminder-specific tests: about 120 (unit entity/DST policy/use cases/delivery/poller/view
text, shared repository contract on fake **and** Mongo, gateway contract, Mongo claim races,
trash/restore/purge journey, DB outage, real-Tk scenario, real Tk + Mongo + poller scenario).

## Acceptance (plan §18)

| Requirement | Scenario | Automated evidence |
|---|---|---|
| FR-09 | set future → ACTIVE | `test_set_reminder`, UI scenario `reminder`, `test_phase3_reminder_…` |
| FR-09 | set past → reject | `test_past_or_current_time_is_rejected…`, UI scenario |
| FR-09 | DST gap / overlap / no zone → reject | `test_reminder_entity`, `test_set_reminder` |
| FR-09 | reschedule | `test_reschedule_*`, contract `test_reschedule_after_*` |
| FR-09 | cancel → no delivery | `test_cancel_*`, `test_cancelled_reminder_never_notifies`, Mongo race test |
| FR-10 | due → notify, once | `test_reminder_delivery`, `test_concurrent_pollers_deliver_each_reminder_exactly_once` |
| FR-10 | delivered → no duplicate | `test_delivered_reminder_is_not_repeated` |
| FR-10 | restart after due | `test_missed_reminders_after_restart…`, desktop scenario (startup scan then poller) |
| FR-10 | overlapping poll | 12-thread claim test: exactly one winner |
| FR-10 | OS notify fails | `test_os_failure_…`, `test_unexpected_provider_exception_…` (no leak), UI shows retry notice |
| FR-10 | trashed silent, restore fires | `test_trashed_note_is_silent…`, `test_full_journey_…` |
| NFR | poller not busy, clean shutdown | `test_reminder_poller` (backoff, join, stuck job, no daemon) |

Phase 1–3 journey (create → … → image → reminder → trash → restore → delivery → purge, image
and reminder surviving restore and both removed on purge): `test_phase3_journey_…`.

## Known limits and risks (Phase 3B)

- **Not exactly-once.** A crash between the OS call and `mark_delivered` re-notifies after the
  2-minute lease; `DELIVERED` means the OS call was accepted, not that a toast was shown.
- After 3 failed notification attempts a reminder stays `ACTIVE` and is no longer polled until
  the user sets a new time (UI says it is waiting). Not exercised against a real OS toast:
  tests replace the notification daemon with a recording gateway; Linux `plyer` needs
  `notify-send`/D-Bus and was **not** run against a real desktop session.
- Reminders only fire while the app is open (DEC-05 OPEN). Missed reminders are delivered at
  most 20 per pass; later passes continue.
- Cancel racing a claim can still show a notification already on its way (state ends `CANCELLED`).
- `describe_reminder` compares to the real clock for the "waiting" wording; the fake clock only
  drives core logic.
- Not run: Windows/macOS Tk and toast, CI (workflow not triggered), performance benchmark of the
  due query beyond the `explain` index check, RTM sign-off by QA/Tech Lead (rows marked
  "AUTOMATED PASS — pending review"), Tech Lead gates A–D.
- Integration test fixtures previously used a 2 s Mongo timeout and produced intermittent
  setup errors on a loaded host (also reproduced on the Plan 01 baseline). The fixture timeout
  is now 10 s (`tests/integration/conftest.py`); a stall of that size is absorbed, not hidden.

## Rollback
Additive schema, no migration. After removing the Phase 3B code, notes keep an ignored
`reminder` sub-document and the Phase 2 purge/retention refuse to delete notes that still
carry it (fail-closed, as for `attachment`); `$unset` the field first if such notes must be
purged. Drop index `idx_notes_reminder_due` afterwards if desired. The `plyer` dependency can
be removed together with the gateway.
