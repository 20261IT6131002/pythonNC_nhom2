# Phase 2 data/index compatibility — P2-02 / D0

**Status:** Review recipe, no migration approval or applied schema change.
Owner: M4, reviewer M1/M3/M5. Authority:
[ADR-0002](../adr/0002-phase2-query-trash-contract.md) and
[public interfaces](PHASE2_PUBLIC_CONTRACTS.md).
Execution belongs to P2-05/06/11/12, not this documentation task.

## 1. Baseline and additive schema

Verified baseline: `infrastructure/mongo/models.py` writes schema_version=1,
`content_plain`, priority/rank, opaque-ID-to-ObjectId references, version,
created_at/updated_at and is_deleted=false. It has no deleted_at.
Old notes remain readable/editable/searchable; do not rename content or IDs,
rewrite all records, reset versions or remove operation keys.

Proposed lazy schema recipe (A2-D01; requires review before implementation):

| Record | Reader behavior | Writer behavior |
|---|---|---|
| v1 active, no deleted_at | Active; absence is normal | Existing create/update remains compatible; no eager rewrite |
| First successful trash transition of v1 | Same note payload plus trash timestamp | Atomic CAS sets is_deleted=true, deleted_at=UTC, schema_version=2 and increments version |
| v2 trash | Requires valid UTC deleted_at; active paths exclude it | Restore atomically unsets deleted_at, sets active, increments version; retains schema_version=2 |
| v2 active after restore | Same existing Note/NoteView mapping | Existing text edits preserve tombstone schema version |
| Deleted record with missing/invalid deleted_at or unknown schema | Typed unavailable/repair-needed; never infer age | No purge or broad repair on startup |

Trash/restore timestamp semantics are A2-T01. State/version/metadata change together,
not a metadata write after CAS. Verify acknowledged read-back uses Mongo timestamp
precision and UTC-aware client codecs. An active v1 create does not require a
separate migration command before being usable.

No eager migration/backfill is necessary for active records under this recipe.
If the reviewed decision instead requires a global version bump, make that a
separate versioned migration with its own dry-run, snapshot and compatibility tests;
do not silently add it to an index script or desktop startup.

## 2. Named indexes and review boundaries

Keep existing indexes and their options unchanged:

| Collection/name | Baseline keys/options |
|---|---|
| notes / uq_notes_operation | client_operation_id ASC; unique; partial string field |
| notes / idx_notes_recent | is_deleted ASC, updated_at DESC, _id DESC |
| categories / uq_categories_name_key | name_key ASC; unique |

Phase 2 candidates:

| Name | Fields / intent | Activation gate |
|---|---|---|
| idx_notes_text | title text, content_plain text | P2-05: actual DEC-07 language/sensitivity and fixture probe; only one compatible text index |
| idx_notes_category_recent | is_deleted ASC, category_id ASC, updated_at DESC, _id DESC | P2-06: filter EXPLAIN evidence |
| idx_notes_priority | is_deleted ASC, priority_rank DESC, updated_at DESC, _id DESC | P2-06: priority tuple EXPLAIN evidence |
| idx_notes_created | is_deleted ASC, created_at DESC, _id DESC | P2-06: created ASC/DESC query plan evidence |
| idx_notes_trash | is_deleted ASC, deleted_at DESC, _id DESC | P2-11: valid tombstones and trash pagination tests |

Names/fields are frozen candidates; text-index language/options and which optional
compound indexes are needed are deliberately not fabricated. Category A-Z resolves
categories.name_key via controlled lookup; a category_id index is not a name-sort
index. Measure the lookup/sort cost. No category name cache or denormalization is
introduced, so rename does not require updating active/trash note documents.

No TTL on notes/deleted_at. If an unexpected TTL, differently configured text
index or conflicting named index already exists, fail preflight with a sanitized
report. Do not drop/recreate it automatically. Cleanup/replacement needs an approved
change and backup. Repeated creation of identical reviewed indexes must be harmless.

## 3. Dry-run, apply, regression and rollback contract

P2-05/11 must implement dry-run/plan reporting in the existing scripts/modules.
Planned CLI: `python scripts/create_indexes.py --dry-run` reports missing,
matching and incompatible indexes/options, performs zero DDL/data writes, and
exits nonzero on incompatibility. Existing invocation without this option remains
backward compatible. Report schema counts/invalid tombstones without note contents
or connection secrets; do not make `--dry-run` a mock that silently applies indexes.

Before applying: validate isolated dev/staging target, capture baseline schema/index
manifest and follow the team's verified backup procedure. Never use production
data for tests. In fixture-owned test DBs, seed Phase 1 documents without deleted_at,
read/create/edit/search them, trash/restore one and check every preserved field;
rerun index setup twice and compare records/index definitions.

Apply only reviewed additive indexes and per-operation CAS tombstone changes.
No automatic collection/index drops, bulk deletions, startup backfills or embedded
credential changes. Database I/O belongs in the worker/CLI path.

Rollback application changes via git revert in reverse dependency order. Preserve
v2 tombstones, deleted_at, versions, data and harmless additive indexes. The old
Phase 1 active queries already exclude is_deleted=true; rolling code back reduces
trash navigation capability but must not silently restore deleted notes. A later
approved cleanup may remove unused indexes separately. Permanent purge cannot be
undone by git revert; backup/restore is the data recovery path, never `down -v`.

## 4. Purge and future locked/attachment records

W3 manual purge can remove only confirmed, verified text-only trash by atomic
ID+version+deleted-state predicate. The adapter also checks schema and supported
payload fields; it rejects any attachment/locked/encrypted representation whose
cleanup/privacy lifecycle is absent. Do not assume future image references are
empty because the current Note DTO does not expose them. Perform final deletion
with the same verified version/state condition so a competing restore/edit wins
safely. Unknown formats fail closed rather than being reinterpreted as text-only.

P2-12 automatic text-only retention remains **W3 scope**. This documentation freeze
does not enable a worker; P2-12 must implement it and pass a reviewed safety gate.
W4 supplies real attachment cleanup/claim/reconciliation before any image record
is eligible. There is no unconditional W4 dependency for verified text-only records.
This does not invent a no-op AttachmentCleanupPort that claims GridFS was cleaned.

### W3 automatic retention DoD — CF-02

- Clock-injected cutoff from aware UTC deleted_at and the actual DEC-02 policy;
  invalid/missing timestamps never imply eligibility. The proposed 30-day arithmetic
  and expired-restore value remain subject to ADR A2-T02/P01 reconciliation.
- Bounded candidate batches, per-record schema/payload eligibility check, then
  atomic ID+version+deleted-state+cutoff deletion with the verified text-only guard.
  Do not delete_many/drop or delete an unqualified stale scan result.
- A concurrent restore/edit must invalidate the removal condition; rejected or
  unknown-outcome actions cannot increment an acknowledged-purge counter.
- Replay/crash/lost-ACK is reconciled idempotently without a second side effect;
  unsupported image/locked records stay intact and produce a sanitized blocked
  maintenance result, never a fabricated cleanup success.
- Explicit runtime activation only after safety review, bounded worker lifecycle
  and tests. Required cases: 29d23h versus 30d cutoff, active/restored exclusion,
  corrupt tombstone, stale version, restart/retry and future-payload rejection.

AC14 must cover these automatic text-only paths, not just manual purge/cancel.
P2-12 stays unfinished if its worker is disabled/unimplemented at W3 exit. If the
team later defers it, record an approved CR, carry-over ID/owner/target/risks and
remaining W3 AC14 status; no such deferral is approved or claimed in this fix.

Before FR-14 locked-note writers: re-review schema_version, ensure encrypted content
is not indexed as plaintext, remove/clear plaintext safely under a reviewed migration
and define title privacy. The W3 `content_plain` text-index candidate does not prove
locked-note security, and W3 purge does not prove W4 GridFS cleanup.
