# Phase 2 implementation and validation

Branch: `feature/p2-search-trash`, cut from `feature/p2-02-contract-freeze` at
`b34462c`, 10/10/2026. User requested completing Phase 2 and supplied
[`sketch.png`](../srs/phase%202/sketch.png), then required proper library icons.
Scope: P2-03..18, FR-03/06/07/11/13 plus FR-04/05 filters, CST-03 and NFR-SEC-03.

## Authority and assumptions

Previously confirmed decisions remain confirmed; concrete P2-01 artifacts are not
available in this checkout. The development implementation follows the documented
technical proposals: updated date default/optional bounds, ordinal name_key/null
first, strict CAS replay, update timestamps on trash/restore, lazy tombstone schema,
30-day text-only retention. These are implementation assumptions for isolated dev,
not an invented Accepted ADR, production migration or signed UAT.
Native Mongo matching options and Vietnamese outcomes will be recorded from real
tests; no assertion of an unspecified approved search expectation.

## Commit slices and checks

| Slice | Tasks | Validation |
|---|---|---|
| Search core/timezone | P2-03/04 | 143 unit/contract tests passed, 3.05s; date/filter negatives, IANA 23h/25h days, real midnight gap/fold, missing-zone fail-closed; architecture gate |
| Mongo query/indexes | P2-05/06 | 26 real Mongo search/CRUD/seed tests passed, 14.05s; five sort combinations, 65-note pages, query-bound cursors, new insert, active/filter intersection, idempotent preflight |
| Trash core | P2-09/10 | Pure transition/version rules and typed Trash/Restore/Purge/ListTrash; confirmation false/non-bool gives zero calls; payload preserved, stale/replay Conflict |
| Mongo trash/retention | P2-11/12 | 21 real Mongo search/trash tests passed, 10.71s; lazy v1→v2 trash/restore, same-ID payload/version, save/delete and restore/purge races, 35-item keyset trash, cutoff/replay and unsupported-field preservation |
| Search/Trash desktop | P2-07/08/13/14 | Four real desktop scenarios passed alongside Phase1 regression; 300ms debounce, dirty guard, stale result invalidation, error preservation, main-thread confirmations, close cancels timers; official Material Icons packaged with Apache-2.0 license |

Retention is an implemented bounded job, not a fake cleanup adapter. Automatic
eligibility and final delete both enforce known text-only fields/schema/state;
future attachment/locked/unknown fields are excluded or explicitly rejected.
`scripts/run_retention.py` defaults to read-only eligibility; `--apply` performs
one bounded batch. UI scheduling is opt-in and uses the existing worker pool.

Text index technical choice: `default_language=none` on title/content_plain;
search explicitly uses caseSensitive=false and diacriticSensitive=false. Real
Mongo tests observed HỌC/học/hoc and quoted học tập/hoc tap matching the same
synthetic Vietnamese title/content notes. This describes chosen native behavior,
not Vietnamese stemming/substring or proof of an unspecified DEC-07 artifact.
`--dry-run` reports matching/missing/incompatible indexes without DDL; unexpected
TTL/index conflicts fail rather than drop/recreate indexes.

Dependencies: merged Phase1 behavior and P2-02 DTO/port proposals; Mongo/Tk remain
outside core. New timezone resolver belongs to infrastructure; tzlocal supplies
OS mapping, tzdata supplies IANA rules. Runtime dependencies are bounded in
pyproject; core imports stdlib only. No OS/package-manager changes are required.

UI follows the supplied sketch with 20/30/50 panes, scrolling filters, note cards,
priority badges, a plain-text editor and Active/Trash navigation. Rich text,
attachments, reminders and PIN controls belong to later phases. Every visible
action has a handler. Icons are original Google Material Icons at a pinned commit,
loaded locally, with source and full license in the package. See
[desktop screenshot](PHASE2_DESKTOP_SMOKE.png).

Initial 10k benchmark found category join and card recreation above the 200ms
target; raw baseline is retained in PHASE2_BENCHMARK_BASELINE.json. Performance
follow-up and final suite results will be recorded before handover.

## Rollback

Revert feature commits in reverse dependency order; preserve database data/volumes,
existing version/operation fields and additive indexes. Permanently purged data
requires an actual backup, not a git revert. Human approval/remote CI gates remain
separate from local validation.
