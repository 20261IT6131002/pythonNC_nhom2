# PHASE 2 — TASK BOARD / 18 SUBTASK CHO TEAM 5

**Nguồn bắt buộc:** W3 trong `docs/NoteApp_Team5_Blueprint/06_IMPLEMENTATION_BACKLOG.csv`, nguyên 9 task gốc `T020–T028`. **Không đổi FR priority:** FR-03/06/07/11 Shall, FR-13 Should. `M1–M5` là slot vai trò từ Phase 1, chưa được gán tên GitHub thực tế. **Total 86h / Week 3** theo estimate gốc.

## 1. Bảng phân chia (có thể tạo 18 GitHub Issues)

| ID | Gốc | Owner | h | PR slice | Đầu ra cụ thể | Phụ thuộc |
|---|---|---|---:|---|---|---|
| P2-01 | T020 | M1 | 3 | D0 | Search semantics, date semantics, delete policy/approved DEC refs | Phase1 merged |
| P2-02 | T020 | M1 | 4 | D0 | Freeze DTO/Port/index/AC, review cross-team, migration approval | P2-01 |
| P2-03 | T023 | M3 | 6 | S1 | Typed `SearchNotesCriteria`, `SortMode`, value rules, `SearchNotes` | P2-02 |
| P2-04 | T023 | M3 | 7 | S1 | Filters/day UTC conversion/portable query use-case + sort validation | P2-03 |
| P2-05 | T025 | M4 | 4 | S2 | Mongo text index/probe Vietnamese + schema/index migration plan | P2-02 |
| P2-06 | T025 | M4 | 8 | S2 | Mongo indexed query + category sort + stable cursor/pages | P2-03/04/05 |
| P2-07 | T021 | M2 | 7 | S3 | Search bar + category/priority/date/sort controls; 300ms debounce | P2-02/03 |
| P2-08 | T021 | M2 | 6 | S3 | Presenter generation/cursor reset/late results/async UI states | P2-06/07 |
| P2-09 | T024 | M3 | 5 | T1 | Domain delete/restore transitions, errors, CAS invariants | P2-02 |
| P2-10 | T024 | M3 | 3 | T1 | Trash/Restore/Purge use cases + typed ports/outputs | P2-09 |
| P2-11 | T026 | M4 | 4 | T2 | Mongo trash repo, CAS, `deleted_at`, restore and manual purge | P2-09/10 |
| P2-12 | T026 | M4 | 3 | T2 | Automatic retention 30d text-only, bounded safe worker, no TTL, replay/restore guard; blob cleanup W4 | P2-11 |
| P2-13 | T022 | M2 | 5 | T3 | Trash navigation/list/restore/permanent delete controls | P2-10/11 |
| P2-14 | T022 | M2 | 3 | T3 | Confirmation, unsaved protection, soft-delete undo/toast | P2-13 |
| P2-15 | T027 | M5 | 7 | Q1 | Search Vietnamese fixtures, test semantics/race/security | P2-03/05 |
| P2-16 | T027 | M5 | 5 | Q1 | Sort/filter/date/index/explain + pagination + performance baseline | P2-04/06 |
| P2-17 | T028 | M5 | 4 | Q2 | Trash concurrency/restore/purge/fault Mongo tests | P2-10/11 |
| P2-18 | T028 | M5 | 2 | Q2 | Desktop smoke + RTM + CI evidence/handover | P2-08/14/17 |
| **TỔNG** | **T020–T028** | | **86** | | **No scope omitted** | |

### Ownership & availability warning

| Role | Effort W3 | Capacity giả định | Vênh | Cần xử lý |
|---|---:|---:|---:|---|
| M1 — PM/Architect | 7h | 16h | -9h | Có thể hỗ trợ review/QA/docs nhưng **không** tự nhận file M2–M5 khi chưa thống nhất |
| M2 — Tk UI | 21h | 16h | +5h | Ưu tiên S3 search UI trước T3 trash; hỗ trợ UI từ M1 nếu có kỹ năng |
| M3 — Domain/App | 21h | 16h | +5h | Contract freeze Day1; không code lại Phase1 ports tùy tiện |
| M4 — Mongo/Data | 19h | 16h | +3h | Index/query và trash là đường găng; tránh thêm new category CRUD ngoài sprint |
| M5 — QA/CI | 18h | 16h | +2h | Chuẩn bị fixtures từ Day1, PR continuous checks |
| **Tổng** | **86h** | **80h** | **+6h** | PM có lựa chọn schedule trong master plan |

**Lưu ý thực hiện:** 18 subtasks này là phân rã đúng tổng giờ và scope gốc, chưa được gán status DONE hay GitHub Issue/PR. Nếu muốn 16h/người/W3 phải reassign/CR hoặc kéo sang đầu W4; mọi công việc carry-over cần ID + risk riêng.

## 2. Các task cards chi tiết

### P2-01 — Search/Delete Decision Freeze (M1, 3h)
- **Source:** T020, FR-03/06/07/11/13; DEC-02/07/09 đã chốt ở nhóm (đính kèm artifact vào board, không duyệt lại).
- **Steps:** xác nhận token search `$text`, diacritic/phrase behavior tiếng Việt; meaning `start/end` local + field `created_at` hay `updated_at` mặc định; category sort locale; xóa mềm/hard; 30d retention; scope purger với ảnh W4; lập danh sách use cases rõ ràng.
- **Output:** `docs/adr/0002-phase2-query-trash-contract.md` hoặc update ADR nếu group dùng 1 file; Decision Trace table + examples chốt.
- **Done:** Có link approved decision hiện có, mỗi edge behavior có test expected; nếu thiếu ghi `ASSUMPTION` và blocker chỉ cho phần tương ứng.

### P2-02 — Shared interfaces & risk review (M1, 4h)
- **Files:** `application/dto/*`, `ports/*`, `docs/architecture/*`, migration notes, branch merge order.
- **Steps:** freeze `SearchCriteria`/`SortMode`, `SearchRepository`/`TrashRepository`, error codes; chốt `deleted_at`, CAS + version, UUID/existing IDs; review `text index` field `content_plain`, backward-compatibility, search vs locked-note FR-14 future.
- **Done:** M2/M3/M4/M5 có interface và data rules để làm song song; PR D0 chỉ docs/contract/tests, không mang Mongo + UI logic chung commit.

### P2-03 — Search DTO + use case (M3, 6h)
- **Files:** `application/queries/search_notes.py`, `application/dto/note_filter.py`, new `application/ports/note_query_repository.py` (hoặc extension nonbreaking được duyệt).
- **Steps:** create frozen input: `text`, `category_id`, `priority`, `date_field`, `start_date`, `end_date`, `sort`, `direction`, `page_size`, `cursor`; typed output `NoteListView` reused; no Mongo `dict` from UI; whitelist sort & date field.
- **Tests:** empty text = non-text filter; empty/invalid category; invalid enum/range/limit/cursor; SRS title/content source fields mapped only in adapter.
- **Done:** FakeRepo contract green without Mongo/Tk; architecture AST gate green.

### P2-04 — Date/Filter/Sort policy in core (M3, 7h)
- **Steps:** ISO local inclusive days → aware UTC half-open interval, invalid date, DST transition local zone, category and priority combined; default sort updated desc; priority numeric rank; category name A–Z, tie `_id`.
- **Tests:** start=end single day; end before start rejected; UTC boundary notes; priority HIGH/MEDIUM/LOW, creation ascending/descending; no global client sorting.
- **Done:** typed validation + deterministic FakeClock/timezone fixtures; no `datetime.utcnow()` naive.

### P2-05 — Text index and semantics spike (M4, 4h)
- **Files:** `infrastructure/mongo/indexes.py`, `scripts/create_indexes.py` and optional `scripts/seed_search_fixture.py`, docs query semantics.
- **Steps:** `text` index `{title:'text',content_plain:'text'}`, verify UTF-8 Vietnamese title/content; test accent/case/token/phrase with real Mongo; choose `default_language` via approved DEC (avoid silently promising Vietnamese stemming); check index exists after repeated setup; report `explain()`.
- **Tests:** seek title-only, content-only, phrase, accented/no-accent examples; no accidental textual leak of encrypted future content.
- **Done:** documented matching semantics + index setup idempotent, no destructive reset/TTL.

### P2-06 — Mongo Query Adapter (M4, 8h)
- **Files:** `infrastructure/mongo/repositories.py` or separate `note_query_repository.py`, `models.py`, indexes; `scripts/create_indexes.py`.
- **Steps:** `$text` + active filter + date `[gte,lt)` + category/priority; sorts priority/category/created/updated with stable ID tie; keyset cursor includes version/sort/filter validation; category A–Z by normalized `categories.name_key` (e.g. `$lookup`, check indexes/explain), source date field approved; `.limit(30+1)`; typed errors.
- **Tests:** no `$where` injection, invalid sort rejected, 65+ pages, same timestamp, newly inserted between pages, combined query, deleted excluded, optional missing category; `maxTimeMS`/timeout strategy if approved.
- **Done:** shared fake/Mongo query contracts; baseline realistic explain, no full-table Python sort.

### P2-07 — Desktop Search/Filter Controls (M2, 7h)
- **Files:** `presentation/tk/views/sidebar.py`, `note_list.py`, optional `search_toolbar.py`; no direct DB access.
- **Steps:** Ctrl+F focus, search Entry, date picker or validated date entry, category+priority selectors, sort Combo, clear/reset, result count, colored priority; use stable toolbar avoiding resize thrash.
- **Tests:** keyboard navigation; no results state; date invalid feedback; UI responsive during 500ms worker; widths 20/30/50 retained at supported resolutions.
- **Done:** screenshot/manual smoke, button/keyboard wired, no inert UI.

### P2-08 — Search Presenter & async state (M2, 6h)
- **Files:** `presentation/tk/presenters/notes_presenter.py`, `state/list_state.py`, `views/app_window.py`, plus existing `UIEventPump` only if necessary.
- **Steps:** 300ms debounce with `root.after` owner thread; every query generation ID; stale responses ignored including initial list; new filter/sort invalidates cursor, clear list correctly; append only same filter fingerprint; cancel scheduled timer on close; do not cancel in-flight Mongo task unsafely.
- **Tests:** typed 1-2-3 fast input out-of-order results, clear while loading, scroll load-more while query changes, close during pending; no user content loss when list changes.
- **Done:** deterministic `ManualRunner`/fake tests + real UI smoke.

### P2-09 — Domain deletion policy (M3, 5h)
- **Files:** `domain/policies/delete_policy.py`, `domain/errors.py`, possible immutable tombstone/value objects (without bringing BSON in).
- **Steps:** explicit active→deleted→restored transitions; version compare; double delete behavior, restore conflict, already purged not found; deletion clock is aware UTC; define safety/attachment-in-progress guard future W4.
- **Tests:** state machine table, stale expected version, timestamps, absence from active list after delete.
- **Done:** pure domain/service, no PyMongo imports.

### P2-10 — Trash/Restore/Purge use cases (M3, 3h)
- **Files:** current scaffold `application/commands/{trash,restore,purge}.py`, `application/ports/trash_repository.py`, optional `queries/list_trash.py`.
- **Steps:** typed input note_id/expected_version, `TrashNote`, `RestoreNote`, `PurgeNote` and `ListTrash` use cases; confirm flag stays in UI/interaction (core requires explicit intent token for irreversible action if agreed), error mapping NotFound/Conflict/Unavailable.
- **Tests:** fake transitions, delete retry semantics, restore/hard-delete negative, no silent overwrite.
- **Done:** caller only uses application types; no UI dialog inside use cases.

### P2-11 — Mongo Trash Adapter + compatible migration (M4, 4h)
- **Files:** `infrastructure/mongo/repositories.py` or `trash_repository.py`, `models.py`, `indexes.py`, `migrations.py`.
- **Steps:** filter `{_id,version,is_deleted:false}` `$set is_deleted:true,deleted_at:clock` `$inc version:1`; restore CAS with `is_deleted:true`, clear deleted_at; trash list 30/page sorted deleted_at desc/_id desc; permanent purge with safe guard; phase1 records still readable; indexes for trash, `--dry-run` documented.
- **Tests:** real DB snapshot, concurrent update-vs-delete, deleted excluded all active/search, restore same id/new version, double action, no hard deletes without acknowledgement.
- **Done:** index/migration repeatable, no data loss Phase1, DB error sanitized.

### P2-12 — Automatic retention/Purge worker, W3 text-only (M4, 3h)
- **Files:** `infrastructure/scheduler/purge_worker.py`, trash adapter maintenance port/tests.
- **Steps:** giữ automatic retention 30 ngày trong W3 cho text-only đã xác minh; không TTL vì AUD-02. Clock-injected cutoff, bounded scan, per-record eligibility, atomic ID/version/deleted-state/cutoff removal; restore thắng CAS thì không purge. Activation gated bởi tests/safety review của P2-12. Note có ảnh/format chưa hỗ trợ giữ nguyên đến cleanup W4; không coi no-op adapter là đã cleanup. Không tự bật destructive worker khi startup.
- **Tests:** no purging active/restored/recent, re-run safe, crash during simulated attachment cleanup leaves retryable state; never use `delete_many({})` or `drop` outside fixture DB.
- **Done:** worker automatic text-only đã hiện thực, tested và qua safety review; cutoff/replay/restore race/unsupported payload tests pass. Nếu chỉ scaffold/disabled thì chưa DONE và AC14 chưa đạt. Nếu team dời khỏi W3 phải có approved CR + carry-over ID/owner/target/risk, giữ AC14 remaining; checkpoint này không duyệt scope move hay đổi 3h estimate.

### P2-13 — Trash UI views (M2, 5h)
- **Files:** `presentation/tk/views/sidebar.py`, `note_list.py`, `app_window.py`; may add `trash_view.py` only if useful.
- **Steps:** list/tab Active–Trash, title/date/status/count, select trashed item, Restore/Permanently Delete actions, pagination; keep `EditorPresenter` coherent if user deletes currently edited note.
- **Tests:** GUI smoke delete→trash→restore; active/trash isolation; DB disconnected retry states.
- **Done:** no reused active query accidentally shows soft deleted; no UI with direct PyMongo.

### P2-14 — Dialogs and unsaved guard (M2, 3h)
- **Files:** `presentation/tk/views/dialogs.py`, `presenters/editor_presenter.py`, `state/editor_state.py` if minimal.
- **Steps:** clear soft-delete confirmation as SRS flow, **modal yes/no for permanent**; cancel = zero DB writes; warning dirty/saving; undo/restore feedback; failure retains content and selection; no destroyed widget callback.
- **Tests:** cancel hard delete no writes; active edit conflict with delete; while saving no hidden text loss; dialog appears only main thread.
- **Done:** UI action wired to typed use-case, not fake button.

### P2-15 — Search semantics & race QA (M5, 7h)
- **Files:** `tests/unit/*`, `tests/contract/*`, `tests/integration/test_search.py`, deterministic Vietnamese fixtures.
- **Steps:** approved Vietnamese/accent cases, phrase/quotes/invalid search input, empty query, title vs content, deleted excluded, search limit, late response race; search guard negative test rejects raw BSON from UI.
- **Done:** tests fail before feature implementation as red evidence and pass after; no blanket skip CI.

### P2-16 — Filters/sorting/performance QA (M5, 5h)
- **Files:** `tests/integration/test_search.py`, `tests/repository_contracts.py`, optional `scripts/seed_search_fixture.py` & benchmark report.
- **Steps:** all four sort modes, priority_rank, category rename/missing reference handling, local-day UTC boundary, combined filters, cursor stable after new item, index info/`explain`; seed 10k deterministic if resource allows; report raw machine conditions and p95.
- **Done:** no false claim <200ms; baseline saved, query-by-query evidence.

### P2-17 — Trash/restore/purge QA (M5, 4h)
- **Files:** `tests/unit/test_delete_policy.py`, `tests/integration/test_trash.py`, fake shared contract tests.
- **Steps:** soft-delete active→trash, restore same id, hard-delete cancel/yes, stale revision, duplicate delete/purge, idempotent replay, DB unavailable/error envelope, retention cutoff; future attachment cleanup test adapter stub explicitly.
- **Done:** Mongo test isolated `noteapp_test_*`, fixture cleanup own DB only, 0 unhandled DB exceptions in UI.

### P2-18 — End-to-end & release evidence (M5, 2h)
- **Files:** `tests/integration/test_desktop.py`, `tests/desktop_scenarios.py`, `docs/testing/PHASE2_TEST_REPORT.md`, RTM, CI logs.
- **Steps:** fresh process create→search→filter→sort→delete→restart→restore, JUnit no skips, verify GitHub run SHA required jobs; summarize known limitations & handover W4. M1 signs UAT according to team workflow (no automated proxy sign).
- **Done:** links to CI run, screenshot/video, test output/coverage, demo script; historical CI Phase1 cannot substitute new run.

## 3. PR slices và merge order tránh cùng sửa file

- **D0 (P2-01/02)** contract freeze, paths/ADR/schema only.
- **S1 (P2-03/04)** application DTO/use case/port + fake unit tests; *M3 owns these files*.
- **S2 (P2-05/06)** Mongo text/query/index + migration docs; *M4 owns index/repo files*.
- **S3 (P2-07/08)** UI search state/view/presenter; *M2 owns views/presenters*.
- **T1 (P2-09/10)** core trash/restore/purge interface.
- **T2 (P2-11/12)** Mongo trash and maintenance; consolidate Mongo index changes with S2 to avoid concurrent editing file `indexes.py`.
- **T3 (P2-13/14)** UI Trash: merge/search UI first, then extend its navigation; don't modify `app_window.py` in two open PRs without coordination.
- **Q1/Q2 (P2-15..18)** tests can start red early, target the associated PR or append test-only PR after APIs freeze; don't depend on a mega-PR.

## 4. Template đưa vào GitHub Issue

```markdown
## [P2-XX] <task title>
Source backlog: T0XX | SRS: FR-XX, NFR-XX | Phase: W3
Owner: Mx | Reviewer: My | Estimate: Nh | Priority: P0/P1
Depends on: P2-..
Allowed files: ...
DoR: links SRS/DEC contract and acceptance examples
Implementation steps:
- [ ] ...
- [ ] ...
Tests (positive, negative, race): ...
Done evidence: PR / CI URL / screenshots / DB migration explain
Rollback/data impact: ...
Status: TODO | DOING | IN_REVIEW | BLOCKED | DONE
```

## 5. Chú ý Source-of-Truth

`PHASE1_TASK_BOARD` đã merge; **không sửa status Phase1** trong Phase2. Tài liệu này đề xuất task W3 theo backlog cũ: mỗi thay đổi estimate, owner, scope/schedule phải ghi lại trong board sau kickoff, không tự tuyên bố đã phê duyệt.

## 6. Checkpoint P2-02 — 10/10/2026

Người dùng yêu cầu bắt đầu P2-02 trên nhánh mới từ nhánh Phase 2 hiện tại,
commit rồi dừng để review. Branch hiện tại `feature/p2-02-contract-freeze` được tạo trực tiếp
từ `feature/phase-2` tại `b29d35f`, working tree ban đầu sạch; không tự chuyển
base sang develop hoặc triển khai P2-03 trở đi. Tên ban đầu là
`docs/p2-02-contract-freeze`, sau commit `1df944c` đã đổi theo yêu cầu người dùng.

| Task | Status | Deliverable / evidence | Dependency và phần cần review |
|---|---|---|---|
| P2-02 | IN_REVIEW / REQUEST_CHANGES | [ADR-0002](../../adr/0002-phase2-query-trash-contract.md), [exact interfaces](../../architecture/PHASE2_PUBLIC_CONTRACTS.md), [data/migration recipe](../../architecture/PHASE2_DATA_MIGRATION.md), [review/checks](../../testing/PHASE2_P2_02_REVIEW.md) | Tech lead review CF-01..07; chưa Accepted/Frozen; giá trị/evidence P2-01 và PR/CI gate còn cần đối chiếu |

Dependency P2-01: master plan ghi quyết định nhóm đã chốt, nhưng repo thiếu giá trị/
artifact cụ thể. Không thực hiện hoặc đánh DONE P2-01 thay người dùng; ASSUMPTION
chỉ cho semantics bị ảnh hưởng. Không đổi status/owner/estimate các task khác.

AC P2-02: downstream có một bộ tên/signature/data/error/cursor/CAS cụ thể;
Phase1 signatures giữ nguyên; D0 chỉ docs/contract checks; text index dùng field
`content_plain`; không triển khai Mongo/UI/query/use-case hoặc áp migration.
Requirement trace: FR-03/06/07/11/13, FR-04/05 filtering, NFR-SEC-03, CST-03;
P2-AC01/04..14/16/17/19. DoD human review chưa được agent tự ký.

Validation thực tế: **143 tests passed, 29.30s, không skip**, core coverage **97%**;
Ruff check pass, 110 files already formatted. Contract declaration/link checks pass.
Đây là regression/contract documentation checks, không claim search/trash runtime
hay Phase2 CI đã chạy; xem review record để đối chiếu lệnh và kết quả.

Rollback: revert commit P2-02; giữ dữ liệu và code Phase1. Các task P2-03..18
giữ trạng thái như board trước, chưa được triển khai trong checkpoint này.

### Tech lead REQUEST_CHANGES follow-up

[Review source](review/NOTEAPP_P2_02_CONTRACT_FREEZE_REVIEW.md) tại `1df944c` có
CF-01..07; [fix/evidence matrix](../../testing/PHASE2_P2_02_REVIEW.md) ghi từng mục.
P2-02 chưa DONE/Accepted/Frozen: CF-01 thiếu concrete decision values/source và
CF-03 PR #5 đang base `feature/phase-2`, chưa có required CI cho fix HEAD.
Fix commit `6b53814` đã push lên nhánh feature. Đổi base PR qua connector bị
GitHub từ chối **403 Resource not accessible by integration**; owner cần sửa base
PR #5 thành `develop`, sau đó đối chiếu checks đúng published HEAD. Không tạo
PR trùng hoặc dùng CI cũ thay cho gate này; lỗi permission không phải CI failed.
ADR canonical trace giữ xác nhận người dùng "đã chốt" nhưng không tự MATCHED
những giá trị chưa biết. P2-12/AC14 vẫn yêu cầu W3 automatic text-only retention;
W4 chỉ là dependency cho blob cleanup. CF-04/07 giao design/test obligations cụ thể,
CF-05 sửa metadata, CF-06 tracked checks; không claim implementation task sau đã chạy.
