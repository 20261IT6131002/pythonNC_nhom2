# Phase 1 task-board follow-up — 10/10/2026

Branch: `feature/task-board`. Merged baseline: `dc4101c` (PR #2).
Source: [supplied task board](../srs/phase%201/PHASE1_TASK_BOARD.md).
Scope: BLK-04, P1-06/12/17/18 behavioral contracts, P1-03/20 setup evidence;
FR-01/02/04/05 text subset, CST-01/02/03, P1-AC01..14.

## Task board and mapping

`3de1759` adds the board supplied by the user, its original 20 task cards, owners,
reviewers and dependencies, plus a status/evidence table for every task. No task
assignments are invented. M1–M5 remain role slots and capacity is an assumption.
The previous board deferral ends with this task; historical evidence remains dated.
Approvals excluded by the previous blocker report are not requested again; missing
artifact links are tracked without inventing signatures or marking SRS approved.

The canonical task mapping corrects the old provisional implementation table:
P1-14 is Mongo category/seed, P1-16 is UI save/error/conflict state, and P1-17
is unit/contract/architecture QA. The summary in the implementation report is
updated during this branch's documentation handover.

## Shared repository contracts

M5 owns `tests/repository_contracts.py`, the shared behavior suite, plus
`tests/contract/test_fake_repositories.py` and
`tests/integration/test_repository_contracts.py`, which supply fresh fake or
real Mongo adapters. These files validate existing public ports; runtime code,
DTOs, schema, indexes and application behavior do not change.

Each adapter runs the same **18 cases**: persisted note/category read-back,
aware UTC, unknown IDs, retry after an edit, successful/stale/missing CAS,
invalid expected versions and version jumps, bounded page sizes, typed cursor
errors, timestamp/ID ordering, insertion between pages, Unicode casefold category
uniqueness and normalized catalog ordering. Mongo fixtures own random
`noteapp_test_*` databases and teardown only those databases.

The initial fake run produced **10 failed, 8 passed**, demonstrating real gaps:
offset pagination repeated a note after a newer insert, and invalid page size,
cursor or expected version did not raise the expected typed error. `tests/fakes.py`
now uses a timestamp/ID cursor and matches the adapter's existing validation.
Fake cursors stay adapter-owned; tests do not require matching Mongo cursor bytes.
This does not promise snapshot isolation for concurrent edits to existing records.

## Actual checks

Windows, Python 3.11.9; existing venv; Mongo dev container healthy at loopback
`127.0.0.1:27017`. Commands below use `.venv/Scripts/python.exe`.

| Command | Observed result |
|---|---|
| `git fetch origin develop`; `git merge-base --is-ancestor HEAD origin/develop`; `git diff --stat HEAD origin/develop` at starting HEAD | Merge PR #2 verified at `dc4101c`; starting HEAD is its ancestor; identical source tree |
| `git merge --ff-only origin/develop` on `feature/task-board` | Fast-forward, no source change and no new merge commit |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` after shared suite | 110 files already formatted |
| `python -m pytest -q tests/contract/test_fake_repositories.py` after fixing fake | 18 passed, 0.14s; no Mongo/display needed |
| `python -m pytest -q --cov=noteapp.domain --cov=noteapp.application --cov-report=term-missing --junitxml=.venv/tools/task-board-baseline.xml` | Baseline: 107 passed, 23.32s, no skips; 97% core statement coverage |
| Same full-suite command with `--junitxml=.venv/tools/task-board-contracts.xml` after shared suite | 143 passed, 29.68s, no skips; 97% core statement coverage (276 statements, 9 missed) |
| `git diff --check` | Passed |

Full runs set `NOTEAPP_TEST_MONGO_URI=mongodb://127.0.0.1:27017`,
`NOTEAPP_REQUIRE_MONGO=1` and `NOTEAPP_REQUIRE_UI=1`. All three real desktop
scenarios and the Windows Tk shell ran. Reports live under ignored `.venv/tools`.
The first sandboxed unit/contract run returned 76 passed / 10 setup errors because
pytest could not access the host temporary directory; the authorized full run
above resolved that environment restriction. No tests were deleted or skipped.

## Remaining artifacts and rollback

The board tracks artifacts still absent from this checkout: role usernames and
capacity confirmation, links to previously confirmed decision/review/UAT records,
a separate deliberately failing remote PR, and a manual slow-I/O video. These do
not authorize publishing or replacing existing approvals. Remote CI for this
branch is not established by the previous PR's run.

Revert this branch's commits in reverse dependency order on a feature branch.
All changes are planning, QA fakes/tests and evidence; preserve DB data and volumes.
No production migration, secrets, TTL, release or merge of this branch is performed.
