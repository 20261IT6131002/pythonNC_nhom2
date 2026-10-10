# P2-02 — contract freeze review record

Date: 2026-10-10. Task: P2-02 / T020 / D0. Status: **IN_REVIEW**.
Branch: `docs/p2-02-contract-freeze`; source branch: `feature/phase-2` at `b29d35f`.
Starting working tree: clean. Scope follows the user's request to start at task 02,
commit and stop for review. P2-03..18 are not implemented by this change.

## Deliverable and requirement trace

- [ADR-0002](../adr/0002-phase2-query-trash-contract.md): proposed choices,
  P2-01 dependency/assumptions and owner review gates.
- [Exact public interfaces](../architecture/PHASE2_PUBLIC_CONTRACTS.md): immutable
  search/local-date/UTC criteria, sort whitelist, query/trash ports, outputs,
  typed errors, IDs, version/CAS, cursor provenance and downstream test cases.
- [Data/migration recipe](../architecture/PHASE2_DATA_MIGRATION.md): named text
  field/index, candidate compound indexes, v1 compatibility/lazy tombstones,
  dry-run/preflight, safe purge, FR-14/W4 handoff and rollback.
- Phase 2 task board and search/trash plan annotations link these exact proposals
  instead of leaving downstream owners to choose incompatible illustrative APIs.

FR-03/06/07/11 are Shall; FR-13 remains Should. Trace also covers FR-04/05 filters,
NFR-SEC-03 and CST-03. P2-AC01/04..14/16/17/19 are mapped as downstream
obligations, **not claimed as passed Phase 2 features**. No SRS/DEC approval,
cross-team review or migration approval is signed by the agent.

## Actual validation

Commands use the existing `.venv/Scripts/python.exe` on Windows/Python 3.11.9.
Real Mongo dev is healthy and bound to `127.0.0.1:27017`. Integration fixtures
create/delete only their own random `noteapp_test_*` DBs.

| Command | Actual result |
|---|---|
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` | 110 files already formatted |
| `python .venv/tools/p2_02_contract_check.py` | 5 Python declaration blocks compile/type-resolve; 10 frozen DTO/port records, 2 typed ports, safe defaults and 19 local Markdown links checked |
| `python -m pytest -q --cov=noteapp.domain --cov=noteapp.application --cov-report=term-missing --junitxml=.venv/tools/p2-02-regression.xml` | **143 passed, 29.30s, no skips**; core statement coverage **97%** (276 statements, 9 missed) |
| `git diff --check` and final staged whitespace check | Passed |

The full suite sets `NOTEAPP_TEST_MONGO_URI=mongodb://127.0.0.1:27017`,
`NOTEAPP_REQUIRE_MONGO=1`, `NOTEAPP_REQUIRE_UI=1`. All existing real Mongo,
shared fake/Mongo contracts, separate-process desktop scenarios and Windows shell
tests ran. Coverage describes existing core behavior, not future scaffold features.
The declaration check validates documented signatures/defaults/types and links,
not unimplemented search/trash behavior. Its script and JUnit report are retained
as ignored artifacts under `.venv/tools`; no new runtime or permanent behavior
tests are needed for this documentation-only D0 slice.

## Independent review checklist

| Reviewer | Review item | State |
|---|---|---|
| M2 | DTO/control names, allowed sort combinations, query generation, cancel/confirmation semantics | Pending independent review |
| M3 | Core-only types, UTC normalization, error/replay semantics, use-case/port ownership | Pending independent review |
| M4 | Cursor sort tuples, lookup/index candidates, lazy schema/dry-run, conditional purge guard | Pending independent review |
| M5 | AC/negative/race matrix, fake/Mongo parity obligations, no false feature/CI claim | Pending independent review |
| M1 / existing decision owner | Link actual P2-01 decisions and migration approval; resolve ADR assumptions | Artifact values not available in this checkout |

The team's earlier DEC confirmations are preserved. Missing value/artifact links
are not a request to repeat an approval, and technical assumptions do not replace
the existing decisions. Automatic retention and unsupported attachment/lock purge
remain gated for their respective implementation tasks.

## Files, risk and rollback

Changed files (M1/M5 documentation ownership):

- `docs/adr/0002-phase2-query-trash-contract.md`.
- `docs/architecture/PHASE2_PUBLIC_CONTRACTS.md`.
- `docs/architecture/PHASE2_DATA_MIGRATION.md`.
- `docs/srs/phase 2/02_PHASE2_TASK_BOARD.md`.
- `docs/srs/phase 2/03_SEARCH_FILTER_SORT_CONTRACT.md`.
- `docs/srs/phase 2/04_TRASH_LIFECYCLE_CONTRACT.md`.
- This review record, `docs/testing/PHASE2_P2_02_REVIEW.md`.

Risk: proposed defaults/replay/category collation/schema recipe require comparison
with P2-01 artifacts and owner review before affected implementation merges.
Runtime code, public Phase 1 signatures, schema/indexes and CI workflow do not change.
No production data, credentials, plaintext drafts, release or branch merge is touched.
Rollback: `git revert <P2-02 commit>` on a feature branch; preserve DB data/volumes.
Remote CI evidence is pending a future PR; earlier Phase 1 CI does not cover this SHA.
