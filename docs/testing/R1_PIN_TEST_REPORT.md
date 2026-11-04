# R1-01 validation and handover

Base: `develop` at `ea9c557`; branch `feature/r1-01-pin-notes`.
Scope: FR-12/AC-12a and required FR-11 ordering changes, BR-10/14 concurrency.
Contract and decisions remain **Proposed**, pending M1/affected-owner review.

Implementation covers domain/DTO/port, metadata CAS, legacy mapper, explicit migration,
additive indexes, server ordering/cursors, editor/card pin actions, purge whitelist,
bootstrap preflight and desktop CI scenario verification.

## Actual local validation — 2026-11-04

Windows 10.0.26100, Python 3.11.9, MongoDB 7.0.43 via Docker loopback.

| Command (use `.venv/Scripts/python.exe` for `python`) | Result |
| --- | --- |
| `python -m ruff check .` | PASS |
| `python -m ruff format --check .` | PASS, 194 files |
| `python -m compileall -q src scripts` | PASS |
| `git diff --check` | PASS |
| `python -m pytest -q tests/unit tests/contract tests/ui --tb=short --cov=noteapp.domain --cov=noteapp.application --cov-report=term` | 421 passed, 1 skipped, 21.26 s |
| `python -m pytest -q tests/integration --tb=short --junitxml=.pytest_cache/r1-integration-final.xml` | 195 passed, 123.10 s; no skips |
| `python scripts/verify_desktop_e2e.py docs/testing/R1_DESKTOP_E2E.xml` | All 7 required scenarios passed; skipped=0 |
| `python -m scripts.benchmark_pinned --output docs/testing/R1_PIN_BENCHMARK.json` | 10,000 synthetic notes; explain and timings saved |

Integration environment: `NOTEAPP_TEST_MONGO_URI=mongodb://127.0.0.1:27017`,
`NOTEAPP_REQUIRE_MONGO=1`, `NOTEAPP_REQUIRE_UI=1`. Pytest needed elevation because
the sandbox could not enumerate its existing Temp directory; Docker also needed
access to its named pipe. No tests were removed, disabled or skipped to hide failures.
The one existing skip is `tests/unit/test_image_file_reader.py:43` (POSIX FIFO test
on Windows). Domain/application combined statement coverage: **98%** (1102 statements,
26 missed); `application/commands/set_pinned.py`: **100%** (26 statements).

[Desktop JUnit](R1_DESKTOP_E2E.xml) contains the seven actual desktop testcase elements
extracted without changing outcomes from the final full integration JUnit report.
The final integration run includes
`test_r1_pin_persists_and_orders_across_restart`, executing two independent Python/Tk
processes against the same fixture-owned Mongo database. The
[screenshot](R1_PIN_DESKTOP.png) uses only synthetic notes and shows a low-priority
pinned match preceding unpinned matches with category sorting selected.

## Requirement evidence

| Requirement / risk | Automated evidence |
| --- | --- |
| TC-ADV-001 | `test_tc_adv_001_all_sorts_filters_and_partition_pages`: all 5 sorts × no filter/text/category/priority/date/combined; pinned-first and exact ordered IDs across pages |
| TC-ADV-002 | `test_tc_adv_002_unpin_returns_to_selected_order`: pin, unpin, then all 5 selected sorts |
| PIN-U01..05 / A01..06 | `tests/unit/test_pinned.py`; defaults, strict boolean, no-op, conflict, missing, unavailable, preserved attachment/reminder/time |
| PIN-R01..05 / P01..03 | Shared `tests/pin_contracts.py` run against fake and Mongo; pin/text race has one CAS winner; 0/20/50 pins with limit 30 |
| PIN-P04 / UI | `pin_changed` invalidates paging before page-one refresh; UI scenario asserts reorder after acknowledgement |
| PIN-P05 / category edges | Ordered page IDs across partitions, including category Z pins before category A unpinned; existing null/missing/dangling category tests pass |
| Migration/preflight | Missing flag read compatibility; read-only report; apply/rerun; invalid scalar and array values rejected before writes; no other field changes |
| Other metadata | `test_pin_does_not_replace_attachment_reminder_or_delivery_claim` compares full Mongo documents before/after |
| PIN-UI01..06 | Real Tk toolbar/card hit target, busy guard, dirty text, next save, failure/conflict and hidden trash action |
| Persistence/trash lifecycle | Independent repository read, active-only CAS, trash/restore flag preservation and restart desktop scenario |
| Existing features | Full unit/contract/UI/integration suites, including image cleanup, reminder delivery and retention |

The first full regression run caught the purge whitelist, category missing/null group
duplication, migration preflight on a raw legacy desktop fixture, and a render that
overwrote trash error feedback. Those were fixed; the final suites above pass.
The historical desktop fixture now writes an explicit false flag, while dedicated
migration tests retain missing-field cases.

## Query benchmark

[Raw timings and explain](R1_PIN_BENCHMARK.json): 10,000 notes, 9,500 active,
1,000 active pinned; 5 warmups + 20 measured samples per query. Includes index names,
execution stages, keys/documents examined and any blocking sorts.

| Query | p95 (ms) |
| --- | ---: |
| Recent first page | 3.089 |
| Recent next page | 7.263 |
| Created descending / ascending | 3.329 / 5.015 |
| Priority | 4.506 |
| Category first / next page | 45.944 / 199.327 |
| Native text / combined filter | 13.920 / 14.062 |

These are local observations, with another regression run active on the same Mongo
instance. They do not establish the SRS performance threshold or a production SLA.

## Changed-file inventory

- Domain/application: `domain/entities/note.py`; `application/commands/set_pinned.py`;
  `application/dto/{note_input,note_view}.py`; `application/ports/note_repository.py`.
- Infrastructure/composition: `bootstrap.py`; `infrastructure/mongo/{models,repositories,
  note_query_repository,indexes,migrations,trash_repository}.py`;
  `scripts/{migrate_pinned,benchmark_pinned,verify_desktop_e2e}.py`.
- Presentation: `presentation/tk/presenters/{pin_presenter,editor_presenter}.py`;
  `presentation/tk/state/editor_state.py`; `presentation/tk/views/{app_window,note_editor,
  note_list}.py`.
- Tests: `tests/{pin_contracts,r1_ui_scenarios,r1_desktop_scenarios,fakes,phase2_fakes,
  phase3_desktop_scenarios,ui_scenarios}.py`; `tests/unit/{test_pinned,test_pin_presenter}.py`;
  `tests/contract/{test_pin_repository,test_desktop_ci_report}.py`;
  `tests/integration/{test_pinned,test_desktop,test_trash}.py`; `tests/ui/test_pin_ui.py`.
- Governance/evidence: root R1 plan, R1 contract/ADR, README, RTM, this report, screenshot,
  benchmark JSON, desktop JUnit and `.github/workflows/ci.yml` scenario step label.

## Open gates and operational notes

Remote Python 3.10/3.12, GitHub CI and independent M1/M2/M3/M4 review remain unverified.
Implementation is recorded in scoped local commits at the user's request; no push,
PR, merge or release has been performed. Local test PASS
does not mark PIN-D01..D14 or unrelated OPEN decisions approved.

The Mongo dev container was started for local verification and remains running.
No development/user database migration was applied. Existing DB rollout must stop
older writers and follow the explicit plan/apply migration and additive index setup
in the README. Local mutations refresh page one; keyset pages are not a cross-client
snapshot while other clients change ordering keys.

Rollback: revert the feature changes, retain additive pin fields/indexes, and pause
old-code purge/retention pending a whitelist review. No user DB was migrated; Mongo
tests and benchmark own fresh random `noteapp_test_*` databases and drop only those.
