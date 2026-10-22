# Phase 3A implementation and validation (FR-04, FR-08)

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
