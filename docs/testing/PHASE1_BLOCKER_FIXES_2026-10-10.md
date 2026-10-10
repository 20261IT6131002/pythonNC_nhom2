# Phase 1 — Blocker fixes, 10/10/2026

Source: [blocker report](../srs/phase%201/NOTEAPP_PHASE1_ONLY_BLOCKERS_2026-10-10.md).
Branch: `feature/foundation`; starting HEAD: `02690ff`.
Scope: BLK-01/02/03, P1-AC02/05/11/12, CST-03; existing CRUD contracts unchanged.

During this fix the user deferred BLK-04 while planning continued. After PR #2
merged, the user supplied the 20-task board for `feature/task-board`; see the
[current follow-up](PHASE1_TASK_BOARD_FOLLOWUP_2026-10-10.md).
Task IDs, owners and reviewers now come from that supplied board, not guesses.
The source report excludes ADR/DEC/UAT approvals and independent review items
already confirmed by the user; these are not reopened by this fix.

## Changes and current status

| Blocker | Fix/evidence | Status |
| --- | --- | --- |
| BLK-03 | All six ordered reading paths in `AGENTS.md` now point to existing files. No duplicate document hierarchy. | Fixed locally and pushed (`32e6430`) |
| BLK-02 | Mongo integration job installs Xvfb/xauth/Tk, runs the three desktop tests, and verifies JUnit has all expected scenarios with no skipped/error/failure results. `NOTEAPP_REQUIRE_UI=1` disables the headless skip fallback. | Closed: real GitHub integration logs confirm all 3 scenarios passed, skipped=0 |
| BLK-01 | Feature commits pushed; user created PR #2 after the connection's create-PR API returned 403. All four CI jobs passed at reviewed source HEAD `96f5ec9`. | Closed at the verified SHA; follow-up evidence-only commits are checked again before handoff |
| BLK-04 | User supplied the task board after PR #2 merged; 20 cards/status/evidence tracked in `feature/task-board`. | Closed locally by `3de1759`; current validation in the task-board follow-up |

## Actual local checks

- Windows/Python 3.11: `python -m pytest -q --junitxml=.venv/tools/phase1-blockers-tests.xml`
  with `NOTEAPP_REQUIRE_MONGO=1`, `NOTEAPP_REQUIRE_UI=1` and isolated loopback Mongo:
  **107 passed, 27.85s**. This includes ten regression cases for complete, skipped,
  failed, errored, missing, duplicate and malformed desktop JUnit reports.
- `python -m ruff check .`: passed. `python -m ruff format --check .`: **107 files**
  already formatted. actionlint validation of `ci.yml`: passed.
- A Linux Docker environment built from the **committed `9c46be1` snapshot** ran
  Python **3.12.15**, Ruff **0.17.0**, Xvfb and the real local Mongo container.
  Linux Ruff check/format also passed.
- `xvfb-run -a -s "-screen 0 1600x1200x24" python -m pytest -vv
  tests/integration/test_desktop.py --junitxml=/tmp/noteapp-desktop-e2e.xml`:
  **3 passed, 9.01s**. The report verifier printed
  `Verified all 3 desktop Mongo E2E scenarios passed; skipped=0.`
- Negative display check: without `DISPLAY`, the unavailable-DB desktop scenario
  with `NOTEAPP_REQUIRE_UI=1` returned **exit 1 / 1 failed**, rather than skipping.
  This is an intentional local negative check, not a remote failed-PR pipeline run.
- `git merge-tree --write-tree --messages HEAD origin/develop`: exit 0, no
  conflicts. No feature/develop/main merge was performed.
- `git diff --check`: passed.

Linux validation copied tracked files via `git archive` into an ignored directory
under `.venv/tools/phase1-linux-validation`. It does not mount the working source,
credentials or production data into the image. Test containers share only the
dedicated dev Mongo network namespace to keep the URI loopback-only; fixtures
create and remove only their own randomly named `noteapp_test_*` databases.

## Files and ownership

- M1: `AGENTS.md` canonical paths; this evidence and the source report reference.
- M5/M2/M4: `.github/workflows/ci.yml`, `tests/integration/test_desktop.py`.
- M5: new `scripts/verify_desktop_e2e.py` and
  `tests/contract/test_desktop_ci_report.py`. The script owns CI report validation,
  not application/domain behavior, which explains its addition outside runtime
  scaffold responsibilities.

## Verified remote evidence

PR: [#2](https://github.com/20261IT6131002/pythonNC_nhom2/pull/2),
base `develop`, head `feature/foundation`. GitHub reported it open, mergeable,
and not draft. No merge was performed.

Run: [CI #2](https://github.com/20261IT6131002/pythonNC_nhom2/actions/runs/38018848284).
Event: `pull_request`. Source SHA:
`96f5ec95b52df66c1a7df0fc46f6a4621e28722d`.
Created: **2026-10-10 02:57:32 UTC**; completed: **02:58:23 UTC**.
Conclusion: **success**.

| Job | Job ID | Result |
| --- | --- | --- |
| quality (3.10) | 114115137167 | success |
| quality (3.12) | 114115137036 | success |
| integration | 114115137108 | success |
| windows-ui | 114115137499 | success |

Integration job logs explicitly show:

```text
test_desktop_create_restart_edit_conflict PASSED [ 33%]
test_desktop_db_unavailable_preserves_text_and_closes_pending PASSED [ 66%]
test_real_launcher_mainloop_and_shutdown PASSED [100%]
3 passed in 5.84s
Verified all 3 desktop Mongo E2E scenarios passed; skipped=0.
```

This is remote Actions evidence, separate from the local tests above. Evidence
commits after this SHA change documentation only; final PR HEAD/checks are verified
again during handoff, and the PR Checks tab shows their current state. The optional
separate deliberate-failure PR exercise is not claimed from the local negative
display test; creating another PR still requires the user's GitHub permissions.

## Rollback

Revert `9c46be1` to remove the CI/report gate change, or `32e6430` to revert the
reading-path correction. Revert only on a feature branch; preserve database data.
No migration, database deletion, release or merge is part of these fixes.
