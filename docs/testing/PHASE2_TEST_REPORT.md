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
Native Mongo matching options and Vietnamese outcomes are recorded from real
tests; no assertion of an unspecified approved search expectation.

## Commit slices and checks

| Slice | Tasks | Validation |
|---|---|---|
| Search core/timezone | P2-03/04 | 143 unit/contract tests passed, 3.05s; date/filter negatives, IANA 23h/25h days, real midnight gap/fold, missing-zone fail-closed; architecture gate |
| Mongo query/indexes | P2-05/06 | 26 real Mongo search/CRUD/seed tests passed, 14.05s; five sort combinations, 65-note pages, query-bound cursors, new insert, active/filter intersection, idempotent preflight |
| Trash core | P2-09/10 | Pure transition/version rules and typed Trash/Restore/Purge/ListTrash; confirmation false/non-bool gives zero calls; payload preserved, stale/replay Conflict |
| Mongo trash/retention | P2-11/12 | 21 real Mongo search/trash tests passed, 10.71s; lazy v1→v2 trash/restore, same-ID payload/version, save/delete and restore/purge races, 35-item keyset trash, cutoff/replay and unsupported-field preservation |
| Search/Trash desktop | P2-07/08/13/14 | Four real desktop scenarios passed alongside Phase1 regression; 300ms debounce, dirty guard, stale result invalidation, error preservation, main-thread confirmations, close cancels timers; official Material Icons packaged with Apache-2.0 license |
| QA/performance | P2-15/16/17 | Shared fake/Mongo contracts; Unicode NFC/NFD, native OR/exclusion/literals, whole-token negatives, UTC local-day edges, rename/dangling/missing references, retention batch starvation; raw 10k measurements + explain |
| E2E/handover | P2-18 | Fresh processes create/search/filter/sort/trash/restart/restore/cancel/confirmed purge; opt-in retention scheduled and shutdown canceled; 4-scenario no-skips verifier extended |

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
target; raw baseline is retained. After category-group lookup/seek and Canvas
rows, overall DB p95 is **46.521ms**, UI p95 **169.909ms** over 100 samples each.
See [benchmark report](PHASE2_BENCHMARK.md) for raw samples, pipelines, explain,
hardware, methodology and the 210.396ms category-render outlier. Debounce is
excluded; this does not certify every request/platform or startup/RAM/FPS.

## Final local checks

Python 3.11.9, Windows build 26100, Tcl/Tk 8.6.12, Mongo 7.0.43 in local Docker.
`NOTEAPP_TEST_MONGO_URI=mongodb://127.0.0.1:27017`, required Mongo/UI flags = 1.
Every database-changing test uses its own UUID-named test database. Retention
activation in desktop E2E is scoped to that fixture; developer retention is off.

- `python -m ruff check .`: pass.
- `python -m ruff format --check .`: 138 files formatted, pass.
- `python -m compileall -q src scripts`: pass.
- `python -m pytest -q tests/unit tests/contract tests/integration tests/ui
  --cov=noteapp.domain --cov=noteapp.application --cov-report=term-missing
  --junitxml=.venv/tools/phase2-all.xml`: **236 passed in 56.15s**, zero skipped,
  errors or failures. 103 unit / 59 contract / 72 integration / 2 UI tests.
- Core coverage: **97%**, 508 statements, 14 uncovered; no core import of Mongo/Tk.
- Four desktop cases extracted from the same JUnit report satisfy
  `scripts/verify_desktop_e2e.py`; no second run or substituted Phase1 evidence.
- Isolated benchmark command ran successfully; full report linked above.

Windows intermittently failed when initializing a second native Tcl interpreter
in the same pytest process. UI assertions now run unchanged in fresh processes,
as desktop restart scenarios already do. Required flags still fail on any missing
display or test failure; no tests were removed, disabled or skipped to pass.

## Runtime acceptance trace

| AC | Executed evidence | Local result / remaining gate |
|---|---|---|
| 01/02 | integration/test_search.py, test_search_edges.py | PASS chosen native title/content, accents/NFD/phrase/OR/exclusion semantics; approved DEC artifact comparison remains human review |
| 03/15 | unit/test_search_presenter.py, ui_scenarios.py | PASS debounce, stale initial/page-two/slow result, 500ms responsive I/O, close timers |
| 04/05 | test_search.py, test_search_edges.py, unit/test_search_core.py | PASS intersection, one-sided/inclusive local days, UTC boundaries, DST/gap/fold fail-closed |
| 06/07/08 | shared phase2_repository_contracts.py, test_search.py, test_search_edges.py | PASS five sorts, 65 items, native-text category seeks and query-bound cursors |
| 09/10/11 | unit/test_trash_core.py, integration/test_trash.py, phase2_desktop_scenarios.py | PASS CAS payload/ID/version and persistence across restart |
| 12/13 | test_trash.py, phase2_repository_contracts.py, phase2_desktop_scenarios.py | PASS no-write cancel, explicit intent, races, stale/replay and NotFound |
| 14 | test_trash.py, ui_scenarios.py, desktop opt-in | PASS implemented text-only cutoff/batch/retry/restore guard and scheduled worker; safety activation review pending, unsupported W4 payload kept |
| 16/17 | architecture/input/error/log gates, full suite | PASS typed whitelist, sanitized failures, Phase1 regression |
| 18 | PHASE2_BENCHMARK.md/json | MEASURED: development overall DB/UI p95 below 200ms; per-query outlier and final DEC-09/hardware acceptance disclosed |
| 19 | CI workflow / setup/index tests | PASS local setup/index/JUnit and all four remote required CI jobs on implementation SHA fb8ae4d; receipt below |
| 20 | this report + board + sketch/screenshot | Technical handover complete; human contract/schema/retention review and M1 UAT signature pending |

Files changed are confined to Phase2 DTO/ports/use cases/policies, Mongo query/trash/
index/timezone/retention adapters, bootstrap, Tk search/trash UI and licensed icons,
tests/CI, setup and Phase2 documentation. Owners/estimates/FR priorities unchanged.
No known functional failures in tested Phase2 paths; production rollout, W4 blob/
encryption cleanup and formal NFR/human acceptance are not inferred from these checks.

## GitHub Actions receipt

[CI run 38045046010](https://github.com/20261IT6131002/pythonNC_nhom2/actions/runs/38045046010)
executed on published implementation SHA
**fb8ae4d3c7173353d500c6ab7ea7f8f7de9e384c**, branch feature/p2-search-trash,
push event, 2026-10-10. GitHub API job snapshots verified every job completed with
success: **quality (3.10)**, **quality (3.12)**, **integration** (real Mongo 7,
Linux Xvfb desktop/JUnit gate), **windows-ui** (native Tk).
No skipped/failed job was substituted and no Phase1 run was reused.

Final README/env/board/receipt commit follows this source SHA and triggers another
feature CI run. Documentation declaration/link regression was rerun: **12 passed,
0.72s**; tracked verifier confirms **5 blocks / 10 models / 2 ports / 33 links**.
Human contract/schema/retention activation review and M1 UAT signature remain
IN_REVIEW. No merge, release or production data operation was performed.

## Rollback

Revert feature commits in reverse dependency order; preserve database data/volumes,
existing version/operation fields and additive indexes. Permanently purged data
requires an actual backup, not a git revert. Human approval/remote CI gates remain
separate from local validation.
