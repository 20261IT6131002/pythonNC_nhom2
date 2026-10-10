# PHASE 1 — TASK BOARD / TEAM 5 / 2 TUẦN

**Status:** DRAFT. M1–M5 là slot vai trò, chưa gắn GitHub username.

**Capacity:** 5×16×2 = 160 giờ (GIẢ ĐỊNH). **Planned:** W1 62h + W2 64h = **126h**. **Buffer:** 34h.

**Nguồn:** kế hoạch 9 tuần + backlog `docs/NoteApp_Team5_Blueprint/06_IMPLEMENTATION_BACKLOG.csv`, được rebaseline cho hai tuần đầu.

## 1. Tóm tắt và phụ thuộc

| Task ID | Week | Owner | Hours | Dependencies | Requirement | Reviewer | Deliverable |
|---|---|---|---:|---|---|---|---|
| P1-01 | 1 | M1 | 6 | — | DEC-01/04/08 | M5 | Kickoff + decision log + capacity |
| P1-02 | 1 | M1 | 6 | P1-01 | ADR-0001 | M3,M4 | Domain/Port/DTO/schema contract accepted |
| P1-03 | 1 | M5 | 5 | — | Tooling | M1 | pyproject dev extras, README, .env.example |
| P1-04 | 1 | M5 | 7 | P1-03 | CI/quality | M3 | GitHub CI checks thật, DB service setup |
| P1-05 | 1 | M3 | 7 | P1-02 | FR-01/02 | M1 | Note/Category/Priority/domain validation |
| P1-06 | 1 | M3 | 6 | P1-02 | PORTS | M4 | DTO/Protocol/FakeRepo/contracts |
| P1-07 | 1 | M4 | 8 | P1-02 | Mongo config | M5 | dev DB, client config, readiness |
| P1-08 | 1 | M4 | 5 | P1-06/07 | Mongo index | M3 | mapper + indexes idempotent |
| P1-09 | 1 | M2 | 6 | P1-02 | CST-02 | M1 | Tk shell + launch bootstrap path |
| P1-10 | 1 | M2 | 6 | P1-06/09 | CST-03 | M5 | bounded worker + UIEventPump main thread |
| **W1** | | | **62** | | | | **Buffer 18h** |
| P1-11 | 2 | M3 | 8 | P1-05/06 | FR-01 | M1 | CreateNote + idempotent op ID |
| P1-12 | 2 | M3 | 5 | P1-05/06/11 | FR-02/list | M4 | UpdateNote CAS + ListNotes paging |
| P1-13 | 2 | M4 | 9 | P1-06/07/08 | FR-01/02 | M3 | MongoNoteRepository CRUD subset |
| P1-14 | 2 | M4 | 4 | P1-07/08 | FR-04/05 | M5 | Mongo category unique, sample seed |
| P1-15 | 2 | M2 | 8 | P1-09/10/11/12/13 | FR-01/02/04/05 | M1 | Editor/List/Category/Priority bound to use cases |
| P1-16 | 2 | M2 | 5 | P1-15 | NFR UI | M5 | DIRTY/SAVING/SAVED/ERROR/CONFLICT |
| P1-17 | 2 | M5 | 7 | P1-05/06/11/12 | QA core | M1 | unit, contract, architecture gate |
| P1-18 | 2 | M5 | 6 | P1-13/14/15 | QA int | M4 | Mongo integration + GUI smoke evidence |
| P1-19 | 2 | M1 | 6 | P1-11..14 | ARCH/SEC | M3 | contract/schema/secret review; merge coordination |
| P1-20 | 2 | M1 | 6 | P1-15..19 | UAT | M5 | fresh clone E2E demo, signoff/next sprint |
| **W2** | | | **64** | | | | **Buffer 16h** |

**Note về dependency dạng `P1-11..14`:** nghĩa là tất cả task trong khoảng số đó. CI job W1 có thể chưa có integration test thật nhưng W2 kết thúc phải có green integration. Tại W1, P1-02 và P1-03 nên làm đồng thời.

## 2. Chi tiết W1 — task cards có thể copy thành Issues

### P1-01 — Kickoff/decisions (M1, 6h)
- **Inputs:** `01_SRS_AUDIT_AND_DECISIONS.md`, SRS v2, W1–W2 roadmap, tên 5 thành viên và khả năng thực tế.
- **Steps:** kiểm DEC-01/04/08, ghi owner/approver, confirm Mongo private dev mode, lập board 20 issues, giới hạn scope phase.
- **Done:** decision statuses/approver trong docs; estimate được team xác nhận, unresolved requirements có `BLOCKED/ASSUMPTION`.
- **Negative:** không tự đánh DEC OPEN thành APPROVED. **Backlog map:** T001.

### P1-02 — ADR + public contract freeze (M1, 6h)
- **Steps:** convert ADR template vào `docs/adr/0001-phase1-core-boundaries.md`, chốt domain, DTO, Protocol, schema, error mapping, `Clock`/version, Review với M2/M3/M4.
- **Done:** ADR Accepted; use-case signatures và ownership được review; no dependency cyclic.
- **Negative:** ports không lộ `ObjectId`, Tk, PyMongo. **Map:** T002.

### P1-03 — pyproject/env/setup (M5, 5h)
- **Files:** `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`.
- **Steps:** runtime deps tối thiểu Tk theme/PyMongo, dev pytest/Ruff, Python 3.10+; README Windows/Linux venv/install; resolve package entrypoint; không commit secret.
- **Done:** fresh venv `pip install -e ".[dev]"` và import noteapp OK; reproducible commands.
- **Negative:** no hardcoded production URI. **Map:** T009 split.

### P1-04 — real CI (M5, 7h)
- **Files:** `.github/workflows/ci.yml`, CI test scripts if needed.
- **Steps:** trigger PR→develop/push develop, Ruff check/format, unit/contract+import gate, Mongo service integration job readiness.
- **Done:** Actions run có lint/tests thật; cố tình làm fail trên branch cho thấy red; không placeholder `echo`.
- **Negative:** integration không silently skip all tests. **Map:** T009.

### P1-05 — pure domain (M3, 7h)
- **Files:** `domain/entities/{note,category}.py`, `domain/value_objects/priority.py`, `domain/policies/note_validation.py`, `domain/errors.py`.
- **Steps:** dataclasses typed, note ID opaque, title trim/length, priority rank 3/2/1, created/updated UTC/Clock, version invariant.
- **Done:** unit tests blank/1/250/251, priority invalid, UTC. **Negative:** domain import external forbidden. **Map:** T005 partial.

### P1-06 — DTO/Ports/Fakes (M3, 6h)
- **Files:** `application/dto/*`, `application/ports/{note_repository,category_repository,clock}.py`, unit fixtures.
- **Steps:** immutable inputs, views, outcomes; `NoteRepository` typed create/get/list/update CAS, fake implementation.
- **Done:** FakeRepo contract unit independent Mongo/GUI; typed exception/result mapping reviewed. **Map:** T006.

### P1-07 — dev Mongo bootstrap (M4, 8h)
- **Files:** `infrastructure/config.py`, `infrastructure/mongo/client.py`, optional `compose.dev.yml`, README setup.
- **Steps:** isolated local/dev Mongo, env-based credentials, ping/check timeouts, safe error mapping, no public port by default.
- **Done:** clean dev startup/reconnect after restart, DB ping and negative unavailable test. **Map:** T007.

### P1-08 — mapper/index foundation (M4, 5h)
- **Files:** `infrastructure/mongo/{models,indexes}.py`, `scripts/create_indexes.py`.
- **Steps:** ObjectId mapper, schema version, `name_key` unique, `client_operation_id` unique partial, list index; CLI idempotent.
- **Done:** run twice indexes remain valid; no destructive reset/TTL. **Negative:** malformed ID typed error. **Map:** T007/T017 partial; GridFS spike T008 defer W4.

### P1-09 — Tk shell (M2, 6h)
- **Files:** `presentation/tk/views/*`, `bootstrap.py`, `main.py` in coordination M1.
- **Steps:** three panes, navigation list/editor placeholders clearly labeled, layout min size, startup/shutdown works using FakeRepo.
- **Done:** screenshot/GUI smoke; UI no DB calls. **Map:** T003 partial.

### P1-10 — async bridge (M2, 6h)
- **Files:** `presentation/tk/async_bridge/{task_runner,ui_event_pump}.py`, state/presenter.
- **Steps:** `ThreadPoolExecutor` bounded, Queue, root.after main thread, request_seq, dispose handlers, fake delay 500ms.
- **Done:** UI receives input during slow task, no worker Tk API, no callback after close. **Map:** T004.

## 3. Chi tiết W2 — task cards

### P1-11 — CreateNote (M3, 8h)
- **Steps:** input normalize, title validation, clock, ID generation once per operation, repo interface, typed results; `client_operation_id` stable retry.
- **Done:** unit fake create/read, invalid title no write, repeated op ID idem. **Map:** T014 partial.

### P1-12 — UpdateNote & ListNotes (M3, 5h)
- **Steps:** update expected_version and conflict, list 30/page stable cursor; typed NotFound/Unavailable.
- **Done:** FakeRepo conflict test, list bounded, zero hidden global state. **Map:** T014/T015 partial.

### P1-13 — MongoNoteRepository (M4, 9h)
- **Steps:** create/find/list/update `find_one_and_update({_id,version}, {$set,...,$inc:{version:1}})`; duplicate op ID reconciliation; mapper, indexes, exception mapping.
- **Done:** Mongo tests persist across new client, CAS, idempotency, timezone-aware mapping. **Negative:** no local exception leaked in view. **Map:** T016.

### P1-14 — MongoCategoryRepository (M4, 4h)
- **Steps:** normalized `name_key` trim/casefold, unique index, get/list/create minimal, seed `Học tập`, `Công việc`, `Cá nhân` in dev.
- **Done:** `Study` vs ` study ` duplicates rejected; UI can choose category; no hard-coded category in entity. **Map:** T015/T017 partial.

### P1-15 — UI CRUD slice (M2, 8h)
- **Steps:** editor title/content/priority/category; create, select note, list recent, edit; invoke application use cases through async bridge.
- **Done:** demo create→save→restart→list→edit; update list without full fetch; no UI direct PyMongo. **Map:** T012/T013 partial.

### P1-16 — UI save/error/conflict state (M2, 5h)
- **Steps:** `DIRTY/SAVING/SAVED/ERROR/CONFLICT`; preserve text on failed save; Ctrl+S; close while pending; stale results dropped.
- **Done:** presenter tests and manual GUI slow I/O video. **Negative:** no `SAVED` when DB disconnected. **Map:** T012 partial.

### P1-17 — Unit/Contract/Architecture tests (M5, 7h)
- **Steps:** domain boundary tests, fake port compliance, AST forbidden imports, use-case negative tests, peer quality checks.
- **Done:** CI unit+contract green, negative example import rejected; report tests and seed requirements. **Map:** T009/T018 partial.

### P1-18 — Mongo Integration/E2E QA (M5, 6h)
- **Steps:** isolated Mongo test DB, create retry, duplicate category, CAS conflict, list pagination, DB unavailable mapping, manual Windows GUI smoke.
- **Done:** CI Mongo integration run link; E2E video/checklist; no tests skipped silently in CI. **Map:** T018.

### P1-19 — Contract/Schema/Security review (M1, 6h)
- **Steps:** inspect DTO/ports, index/schema/unique operation, secret logging, architecture gate, reviewer cross-approve PRs.
- **Done:** no open P0/P1 defect, ADR revision tracked, PRs merged to develop after checks. **Map:** T011.

### P1-20 — UAT/handover W3 (M1, 6h)
- **Steps:** fresh clone/run; create/save/restart/list/edit/error/conflict demo; link Actions results; decide accepted/not accepted; carry-over W3 issues.
- **Done:** signed 14 Phase1 AC, known limitations, handover README. **Map:** T011 + PM integration.

## 4. Review & merge order

`P1-01 → P1-02 → (P1-05/P1-06/P1-07/P1-09) → (P1-11/P1-12/P1-13/P1-14/P1-10) → (P1-15/P1-16/P1-17/P1-18) → (P1-19/P1-20)`; `P1-03→P1-04` parallel. Nên dùng PR nhỏ vào `develop`, convention `feature/p1-XX-short-slug`, ít nhất 1 reviewer khác owner.

## 5. Template Issue

```markdown
## [P1-XX] Tên task
Owner: Mx | Reviewer: My | Estimate: Xh | Week: W1/W2
Requirement/DEC/ADR: ...
Dependencies: ...
Files expected to touch: ...
Acceptance (positive, negative, edge): ...
Test command + real output: ...
Security/data/rollback: ...
Evidence: PR URL / Actions URL / screenshot/video
Status: TODO / DOING / BLOCKED / IN_REVIEW / DONE
```

## 6. Khi nào được khóa Phase 1?

Phải đạt **P1-AC01..P1-AC14** của `PHASE1_FOUNDATION_CRUD.md`, có CI thật và demo **Mongo thật**. Nếu chỉ có fake UI, chưa có CAS/idempotency/CI, thì giữ `NOT ACCEPTED`. Test coverage FR-01/02 mới là text flow partial; ảnh và reminder không nằm Phase 1.

## 7. Theo dõi triển khai thực tế — 10/10/2026

Board do người dùng cung cấp, được đưa vào Git trên `feature/task-board` sau
khi nhánh `feature/foundation` đã merge qua
[PR #2](https://github.com/20261IT6131002/pythonNC_nhom2/pull/2).
Đã fetch và xác minh `origin/develop` tại `dc4101cc739b133db14ef99d2235d4232384e362`;
nhánh hiện tại fast-forward tới commit đó, không thay đổi cây source.
Scope tiếp tục: FR-01/02/04/05 (text flow), CST-01/02/03,
P1-AC01..14; không mở rộng sang Phase 2.

**Cách đọc trạng thái:** `DONE` là deliverable kỹ thuật đã có trên nhánh foundation
đã merge và có tests/evidence dưới đây; không có nghĩa full FR hoặc Phase 1 đã
được nghiệm thu. `IN_REVIEW` là còn thiếu artifact để đối chiếu đủ Done của card;
không yêu cầu duyệt lại các ADR/DEC/UAT/review mà người dùng đã xác nhận ở
[báo cáo blocker](NOTEAPP_PHASE1_ONLY_BLOCKERS_2026-10-10.md).
Không tự sửa trạng thái OPEN/Proposed của SRS/ADR khi chưa có bản ghi cập nhật.
M1–M5 vẫn là slot từ board gốc; tên thành viên và capacity 160h là ASSUMPTION.

**Bằng chứng chung:**

- [Triển khai foundation](../../testing/PHASE1_IMPLEMENTATION.md),
  [xử lý blocker và CI](../../testing/PHASE1_BLOCKER_FIXES_2026-10-10.md).
- [CI PR #2](https://github.com/20261IT6131002/pythonNC_nhom2/actions/runs/38018848284)
  pass 4 jobs tại source SHA `96f5ec9`; đây là bằng chứng nhánh trước, không phải
  CI cho các commit mới trên `feature/task-board`.
- Kiểm tra lại baseline tại `dc4101c`: Windows/Python 3.11.9,
  Mongo dev loopback `127.0.0.1:27017`, `NOTEAPP_REQUIRE_MONGO=1`,
  `NOTEAPP_REQUIRE_UI=1`: **107 passed, 23.32s, không skip; core coverage 97%**.
  Ruff check pass; format check: **107 files already formatted**.
  Fixtures chỉ teardown DB `noteapp_test_*` do chính test tạo.

| Task | Status | AC / evidence hiện có | Phần tiếp tục / giới hạn |
|---|---|---|---|
| P1-01 | IN_REVIEW | Scope/assumptions trong plan và ADR; 20 cards trong board này | Gắn username cho M1–M5, capacity thực tế và liên kết bản ghi quyết định đã chốt; chưa tự tạo 20 GitHub Issues |
| P1-02 | IN_REVIEW | [ADR-0001](../../adr/0001-phase1-core-boundaries.md), DTO/ports/schema, architecture tests (AC02/14) | Đồng bộ artifact review đã xác nhận với ADR còn ghi Proposed; không tự nâng SRS/DEC thành APPROVED |
| P1-03 | DONE | `pyproject.toml`, `.env.example`, README; editable install trong hồ sơ foundation (AC01) | Kiểm chứng lại setup từ tracked snapshot trên nhánh này cho handover |
| P1-04 | IN_REVIEW | CI thật, Mongo/Xvfb/no-skip verifier; 4 jobs xanh ở run PR #2 (AC12) | Chưa có remote PR cố tình fail; local negative display test không thay thế bằng chứng đó |
| P1-05 | DONE | `tests/unit/test_core.py`: title blank/1/250/251, priority rank, UTC; core không import Tk/Mongo (AC02/03) | FR-01/02 chỉ text subset |
| P1-06 | DONE | Frozen DTO/Protocol, fake và Mongo cùng chạy 18 behavioral cases từ `tests/repository_contracts.py` (AC02/07/08) | Không đổi public ports; fake dùng cursor theo timestamp/ID, không offset |
| P1-07 | DONE | Config loopback/private dev, Mongo healthy; config/unavailable tests (AC13) | Không triển khai remote/public Mongo |
| P1-08 | DONE | Mapper, unique/indexes, `test_indexes_idempotent_and_no_ttl`, CLI chạy hai lần (AC08/09/13) | Không migration dữ liệu có sẵn, không TTL |
| P1-09 | DONE | Shell 3 pane, launcher/lifecycle, `tests/ui/test_shell.py`; [Windows screenshot](../../testing/PHASE1_DESKTOP_SMOKE.png) (AC11) | Screenshot là evidence kỹ thuật |
| P1-10 | DONE | `tests/unit/test_async_bridge.py`: I/O 500ms, bounded queue, owner thread, close/stale result (AC11) | Không claim NFR FPS/startup/RAM benchmark |
| P1-11 | DONE | CreateNote validation/idempotency; fake + Mongo retry/concurrency tests (AC03/04/08) | Operation ID ổn định mỗi logical create |
| P1-12 | DONE | Update CAS + 30/page; shared contract kiểm tra stale/missing/invalid version, paging theo timestamp/ID và insert giữa trang (AC06/07) | Không lặp note vì insert mới trước cursor; không hứa snapshot isolation khi note cũ bị sửa |
| P1-13 | DONE | Real Mongo restart/new client, CAS một winner, 8 retries một row, UTC, error mapping (AC04..08/13) | Atomic `update_one` + version filter đáp ứng CAS; không đổi sang `find_one_and_update` chỉ vì ví dụ card |
| P1-14 | DONE | Category trim/casefold unique; seed 3 danh mục chạy lặp, UI lookup (AC09) | Không mở full category lifecycle UI |
| P1-15 | DONE | `tests/integration/test_desktop.py`: create → restart → list → edit, category/priority binding (AC04/05/06) | Windows local và Linux Xvfb của nhánh trước |
| P1-16 | IN_REVIEW | Presenter states, editor giữ text khi validation/DB fail/conflict; Tk pending-close tests (AC10/11) | Card yêu cầu manual slow-I/O video; hiện có automated tests + screenshot, chưa có video |
| P1-17 | DONE | Unit/contract/AST gates, negative import samples, shared repository contract (AC02/03) | Baseline 107 tests → 143 tests; kết quả chi tiết trong hồ sơ follow-up |
| P1-18 | DONE | Real Mongo integration + shared contracts + Windows desktop required mode (AC04..12): 143 passed, không skip | CI nhánh mới vẫn cần chạy trên PR; CI desktop nhánh trước có link ở trên |
| P1-19 | IN_REVIEW | Foundation đã merge PR #2; sanitized telemetry/config và architecture gate xanh (AC02/13/14) | Liên kết artifact contract/schema/security review đã xác nhận; không tự cross-approve PR |
| P1-20 | IN_REVIEW | Foundation có fresh-process desktop demo và CI link; approvals trước đã được xác nhận | Bổ sung clean tracked-snapshot install/run, checklist AC01..14 và handover; không tự ký thay M1/M5 |

**Phạm vi file và dependency của nhánh này:** board + docs/testing/README để đóng
BLK-04 và sửa mapping task; tests/fakes + shared contract tests cho P1-06/12/17/18
phụ thuộc ports/domain/Mongo đã có; docs/testing cho P1-03/20 setup/handover.
AC mỗi task giữ nguyên cards W1/W2. Tests dự kiến: Ruff check/format, unit/contract
không DB/GUI, integration Mongo test cô lập, desktop/Tk với required mode, fresh
snapshot editable install và smoke. Commit riêng theo lát cắt.

**Rollback:** revert từng commit của `feature/task-board` theo thứ tự ngược;
không reset nhánh tích hợp, không xóa DB/volume, không sửa schema hay secrets.

Kết quả và bàn giao nhánh hiện tại:
[task-board follow-up](../../testing/PHASE1_TASK_BOARD_FOLLOWUP_2026-10-10.md).
