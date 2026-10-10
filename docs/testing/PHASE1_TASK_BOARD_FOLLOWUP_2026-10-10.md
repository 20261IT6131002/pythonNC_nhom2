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

## Fresh tracked-snapshot setup — P1-03/20, AC01

After commit `6dc0dd3`, `git archive --format=zip
--output=.venv/tools/task-board-clean-6dc0dd3.zip HEAD` exported tracked files only.
PowerShell `Expand-Archive` extracted them into
`.venv/tools/task-board-clean-6dc0dd3`; `python -m venv .venv` created a new venv
inside that snapshot. No `.git`, existing virtualenv, local secrets or untracked
source files were copied. This is a fresh committed snapshot on the same Windows
host, not a remote clone or an independent teammate's UAT.

From the snapshot directory, using its own `.venv/Scripts/python.exe`:

| Command | Observed result |
|---|---|
| `python -m pip install -e ".[dev]"` | Successful fresh editable install; PyMongo 4.18.3, ttkbootstrap 1.20.4, pytest 8.4.2, Ruff 0.17.0 |
| `python -m pip check` | No broken requirements found |
| Import `noteapp`; print `sys.prefix` and `noteapp.__file__` | Uses the new snapshot venv and snapshot `src/noteapp`, not the original working tree |
| `python -m ruff check .`; `python -m ruff format --check .` | Passed; 110 files already formatted |
| `python -m pytest -q --junitxml=../task-board-clean-tests.xml` with required Mongo/UI | **143 passed, 27.50s, no skips**, including real launcher/mainloop/shutdown and separate-process restart |

The first pip invocation preceded completed venv bootstrap and reported no pip;
after bootstrap, sandboxed pip could not obtain build dependencies. The authorized
network-enabled install above succeeded without changing dependency constraints.
The fresh-suite XML is stored in ignored `.venv/tools/task-board-clean-tests.xml`.
This extends AC01/05/10/11 evidence without claiming a new UAT signature.

The one-off `.venv/tools/validate_task_board_docs.py` check verifies all **20 task
status rows** in order and **21 local Markdown links** across README, board,
blocker report and testing documents. It passed. Ignored setup/report artifacts
remain available for inspection; they are not committed.

## Changed files and ownership

- M1/M5 planning: `docs/srs/phase 1/PHASE1_TASK_BOARD.md`,
  `docs/srs/phase 1/NOTEAPP_PHASE1_ONLY_BLOCKERS_2026-10-10.md`.
- M1/M5 handover: `README.md`, `docs/testing/PHASE1_IMPLEMENTATION.md`,
  `docs/testing/PHASE1_BLOCKER_FIXES_2026-10-10.md`,
  `docs/testing/PHASE1_DRAFT_PR_BODY.md`, this follow-up document.
- M5 QA: `tests/fakes.py`, `tests/repository_contracts.py`,
  `tests/contract/test_fake_repositories.py`,
  `tests/integration/test_repository_contracts.py`.

Commit slices: `3de1759` supplied board/status; `6dc0dd3` shared contracts/fake fix;
the final handover commit updates documentation only. No runtime source changed.

## Acceptance checklist for handover

This checklist maps evidence, not a new M1/M5 acceptance signature. Existing
confirmations recorded in the blocker report are preserved. The original ACs
in [the plan](../srs/phase%201/PHASE1_FOUNDATION_CRUD.md) remain unchanged.

| AC | Technical evidence | Handover qualification |
|---|---|---|
| AC01 | Fresh tracked-snapshot setup recorded above | Same Windows host; not an independent teammate's clean clone |
| AC02 | `tests/contract/test_architecture.py`, including negative import samples | Unit/contract runs do not instantiate Tk or connect to Mongo |
| AC03 | `tests/unit/test_core.py`: blank/1/250/251 title, invalid priority, UTC | Text-only FR-01/02 subset |
| AC04 | Mongo create/read-back and desktop create scenario; shared category/priority contract | Real fixture-owned DB, not a mocked database |
| AC05 | Desktop create and edit run in separate Python processes and reload persisted data | Automated Windows restart demonstration |
| AC06 | Mongo update version/UTC tests and shared CAS contract | Existing atomic version filter and increment |
| AC07 | Mongo concurrency plus shared stale CAS rejection and presenter conflict preservation | Stale content cannot overwrite the winner |
| AC08 | Mongo 8 concurrent retries, shared retry-after-edit, presenter lost-ACK retry | One logical create remains one record |
| AC09 | Mongo normalized name index; shared Straße/STRASSE rejection, seed repeatability | Category lifecycle remains outside this slice |
| AC10 | Presenter states and real Tk invalid/conflict/DB-error scenarios | Unsaved editor text stays in RAM |
| AC11 | Main-thread pump, 500ms worker, bounded capacity, stale/closed callback tests; Windows screenshot in board | Manual slow-I/O video artifact still absent |
| AC12 | PR #2 CI run in the board: all 4 jobs passed; desktop verifier reports 3 scenarios with no skips | New branch CI and separate deliberately failing remote PR not claimed |
| AC13 | Config isolation, telemetry redaction and launcher sanitization tests | No production/public Mongo, credentials, TTL or destructive migration |
| AC14 | Original task cards + actual status, corrected implementation mapping, ADR and rollback links | Link previously confirmed review/UAT records; do not sign or approve on behalf of M1/M5 |

## Remaining artifacts and rollback

The board tracks artifacts still absent from this checkout: role usernames and
capacity confirmation, links to previously confirmed decision/review/UAT records,
a separate deliberately failing remote PR, and a manual slow-I/O video. These do
not authorize publishing or replacing existing approvals. Remote CI for this
branch is not established by the previous PR's run.

Revert this branch's commits in reverse dependency order on a feature branch.
All changes are planning, QA fakes/tests and evidence; preserve DB data and volumes.
No production migration, secrets, TTL, release or merge of this branch is performed.
