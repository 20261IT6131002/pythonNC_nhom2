# ADR-0002 — Phase 2 query/trash contract freeze

Status: **Proposed / REQUEST_CHANGES — not Accepted/Frozen**. Date: 2026-10-10.
Task: **P2-02**, source backlog T020, slice D0.
Owner: M1; reviewers: M2/M3/M4/M5, independently of the author.
Branch: `feature/p2-02-contract-freeze`, cut from `feature/phase-2` at `b29d35f`.
Originally named `docs/p2-02-contract-freeze`; renamed at the user's request after
commit `1df944c`. The source commit and existing contract declarations are unchanged.

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
2. Specify inputs, normalized UTC criteria, five supported sort combinations,
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
   W3 retains P2-12 automatic retention for verified text-only records with a
   reviewed safety gate; only blob cleanup integration belongs to W4. Activation
   is disabled until P2-12 is implemented/tested, not unconditionally until W4.
7. [Data compatibility and migration notes](../architecture/PHASE2_DATA_MIGRATION.md)
   define additive changes, dry-run/preflight, old-record reads and rollback.
   This commit applies no migration or index change.
8. Future FR-14 must review plaintext indexing and cleanup guards before enabling
   locked-note writers; Phase 2 does not implement lock/encryption behavior.

## Canonical decision trace — CF-01

This is the only reconciliation table for P2-01 values. The user reconfirmed
**"đã chốt"** on 10/10/2026 during this follow-up. That confirms decision status,
not the per-case values or an artifact path; do not substitute a proposed value
for an agreed one. The [tech lead review](../srs/phase%202/review/NOTEAPP_P2_02_CONTRACT_FREEZE_REVIEW.md)
requires this distinction. Other documents reference these IDs rather than
maintaining separate agreed-value tables.

`MATCHED` means a linked existing decision has the same concrete value; `ADJUSTED`
means this proposal was changed to that linked value; `DEFERRED` means the value
comparison is pending, **not** a sprint scope deferral. None is MATCHED/ADJUSTED
without evidence. Owners must attach value/source before affected production merge.

| ID | Proposed value only | Agreed value / P2-01 evidence link | State | Owner / affected gate |
|---|---|---|---|---|
| A2-Q01 | UPDATED_AT default; independent optional date bounds | NOT PROVIDED; need date-field and one-sided range values | DEFERRED / BLOCKED | M1+M3+M2; P2-03/04/07 default/range semantics |
| A2-Q02 | Ordinal name_key; uncategorized/dangling empty key first ASC | NOT PROVIDED; need collation and null placement values | DEFERRED / BLOCKED | M1+M4+M2; P2-06/07/16 category ordering |
| A2-Q03 | Trim only; no Unicode rewriting or arbitrary text cap | NOT PROVIDED; need normalization/syntax/resource-limit values | DEFERRED / BLOCKED | M1+M3+M5; P2-03/15 text policy |
| A2-Q04 | Native title/content_plain full-text; tokenizer/options unspecified | NOT PROVIDED; need DEC-07 tokenizer/language and accent/phrase/Unicode expected cases | DEFERRED / BLOCKED | M1+M4+M5; P2-05/06/15 text-index activation |
| A2-T01 | updated_at=now on trash/restore; strict wrong-state/replay Conflict | NOT PROVIDED; need DEC-02 timestamp/retry values | DEFERRED / BLOCKED | M1+M3+M4; P2-09/10/11/17 mutation semantics |
| A2-T02 | Restore allowed after 30 days until purge actually wins | NOT PROVIDED; need DEC-02 expired-restore/cutoff values | DEFERRED / BLOCKED | M1+M3+M4; P2-09..12/17 retention lifecycle |
| A2-D01 | Lazy v2 tombstone on first trash; active v1 writers unchanged | NOT PROVIDED; need migration decision/source | DEFERRED / BLOCKED | M1+M4; P2-11 schema activation |
| A2-P01 | W3 manual + automatic text-only purge under safe gate; unsupported blobs blocked until W4 cleanup | NOT PROVIDED; W3 P2-12 remains required by task board; need actual lifecycle/deviation values | DEFERRED / BLOCKED | M1+M4+M5; P2-10..12/17 activation |
| A2-N01 | Keep <200ms/10k target; report DB/UI p95 with conditions | NOT PROVIDED; need DEC-09 accepted sample/measurement method | DEFERRED / BLOCKED | M1+M5; P2-16/18 performance acceptance |

Vietnamese token/phrase/accent expected matches and text-index language are
**unspecified**, not inferred from these assumptions. Their implementation/acceptance
is blocked only until the actual DEC-07 examples are available. Technical contract
review can proceed; no production semantics or migration approval is asserted.
CF-01 remains open on value/evidence reconciliation. Common typed interfaces,
negative validation and isolated prototypes can proceed; the affected defaults,
schema and lifecycle must not be silently hardcoded from this proposal.

## Consequences, review and rollback

Separate ports preserve Phase 1 compatibility and let M2 work with typed fakes,
M3 implement policies and M4 implement adapters without sharing GUI/DB code.
P2-03/04 own executable validation/date conversion; P2-09/10 own deletion policies
and use cases. D0 contains documentation and contract checks only.

The [P2-02 review record](../testing/PHASE2_P2_02_REVIEW.md) contains validation,
file scope and reviewer checklist. REQUEST_CHANGES means the deliverable needs review fixes,
not that cross-team review, schema approval or a Phase 2 feature is accepted.
Revert the P2-02 documentation commit to withdraw this proposed contract; preserve
all application code, databases and volumes.
