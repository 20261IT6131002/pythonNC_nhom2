# P2-02 — contract freeze review record

Date: 2026-10-10. Task: P2-02 / T020 / D0. Status: **REQUEST_CHANGES / IN_REVIEW**.
Branch: `feature/p2-02-contract-freeze`; source branch: `feature/phase-2` at `b29d35f`.
Originally named `docs/p2-02-contract-freeze`; renamed after `1df944c` at user request.
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

### Initial `1df944c` evidence (historical)

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
The initial declaration check validated documented signatures/defaults/types and
links, not search/trash behavior. It was a one-off ignored script; CF-06 now replaces
that reproducibility gap with tracked CLI/contract tests described below.

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
the existing decisions. Automatic text-only retention stays W3/P2-12 with its
safety/implementation gate; unsupported attachment/lock cleanup belongs to W4.

## Tech lead follow-up — CF-01..07

Source: [review at 1df944c](../srs/phase%202/review/NOTEAPP_P2_02_CONTRACT_FREEZE_REVIEW.md).
The source review remains historical; this table is the agent's fix/evidence record,
not independent approval or a replacement for REQUEST_CHANGES.

| Finding | Fix/evidence | Current gate |
|---|---|---|
| CF-01 | ADR now owns agreed-value/evidence/state/owner per A2-*; user's "đã chốt" confirmation preserved; actual per-case values absent, so DEFERRED/BLOCKED rather than invented MATCHED | OPEN: attach existing P2-01/DEC-02/07/09 values/source; ADR not Accepted/Frozen |
| CF-02 | Master plan, board P2-12, trash contract, migration recipe and AC14 now require W3 automatic verified text-only retention; W4 adds blob cleanup, not an unconditional retention delay | Documentation inconsistency addressed; real P2-12 worker/tests still required, no scope change/CR approval fabricated |
| CF-03 | Existing PR #5 verified; current base is feature/phase-2, which CI does not target; no PR-triggered run for 1df944c. Merge-tree against current origin/develop is conflict-free | OPEN: retarget existing PR to develop, publish reviewed commits, verify jobs at that source HEAD and independent review |
| CF-04 | Concrete Windows IANA/CLDR/tzdata strategy, fail-closed dated queries with undated CRUD preserved; 23h/25h and fold/gap test obligations | Design addressed; implementation/tests belong to P2-04/16, not falsely claimed here |
| CF-05 | Current branch metadata fixed in ADR/board/report; original docs/ name retained only as explicit history | Addressed locally |
| CF-06 | Tracked scripts/verify_phase2_contract.py and tests/contract/test_phase2_documentation.py; CI quality/windows jobs already run tests/contract, no workflow trigger changes needed | Reproducibility addressed locally; remote execution remains CF-03 |
| CF-07 | [Concrete category/text/seek prototype](../architecture/PHASE2_CATEGORY_QUERY_PLAN.md), 10k seed/EXPLAIN/DB+UI timing receipt, compatible optimization fallback | Design addressed; actual P2-05/06/16 prototype/benchmark remains unmeasured |

### Verified remote/base observations

Git fetch verified `origin/develop` at `16b4897eca1abd6e88870cc16d511c339a0efb20`.
`git merge-tree --write-tree --messages HEAD origin/develop` at `1df944c`
returned exit 0/no conflicts. This is a dry-run, not a merge/rebase or CI result.

GitHub read-only metadata verified
[PR #5](https://github.com/20261IT6131002/pythonNC_nhom2/pull/5): open, not draft,
head `feature/p2-02-contract-freeze` at `1df944ca14d652853db8ed0354f84f040fcf16e8`,
base `feature/phase-2` at `b29d35f8ae9d214504a7468932acea36fa34ca03`.
The PR is mergeable, but its target is outside ci.yml pull_request branches
`main/develop`; commit workflow-run lookup returned no PR-triggered runs.
This is not an observed CI failure and does not call the existing PR absent.
Change the existing PR base to develop rather than creating a duplicate; its
independent review/green final-source-SHA checks remain required before merge.

### Reproducible checks after the follow-up

`python scripts/verify_phase2_contract.py` works from a clean installed checkout
or `--root <trusted-checkout>`. It compiles the five declaration blocks, resolves
typed/frozen fields/ports/defaults and checks local Markdown references, including
the tracked source review. It executes only trusted repo declarations, not external
query content, and does not validate decisions or unimplemented Phase 2 features.

`tests/contract/test_phase2_documentation.py` exercises real documents/CLI plus
negative mutable DTO, changed defaults, unsafe default confirmation, unresolved/
missing return types, missing protocol, malformed/missing code block, broken link
and missing required document. Existing CI suite commands collect these tests.

| Follow-up command | Actual result |
|---|---|
| `python scripts/verify_phase2_contract.py` | 5 declaration blocks, 10 frozen models, 2 typed ports, 29 local links verified |
| `python -m pytest -q tests/contract/test_phase2_documentation.py` | 12 passed, 0.90s |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` | 112 files already formatted |
| `python -m pytest -q --cov=noteapp.domain --cov=noteapp.application --cov-report=term-missing --junitxml=.venv/tools/p2-02-review-fixes.xml` with required Mongo/UI | **155 passed, 31.33s, no skips**; existing core coverage **97%** (276 statements, 9 missed) |
| `git diff --check`; staged whitespace check | Passed |

The first new checker-test run had 11 passed/1 failed: missing-document preflight
reported a broken link before its missing-file error. The checker now reads required
documents before verifying links; the same negative test passes without being
removed or weakened. Final regression includes all Mongo and Tk scenarios; no
Phase2 search/trash/runtime benchmark implementation is claimed from these checks.

## Files, risk and rollback

Changed files (M1/M5 documentation ownership):

- `docs/adr/0002-phase2-query-trash-contract.md`.
- `docs/architecture/PHASE2_PUBLIC_CONTRACTS.md`.
- `docs/architecture/PHASE2_DATA_MIGRATION.md`.
- `docs/architecture/PHASE2_CATEGORY_QUERY_PLAN.md` (CF-07 execution strategy).
- `docs/srs/phase 2/01_PHASE2_MASTER_PLAN.md` (CF-02 scope consistency).
- `docs/srs/phase 2/02_PHASE2_TASK_BOARD.md`.
- `docs/srs/phase 2/03_SEARCH_FILTER_SORT_CONTRACT.md`.
- `docs/srs/phase 2/04_TRASH_LIFECYCLE_CONTRACT.md`.
- `docs/srs/phase 2/05_TEST_RTM_ACCEPTANCE.md` (CF-02 AC14 gate).
- `docs/srs/phase 2/review/NOTEAPP_P2_02_CONTRACT_FREEZE_REVIEW.md` (supplied source).
- This review record, `docs/testing/PHASE2_P2_02_REVIEW.md`.
- M5 QA: `scripts/verify_phase2_contract.py`,
  `tests/contract/test_phase2_documentation.py` (CF-06 repeatable gate).

Risk: proposed defaults/replay/category collation/schema recipe require comparison
with P2-01 artifacts and owner review before affected implementation merges.
Application runtime, public Phase 1 signatures, schema/indexes and CI workflow do
not change; the tracked checker and its tests are QA tooling only.
No production data, credentials, plaintext drafts, release or branch merge is touched.
Rollback: `git revert <P2-02 commit>` on a feature branch; preserve DB data/volumes.
Remote CI evidence is pending a future PR; earlier Phase 1 CI does not cover this SHA.
