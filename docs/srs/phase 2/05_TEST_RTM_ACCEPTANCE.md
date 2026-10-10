# PHASE 2 — TEST STRATEGY, RTM VÀ ACCEPTANCE GATES

**Baseline:** `develop` sau Foundation + Task Board (PR #2 + #4); Phase 1 tests/CI green. **Status:** test plan, **không** là kết quả kiểm thử Phase 2. **Nguồn:** SRS gốc FR-03/06/07/11/13, NFR-PERF-01..04, NFR-SEC-03, CST-03; SRS v2 AC-03/06/07/11/13; backlog W3 T020..T028.

## 1. Chiến lược test theo lớp

| Lớp | Owner | Test suite dự kiến | Không dùng |
|---|---|---|---|
| Domain/unit | M3, M5 | validate date/sort, delete policy, transition, fake clock | DB real, Tk, sleeps |
| Application contract | M3, M5 | typed ports, fake query/trash repo, error outcomes, deterministic pagination | Raw Mongo dict/pymongo trong core |
| Infrastructure integration | M4, M5 | Mongo `$text`/indexes, combined filters, CAS delete/restore, purge state | Mock DB thay real Mongo |
| Presenter/UI unit | M2, M5 | ManualRunner, generation/stale, debounce scheduled, close pending | sleeping unbounded trong unit |
| Desktop integration E2E | M2/M4/M5 | Tk/Xvfb/Windows display, real Mongo, fresh-process restart | CI skip mà vẫn claim pass |
| Benchmark/security | M1/M4/M5 | 10k text query baseline, `explain`, input injection, idle memory baseline | claim target nếu chưa đo |

**Fixture safety:** mỗi integration test tạo `noteapp_test_<uuid>` và chỉ drop đúng DB do mình tạo, Mongo local loopback; `NOTEAPP_REQUIRE_MONGO=1` và `NOTEAPP_REQUIRE_UI=1` trong required jobs. Cấm kết nối DB production và cấm `drop_database` qua fixture nhận tên tùy ý.

## 2. Requirement Traceability Matrix (W3)

| Acceptance ID | FR / Source | Test case & expected result | Level | Priority |
|---|---|---|---|---|
| P2-AC01 | FR-06 | Text index `title` + actual `content_plain` tồn tại, search by title and content succeeds with approved matching | Mongo | Must |
| P2-AC02 | FR-06 | Vietnamese accent/token/phrase behavior exactly documented; negative punctuation/Unicode tests | Mongo/QA | Must |
| P2-AC03 | FR-06 CST-03 | debounce ~300ms; out-of-order results never overwrite newer search | Presenter/UI | Must |
| P2-AC04 | FR-06 FR-07 | keyword + category + priority + date combined uses intersection and excludes trash | Mongo | Must |
| P2-AC05 | FR-07 | Start/end equal local date inclusive; end before start rejected; boundaries respect DST and UTC | Unit/Mongo | Must |
| P2-AC06 | FR-11 | priority sorted HIGH→MEDIUM→LOW; category A→Z by normalized name, not ObjectId | Unit/Mongo | Must |
| P2-AC07 | FR-11 | created asc and desc, updated desc, stable tie `_id`, no global client sorting | Mongo | Must |
| P2-AC08 | FR-06/11 | pagination of >=65 results has no duplicate/missing under static dataset; stale cursor after filter reset not reused | Contract/Mongo | Must |
| P2-AC09 | FR-03 | soft delete increments version, sets deleted_at aware UTC, preserves content | Domain/Mongo | Must |
| P2-AC10 | FR-03/13 | deleted item excluded from active list/search, present in trash after restart | Mongo/E2E | Must |
| P2-AC11 | FR-13 | restore returns same ID/content/priority/category, increments version, returns to active list/search | Mongo/E2E | Must |
| P2-AC12 | FR-03/13 | hard delete requires modal yes/no; NO → zero DB writes, YES → permanent delete via safe pathway | UI/Mongo | Must |
| P2-AC13 | FR-02/03/13 | save-vs-delete and restore-vs-purge races produce Conflict/not-found, no silent overwrite | Unit/Mongo | Must |
| P2-AC14 | FR-13 AUD-02 | retention 30d cutoff and purge idempotency; no TTL deleting records without attachment cleanup | Mongo/QA | Must per approved scope |
| P2-AC15 | CST-03 | 500ms artificial DB operation doesn't block event loop, closed window never receives callback | UI/E2E | Must |
| P2-AC16 | NFR-SEC-03 | search/filter rejects NoSQL dict/operator injection; no secrets/content in logs | Contract/Mongo | Must |
| P2-AC17 | FR-01/02/04/05 | Phase1 create/edit/idempotency/category CAS/restart regression unchanged | Full suite | Must |
| P2-AC18 | NFR-PERF-02 | 10k fixture + 100 representative searches; report query p95 and UI p95, compare <200ms goal | Perf | Must **measure**; pass if actual metric meets threshold |
| P2-AC19 | Delivery | Fresh setup, indexes migration idempotent, CI all required jobs green for Phase2 HEAD | CI/OPS | Must |
| P2-AC20 | Delivery | UAT recorded, RTM with links, 0 P0/P1 within W3 scope, known limitations/carry-over explicit | Manual | Must |

**FR-13 priority clarification:** SRS gốc marks Trash as **Should**, not Shall. We schedule it W3 because user flow depends on safe delete, but do not rewrite original requirement priority. If the approved product baseline upgraded FR-13, link that decision in the RTM.

## 3. Test data/seed model

**Small deterministic (integration 100–200 notes):**

- Titles & content: `Học tập`, `hoc tap`, `Công việc`, `Kế hoạch`, `Lịch họp`, Unicode normalized/decomposed; same `updated_at` ties; text match in title only and content only.
- Categories: `Study`, `Công việc`, `Cá nhân`, `Straße`; missing/unclassified note; mixed priorities HIGH/MEDIUM/LOW.
- Date: local midnight ±1s, created vs updated fields, March/November DST in `America/New_York`, ordinary Vietnam day (`Asia/Ho_Chi_Minh`).
- Soft deletion: 0/29/30/31 days since deletion; deleted vs active, stale version, concurrently restored.
- 65 notes same initial timestamp sorted by `_id`; insert a new note between page fetches; edit/delete current note between pages. State clearly which cases guarantee no duplicates vs best effort under concurrent edits.

**Benchmark seed 10k (separate, never in normal CI default):** mix 10k titles and 10k body texts in UTF-8, 20% category-null, 3 priorities, all date buckets, small trash percentage. Fixed RNG seed and ID generation recorded. Generator must not clear developer data, allow only dedicated `noteapp_test_*` benchmark DB; teardown allowed only for created DB. Record Mongo version/index info/OS/RAM/CPU/network/unique dataset seed.

## 4. Negative and fault injection matrix

| Test ID | Injection/edge | Expected user-safe behavior |
|---|---|---|
| NEG-Q01 | Search `{"$ne":null}` string, literal `$where`, quotes | Treated as text/validated typed query, no operator injection |
| NEG-Q02 | Unsupported sort field/direction/date field passed to use case | ValidationError, no DB query |
| NEG-Q03 | `start_date > end_date`; invalid timezone/DST input | ValidationError; UI clear message |
| NEG-Q04 | Old search result after new user input | Ignored; never overwrites current query result |
| NEG-Q05 | Old page-2 response after filter/sort change | Ignored; cursor restarted |
| NEG-Q06 | Concurrent note inserted between pages | No repeated previous entries; new item visible on Refresh; no snapshot guarantee claimed |
| NEG-Q07 | Category with no matching notes; deleted-only matches | Correct no-results without error |
| NEG-T01 | Cancel hard delete | unchanged DB row/attachment; zero purge call |
| NEG-T02 | Repeated delete/restore/purge using same old version | rejected/idempotent as contract, no corruption |
| NEG-T03 | Update and soft-delete race on same version | one CAS winner, no overwrite |
| NEG-T04 | Restore after purge | NotFound; don't create new note implicitly |
| NEG-T05 | Purge simulated failure after attachment cleanup | cleanup state recoverable; not silent success |
| NEG-T06 | Mongo unavailable during trash operation | editor text remains, safe error, no false success |
| NEG-T07 | Delete/restore while UI window closes | no Tk callback into destroyed window, worker reconciles safely |
| NEG-T08 | Existing Phase1 note with deleted_at missing | active and searchable, not mistakenly purged |

## 5. Performance measurement (do not fake requirements)

SRS gốc says **NFR-PERF-02 search latency <200ms with 10,000 notes**; include query+UI timing traces separately. Proposed measurement (if approved DEC-09) is 100 representative searches, 20 warm-up calls, report p50/p95/p99 DB duration, UI total, index scan/total docs examined, machine configuration and Mongo physical location. A p95 result outside target is a performance bug or known deviation, not automatically PASS from `explain()`.

Other original NFR startup <2s with 5,000 notes, scroll >=60 FPS, RAM <=150 MB normal / 300MB images remain product requirements; W3 should gather baseline if needed but must not mark them met without genuine measurements on agreed platforms/hardware.

## 6. CI / quality requirements

Keep existing jobs: `quality` Python 3.10/3.12 Ruff+pytest; `integration` real Mongo 7 and Linux Xvfb desktop E2E with JUnit no-skips verifier; `windows-ui` Tk tests. Extend required tests, not just local runs. Desktop E2E new scenarios should have report verification, not be skipped because a runner lacks a display. App must run without GUI on unit/contract imports.

Suggested local commands after Phase2 implementations:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
docker compose -f compose.dev.yml up -d --wait
$env:NOTEAPP_TEST_MONGO_URI = "mongodb://127.0.0.1:27017"
$env:NOTEAPP_REQUIRE_MONGO = "1"
$env:NOTEAPP_REQUIRE_UI = "1"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q tests/unit tests/contract
.\.venv\Scripts\python.exe -m pytest -q tests/integration
.\.venv\Scripts\python.exe -m pytest -q tests/ui
```

Use existing venv if installed. If CI cannot run display on one platform, record explicit affected job and not claim required E2E pass. Every new code path has **positive, negative, race** tests; no marker exclusion to hide failing tests.

## 7. Regression smoke script for M1/UAT

1. Start local Mongo (`docker compose -f compose.dev.yml up -d --wait`); run index setup twice and ensure no data loss.
2. Create note `Học tập`, HIGH priority, category `Học tập`, content `Ôn tập`.
3. Restart app. Note exists and updates safely as Phase1.
4. Search `Ôn tập`; verify visible according to approved Mongo full-text semantics, then category filter.
5. Filter date includes today; reverse range shows validation.
6. Sort priority/created/updated/category with sample notes and verify deterministic results.
7. Move note to Trash; active search no longer shows it; Trash shows it after restart.
8. Restore it; active search shows same ID/content; version is newer.
9. Try permanent delete → choose NO: note remains. Retry → YES: note no longer exists.
10. Simulate DB outage and slow I/O; UI does not lock, errors do not claim success; no text lost from unsaved editor.
11. Verify older Phase1 CRUD/contract tests still green and GitHub Actions run associated with actual Phase2 PR SHA has all checks green.

## 8. Test results template (fill with real observations)

```markdown
# PHASE2 TEST REPORT — <date / commit>
Branch/SHA/PR: ...
Environment: Windows/Linux/macOS; Python ...; Mongo ...; Tcl/Tk ...
Index/migration: applied twice? ...
Unit: <count pass/fail/skip>; Contract: ...; Mongo Integration: ...; Desktop E2E: ...
10k search benchmark: seed ...; p50 ... ms; p95 ... ms; p99 ... ms; NFR-PERF-02 PASS/FAIL/UNVERIFIED
RTM P2-AC01..20: links to each case & evidence
Incidents: P0... / P1... / postponed ...
Reviewer M1/M5: ... (human approval only)
Known limitations: ...
Rollback: ...
```

**Never fabricate run URLs/test counts/benchmark results or sign UAT on someone's behalf.**
