Phase 1 implements text create/list/edit in the Tk desktop with Mongo persistence,
seeded category lookup and priority. Create retries use a stable operation ID;
updates use atomic version checks. Bounded workers preserve editor text on errors,
conflicts and late responses.

The blocker fixes correct all six source paths in AGENTS.md and add desktop-to-Mongo
E2E under Linux Xvfb. The integration job requires all three scenarios to run without
skips and checks their JUnit report. Windows UI checks remain in place.

Scope: FR-01/02/04/05, CST-01/02/03, P1-AC02/05/10/11/12/13, BLK-01/02/03.
BLK-04 is deferred by the user while planning continues; no task-board assignments
are invented. ADR/DEC/UAT approvals excluded by the latest blocker report are not
requested again.

Validation: 107 local Windows unit/contract/Mongo/Tk tests passed; all three desktop
E2E passed under Linux/Python 3.12/Xvfb with real Mongo, skipped=0. Ruff check/format
and actionlint passed. Required UI mode without a display fails instead of skipping.
Remote Actions results must be verified for this PR's HEAD.

Config is limited to loopback/isolated development and test databases. Teardown
owns only generated test DBs; no production data, destructive migrations, note TTL,
release or automatic merge. Rollback: revert individual commits in reverse dependency
order while preserving DB data. Details: docs/testing/PHASE1_BLOCKER_FIXES_2026-10-10.md.
