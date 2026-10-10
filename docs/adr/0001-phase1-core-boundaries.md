# ADR-0001 — Phase 1 technical slice contracts

Status: **Proposed — pending M1/M2/M3/M4 review**. Date: 2026-10-09.
Owner: M1; implementation on `feature/foundation` at the user's request.
This document records reversible implementation assumptions, not approval of
SRS v2, DEC-01/04/08/09, a production migration, or permission to merge.

## Contracts under review (P1-02, P1-05/06/11/12/13)

- Domain is stdlib only. Application depends on domain and its own DTO/ports.
  Presentation depends on public application DTO/use cases, never Mongo adapters.
  `bootstrap.py` owns wiring; no database connection occurs during imports.
- `NoteRepository`: `create(note, operation_id)`, `find_by_id(note_id)`,
  `list_recent(limit, cursor)`, `update_if_version(note, expected_version)`.
  Create retries return the first acknowledged note for the operation ID, even
  when the retry payload differs. The UI retains edits made while saving.
- `CategoryRepository`: `create(category)`, `find_by_id(category_id)`, `list_all()`.
  Category names use trim/casefold; uniqueness is enforced by a DB index.
- `Clock.now()` returns aware UTC. Core IDs are opaque strings; only the Mongo
  mapper validates/converts ObjectId-compatible IDs. New IDs use stdlib randomness.
- Frozen Create/Update input DTOs, NoteView/CategoryView, NotePage and NoteListView.
  List defaults to 30, accepts 1..100, and orders active records by
  `(updated_at DESC, _id DESC)` with an opaque adapter-owned cursor.
- Typed `ValidationError`, `NotFound`, `Conflict`, `RepositoryUnavailable` and
  `DuplicateCategory` are exposed without driver messages or note content.
- Update uses atomic `_id + expected_version` CAS and `$inc` version; a failed CAS
  distinguishes missing records from stale versions. No multi-document transaction.
- The new **isolated development** collections use `schema_version=1` for this
  minimal text slice. No existing schema is migrated and no 1 MiB content cap is
  introduced while DEC-08 is open. Mongo's actual BSON limit still applies.
- Unique partial operation-ID index, active recent-list compound index, unique
  category name-key index. No TTL, search index, attachment or reminder behavior.
- Local loopback Mongo only until DEC-04 review. Runtime DB names use
  `noteapp_dev*`; integration DBs are generated `noteapp_test_*` names and only
  the database created by a fixture is eligible for that fixture's teardown.
- Bounded executor submits immutable snapshots. Workers only enqueue result
  envelopes; a main-thread event pump checks request sequence/editor revision.
  Save is acknowledged only after the repository returns. Errors preserve text.

## Scope and review gates

P1-01/20 approval and signed UAT remain human gates. This branch implements the
technical slice only; release workflow, production settings and deferred features
stay outside scope. Rollback uses `git revert` of individual implementation
commits; it does not delete databases. Index scripts only add named indexes.

The provided rules live at `docs/BASE_RULES.md` and the plan at
`docs/srs/phase 1/PHASE1_FOUNDATION_CRUD.md`; older paths in the supplied documents
are references, not a reason to create a second document hierarchy.

Technical references: [PyMongo UTC handling](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/dates-and-times/),
[PyMongo connection options](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/connection-options/),
[ttkbootstrap Panedwindow](https://www.ttkbootstrap.org/en/latest/reference/api/panedwindow.html).
