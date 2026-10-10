# ADR-0002 — Phase 2 query/trash contract freeze

Status: **Proposed / IN_REVIEW**. Date: 2026-10-10.
Task: **P2-02**, source backlog T020, slice D0.
Owner: M1; reviewers: M2/M3/M4/M5, independently of the author.
Branch: `docs/p2-02-contract-freeze`, cut from `feature/phase-2` at `b29d35f`.

## Context and authority

The Phase 2 plan contains illustrative interfaces with several alternatives:
input names, a query port versus extending `NoteRepository`, trash return types,
and error behavior for repeated actions. Downstream owners need one reviewable
contract before implementing P2-03..18.

The user requested starting at P2-02 and stopping after committing it for review.
The [master plan](../srs/phase%202/01_PHASE2_MASTER_PLAN.md) records that DEC-02/07/09
were already agreed by the team, but their artifact/values are absent here.
This ADR does not request reapproval or claim that those decisions are still open.
P2-01 artifact references remain a dependency for the affected semantics.

## Proposed technical decisions

1. Keep every Phase 1 entity, DTO, port and use-case signature unchanged.
   Add separate `SearchRepository` and `TrashRepository` ports. Do not add
   `deleted_at` to `Note` or `NoteView` or make active `find_by_id` return trash.
2. Freeze exact inputs, normalized UTC criteria, five supported sort combinations,
   trash outputs and error mapping in
   [the public contract](../architecture/PHASE2_PUBLIC_CONTRACTS.md).
   The Python blocks are declarations for later tasks, not runtime implementations.
3. Core IDs stay opaque strings. Existing UUID client-operation IDs apply to
   create; edit/trash/restore/purge target the existing note ID and expected version.
   BSON conversion, query operators, cursor decoding and joins belong to Mongo.
4. Search uses native text fields `title` and `content_plain`; preserve existing
   named indexes. Language/diacritic options require DEC-07 values and P2-05 probes.
5. Query cursors bind the normalized query and sort order; trash has a separate
   cursor namespace. No cursor is interpreted as an executable expression or query.
6. Trash/restore use atomic state-and-version predicates. Manual purge is confirmed,
   conditional and restricted to verified text-only records until W4 cleanup exists.
   Retention automation remains disabled pending the approved lifecycle.
7. [Data compatibility and migration notes](../architecture/PHASE2_DATA_MIGRATION.md)
   define additive changes, dry-run/preflight, old-record reads and rollback.
   This commit applies no migration or index change.
8. Future FR-14 must review plaintext indexing and cleanup guards before enabling
   locked-note writers; Phase 2 does not implement lock/encryption behavior.

## Assumption trace — resolve against existing P2-01 decisions

| ID | Proposed value for review | Affected tasks | Required existing artifact |
|---|---|---|---|
| A2-Q01 | Default date field `UPDATED_AT`; absent bounds allowed independently | P2-03/04/07 | Date/UX decision |
| A2-Q02 | Category order is ordinal normalized `name_key`; uncategorized/dangling reference uses empty key, sorts first ascending | P2-06/07/16 | Category collation/placement decision |
| A2-Q03 | Text is trimmed only; no automatic Unicode/accent rewriting, no arbitrary search-text length cap | P2-03/05/15 | DEC-07 matching/syntax examples and any approved resource limit |
| A2-T01 | Trash and restore set `updated_at=now_utc`, preserve `created_at`; repeated/wrong-state requests are strict Conflict | P2-09/10/11/17 | DEC-02 transition/retry/timestamp decision |
| A2-T02 | Restore remains possible after 30 days until an actual purge claim/removal wins | P2-09..12/17 | DEC-02 retention/restore decision |
| A2-D01 | Lazy tombstone schema v2 on first trash transition; v1 active writers remain compatible | P2-11 | Existing migration approval or M1/M4 review of this recipe |
| A2-P01 | Manual purge only verified text-only trash; automatic retention off until cleanup/lifecycle review | P2-10..12/17 | DEC-02/AUD-02 deviation and W4 cleanup handoff |

Vietnamese token/phrase/accent expected matches and text-index language are
**unspecified**, not inferred from these assumptions. Their implementation/acceptance
is blocked only until the actual DEC-07 examples are available. Technical contract
review can proceed; no production semantics or migration approval is asserted.

## Consequences, review and rollback

Separate ports preserve Phase 1 compatibility and let M2 work with typed fakes,
M3 implement policies and M4 implement adapters without sharing GUI/DB code.
P2-03/04 own executable validation/date conversion; P2-09/10 own deletion policies
and use cases. D0 contains documentation and contract checks only.

The [P2-02 review record](../testing/PHASE2_P2_02_REVIEW.md) contains validation,
file scope and reviewer checklist. IN_REVIEW means the deliverable is prepared,
not that cross-team review, schema approval or a Phase 2 feature is accepted.
Revert the P2-02 documentation commit to withdraw this proposed contract; preserve
all application code, databases and volumes.
