# Phase 1 — Blocker fixes, 10/10/2026

Source: [blocker report](../srs/phase%201/NOTEAPP_PHASE1_ONLY_BLOCKERS_2026-10-10.md).
Branch: `feature/foundation`; starting HEAD: `02690ff`.
Scope: BLK-01/02/03, P1-AC02/05/11/12, CST-03; existing CRUD contracts unchanged.

The user deferred BLK-04 while planning continues. Do not fabricate the 20-task
board, task IDs, owners, reviewers, or replace provisional mappings with guesses.
The source report excludes ADR/DEC/UAT approvals and independent review items
already confirmed by the user; these are not reopened by this fix.

## Changes and current status

| Blocker | Fix/evidence | Status |
| --- | --- | --- |
| BLK-03 | All six ordered reading paths in `AGENTS.md` now point to existing files. No duplicate document hierarchy. | Fixed locally and pushed (`32e6430`) |
| BLK-02 | Mongo integration job installs Xvfb/xauth/Tk, runs the three desktop tests, and verifies JUnit has all expected scenarios with no skipped/error/failure results. `NOTEAPP_REQUIRE_UI=1` disables the headless skip fallback. | Implementation verified on Windows and Linux; remote CI confirmation pending (`9c46be1`) |
| BLK-01 | Feature commits pushed. Draft PR creation attempted through GitHub; API returned 403 `Resource not accessible by integration`. User elected to create the Draft PR. | Awaiting PR and required checks at final HEAD |
| BLK-04 | User will provide the approved task board later. | Deferred explicitly by user |

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

## Remote evidence still required

Draft PR target: `develop`, head: `feature/foundation`.
[Create/view the comparison](https://github.com/20261IT6131002/pythonNC_nhom2/compare/develop...feature/foundation?expand=1).
A ready-to-paste description is in [the draft PR body](PHASE1_DRAFT_PR_BODY.md).

Record the PR URL, Actions run URL, source SHA, time and conclusions for
`quality (3.10)`, `quality (3.12)`, `integration` (including all three desktop E2E),
and `windows-ui`. Close BLK-01/02 only after these pass on the final PR HEAD.
Neither local validation nor successful pushing is a substitute for that evidence.
The optional separate deliberate-failure PR exercise cannot be claimed complete
from the local negative display test.

## Rollback

Revert `9c46be1` to remove the CI/report gate change, or `32e6430` to revert the
reading-path correction. Revert only on a feature branch; preserve database data.
No migration, database deletion, release or merge is part of these fixes.
