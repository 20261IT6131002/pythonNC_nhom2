# R1_PLAN_03_FR17_DRAFT_RECOVERY.md

## FR-17 — Encrypted Local Draft Recovery

**Project:** `20261IT6131002/pythonNC_nhom2`

**Target:** R1 / Release 0.2

**Priority:** P0 Reliability

**Recommended branch:** `feature/r1-03-draft-recovery`

**Dependency:** `feature/r1-02-secure-storage-foundation` phải merge trước

**Current develop baseline:** `60f608524aa79839e45d1e714c88493861f48ddd`

**Primary RTM:** TC-REC-001, TC-REC-002, TC-REC-003

**Related:** FR-01, FR-02, BR-09, BR-10, BR-14, NFR-REL-01, NFR-REL-02, NFR-SEC-04

---

# 1. Mục tiêu

FR-17 phải bảo đảm người dùng không mất nội dung đã được ghi thành công vào local draft khi:

- MongoDB unavailable.
- Save remote thất bại.
- App/process bị đóng đột ngột.
- Restart trước khi remote save hoàn tất.
- Remote note thay đổi trong lúc local draft tồn tại.

Luồng nghiệm thu chính:

```text
Edit
 ↓
encrypted local autosave
 ↓
Mongo unavailable / crash
 ↓
restart
 ↓
recover draft
 ↓
reconnect
 ↓
save without duplicate or silent overwrite
```

Invariant bắt buộc:

```text
NO plaintext draft on disk
NO phantom SAVED
NO silent stale overwrite
NO duplicate new note
NO deletion before remote ACK
NO Tk main-thread crypto/file/DB I/O
```

---

# 2. Căn cứ SRS / RTM

## TC-REC-001
Offline draft → terminate/restart → recover.

Expected:
- encrypted draft restored;
- không bị đánh dấu remote-saved giả.

## TC-REC-002
Reconnect khi remote version đã thay đổi.

Expected:
- conflict hiển thị;
- không xóa silent local draft;
- không overwrite remote.

## TC-REC-003
Keyring unavailable hoặc local ciphertext bị tamper.

Expected:
- fail closed;
- không plaintext fallback;
- không crash/leak traceback.

## BR/NFR liên quan
- BR-09: DB unavailable → encrypted local draft, không phantom SAVED.
- BR-10: versioned editing, không silent overwrite.
- BR-14: I/O chạy worker.
- NFR-REL-01: network cut/restore không crash, draft recoverable.
- NFR-REL-02: `client_operation_id`, version conflict, graceful shutdown.
- NFR-SEC-04: secure local storage hoặc fail closed.

---

# 3. Entry Gate

R1-02 hiện là dependency bắt buộc. Không copy crypto/keyring code sang FR-17 branch.

Sau khi R1-02 merge:

```bash
git checkout develop
git pull
git checkout -b feature/r1-03-draft-recovery
```

FR-17 reuse:

```text
ContentCipher
SecretStore
EncryptedEnvelope
AES-GCM adapter
native keyring adapter
security error mapping
```

---

# 4. Trạng thái code hiện tại

Đã có:
- `EditorState` với CLEAN/DIRTY/SAVING/SAVED/ERROR/CONFLICT.
- `revision`.
- `operation_id`.
- `EditorPresenter._saving_revision`.
- `CreateNote(client_operation_id)`.
- `UpdateNote(expected_version)`.
- CAS conflict.
- TaskRunner worker flow.

Chưa có:
- `DraftStore` implementation.
- `DraftRecovery` implementation.
- encrypted local draft.
- autosave debounce.
- draft key provisioning.
- restart recovery.
- reconnect workflow.
- local-only/offline state.
- recovery dialog.

Hiện hai file vẫn là scaffold:

```text
src/noteapp/application/services/draft_recovery.py
src/noteapp/application/ports/draft_store.py
```

---

# 5. Kiến trúc mục tiêu

```text
Tk Editor
   │
   ▼
EditorPresenter
   │
   ├── remote Save ─────> CreateNote / UpdateNote
   │
   └── draft event
          │
          ▼
   DraftAutosavePresenter
          │
          ▼
      TaskRunner
          │ worker
          ▼
 DraftRecoveryService
          │
          ▼
      DraftStore
          │
          ▼
EncryptedLocalDraftStore
      │           │
      ▼           ▼
ContentCipher   SecretStore
      │           │
      ▼           ▼
 AES-GCM       OS Keyring
```

Dependency direction phải giữ:

```text
Presentation -> Application -> Ports <- Infrastructure
```

Không cho:
- Tk import `keyring`.
- Tk import `cryptography`.
- Application import local filesystem adapter.
- Domain import recovery/application code.

---

# 6. Contract Freeze trước implementation

Tạo:

```text
docs/srs/r1/03_R1_DRAFT_RECOVERY_CONTRACT_FREEZE.md
docs/adr/ADR_R1_DRAFT_RECOVERY.md
```

Các quyết định cần freeze:

| ID | Decision |
|---|---|
| REC-D01 | mỗi draft có opaque `draft_id` |
| REC-D02 | new note phải persist `client_operation_id` |
| REC-D03 | existing note persist `note_id + base_version` |
| REC-D04 | draft persist `revision`; older revision không overwrite newer |
| REC-D05 | autosave debounce proposal 750 ms |
| REC-D06 | support nhiều draft identities, không global single JSON |
| REC-D07 | draft master key lấy từ OS keyring |
| REC-D08 | existing ciphertext + missing key → recovery unavailable, không regenerate |
| REC-D09 | keyring unavailable → fail closed |
| REC-D10 | chỉ delete draft sau remote ACK đúng revision |
| REC-D11 | remote save fail → retain draft |
| REC-D12 | stale remote version → conflict + retain local |
| REC-D13 | recovery là explicit user action |
| REC-D14 | giữ extension point cho future locked-note recovery |

---

# 7. LocalDraft DTO

Tạo:

```text
src/noteapp/application/dto/local_draft.py
```

Proposal:

```python
@dataclass(frozen=True)
class LocalDraft:
    draft_id: str
    note_id: str | None
    client_operation_id: str
    base_version: int
    revision: int
    title: str
    content: str
    priority: Priority
    category_id: str | None
    updated_at: datetime
    source_locked: bool = False
```

Sensitive payload được mã hóa toàn bộ khi persist.

Không persist image binary/reminder state trong draft V1.

---

# 8. Persisted format

Plain wrapper tối thiểu:

```text
format_version
draft_id
encrypted_envelope
```

Không để plaintext:
- title;
- content;
- category;
- priority;
- operation id;
- note id;
- base version;
- revision.

Dùng strict UTF-8 JSON.

Không dùng:
- pickle;
- marshal;
- eval.

Serializer reject:
- unknown version;
- duplicate/extra fields;
- invalid UUID;
- invalid priority;
- invalid timestamp;
- oversized payload;
- malformed envelope.

Proposal bound:

```text
1 MiB encrypted draft payload max
```

---

# 9. DraftStore port

Replace scaffold:

```python
class DraftStore(Protocol):
    def save_if_newer(self, draft: LocalDraft) -> bool: ...
    def get(self, draft_id: str) -> LocalDraft | None: ...
    def list_recoverable(self) -> tuple[DraftHeader, ...]: ...
    def delete(self, draft_id: str) -> None: ...
```

`DraftHeader` không chứa title/content.

Revision rules:

```text
no existing -> save
incoming > current -> replace
incoming == current -> idempotent
incoming < current -> ignore/reject
```

---

# 10. Draft master key

Không tạo policy key trong raw `SecretStore`.

Tạo `DraftKeyProvider`.

Flow:

```text
get("draft-master-key.v1")
 ↓ missing
generate 32 random bytes
 ↓
put
 ↓
readback verify
```

Không lưu key:
- cạnh draft;
- `.env`;
- config JSON;
- Mongo;
- log.

Nếu draft file tồn tại nhưng key missing:
- không generate key mới rồi giả rằng draft vô dụng;
- return recovery-unavailable;
- giữ ciphertext.

---

# 11. Key provisioning race

Nếu hai worker cùng thấy key missing:

```text
A -> KA
B -> KB
```

không được xảy ra:

```text
draft encrypted KA
keyring final KB
```

V1 desktop single-process:

```text
serialize provisioning bằng application-level lock
```

Cross-process concurrency nếu chưa support phải ghi limitation.

---

# 12. EncryptedLocalDraftStore

Tạo:

```text
src/noteapp/infrastructure/local/encrypted_draft_store.py
```

Dependencies:
- `ContentCipher`;
- `SecretStore`/DraftKeyProvider;
- path provider.

AAD proposal:

```text
noteapp:draft:v1:<draft_id>
```

AAD distinct với future locked-note context.

---

# 13. Atomic write

```text
serialize encrypted wrapper
 ↓
write temp cùng directory
 ↓
flush
 ↓
fsync best effort
 ↓
os.replace(final)
```

Không delete old file trước.

Failure trước replace:
- old good draft vẫn đọc được.

Filename:
```text
<opaque-draft-id>.draft
```

Không dùng title/note-id làm filename.

---

# 14. Autosave

Tách trách nhiệm:

```text
Presentation -> debounce scheduling
Application -> snapshot/save policy
Infrastructure -> file/keyring/crypto
```

Main thread tạo immutable snapshot.

Worker không đọc trực tiếp Tk widgets.

Proposal debounce:

```text
750 ms
```

nhưng test phải dùng fake scheduler/direct callback, không sleep thật.

---

# 15. Autosave revision race

Scenario:

```text
rev 5 submitted
rev 6 submitted
rev 6 completes
rev 5 completes late
```

Expected:

```text
stored revision remains 6
```

Correctness phải nằm ở `save_if_newer`, không phụ thuộc timing.

---

# 16. Sync state

Không nhồi local persistence vào `EditorPhase`.

Tạo:

```python
class SyncState(str, Enum):
    REMOTE = "REMOTE"
    LOCAL_PENDING = "LOCAL_PENDING"
    LOCAL_SAVED = "LOCAL_SAVED"
    OFFLINE = "OFFLINE"
    RECOVERY_AVAILABLE = "RECOVERY_AVAILABLE"
    SECURE_AUTOSAVE_DISABLED = "SECURE_AUTOSAVE_DISABLED"
```

Valid examples:

```text
phase=DIRTY,    sync=LOCAL_PENDING
phase=DIRTY,    sync=LOCAL_SAVED
phase=ERROR,    sync=LOCAL_SAVED
phase=CONFLICT, sync=LOCAL_SAVED
```

Không claim:

```text
phase=SAVED
```

nếu chỉ local draft thành công.

---

# 17. UI status

Proposal:

```text
Đang lưu nháp an toàn…
Đã lưu nháp cục bộ
Mất kết nối • Bản nháp đã được lưu an toàn trên máy
Không thể lưu nháp an toàn trên thiết bị này
```

Không dùng chữ “Đã lưu” cho local-only state nếu dễ bị hiểu là remote SAVED.

---

# 18. New note flow

```text
New
 ↓
operation_id generated once
 ↓
edit revision N
 ↓
encrypted local draft
 ↓
LOCAL_SAVED
 ↓
user Save
 ↓
CreateNote(same operation_id)
```

Success:
- remote ACK;
- nếu không có newer revision → delete draft;
- state REMOTE/SAVED.

Remote fail:
- retain draft;
- ERROR/OFFLINE;
- không phantom SAVED.

---

# 19. ACK-loss / duplicate protection

Scenario:

```text
Create reaches Mongo
Mongo commits
client misses ACK
app crashes
```

Restart:
- recover same `client_operation_id`;
- retry Create.

Expected:
- repository idempotency;
- exactly one logical note.

Đây là acceptance bắt buộc của FR-17 new-note recovery.

---

# 20. Existing note flow

```text
open version=7
edit
draft base_version=7
restart
```

Nếu remote vẫn v7:
- recover DIRTY;
- save expected_version=7.

Nếu remote v8:
- conflict;
- local draft retained;
- remote retained;
- no overwrite.

---

# 21. Draft deletion policy

Không delete khi:
- user click Save;
- task submitted;
- state SAVING.

Delete chỉ sau:
- remote ACK success;
- ACK covers saved revision;
- không có newer local revision.

Nếu user gõ tiếp trong lúc save:
- ACK của old revision không được xóa newer draft.

Reuse idea từ `_saving_revision`.

---

# 22. Recovery service

Replace:

```text
application/services/draft_recovery.py
```

Responsibilities:
- list recoverable drafts;
- decrypt selected draft;
- classify new/existing;
- compare remote version nếu available;
- return recovery decision model.

Không mutate Tk.

Decision model proposal:

```text
SAFE_NEW
SAFE_EXISTING
REMOTE_CONFLICT
REMOTE_UNAVAILABLE
CORRUPT
KEY_UNAVAILABLE
```

---

# 23. Startup refactor

Current bootstrap requires Mongo readiness early.

FR-17 cần:

```text
build UI shell
 ↓
probe local recovery
 ↓
probe Mongo asynchronously
 ↓
combine states
```

Mongo-down startup không được ngăn local recovery.

Không nhất thiết xây full connection manager trong task này.

Manual reconnect là đủ cho V1.

---

# 24. Recovery dialog

Tạo:

```text
presentation/tk/views/recovery_dialog.py
```

Safe:

```text
Phát hiện bản nháp chưa đồng bộ.

[Khôi phục]
[Bỏ qua]
[Xóa bản nháp]
```

Conflict:

```text
Bản trên máy chủ đã thay đổi.

[Khôi phục bản local để xem]
[Giữ lại để xử lý sau]
```

Không có overwrite-server trực tiếp không qua CAS.

---

# 25. Recover into editor

Recovered editor:

```text
note_id      = draft.note_id
title        = draft.title
content      = draft.content
priority     = draft.priority
category_id  = draft.category_id
version      = draft.base_version
revision     = draft.revision
operation_id = persisted operation id
phase        = DIRTY
sync         = LOCAL_SAVED
```

Không set SAVED.

---

# 26. Drift handling

## Category drift
Category có thể đã bị xóa remote.

Không crash.
Không silently rewrite draft trước khi user thấy.

## Trash drift
Remote note có thể đã bị trash.

Không auto-create duplicate note.

Giữ draft và báo remote-missing/conflict state.

## Pin drift
Draft không sở hữu pin state.
Current remote pin phải được preserve.

## Attachment/reminder drift
Draft V1 không sở hữu các metadata này.
Remote/current state phải được preserve.

---

# 27. Security failure cases

## Keyring unavailable
- secure autosave disabled;
- no plaintext file;
- existing ciphertext untouched.

## Key missing with existing draft
- recovery unavailable;
- no silent regeneration.

## Tampered ciphertext
- authentication failure;
- no partial plaintext;
- no crash.

## Malformed wrapper
Reject:
- bad JSON;
- duplicate fields;
- extra fields;
- invalid base64;
- oversized payload;
- unknown version.

---

# 28. Shutdown

Need explicit decision for pending autosave.

Proposal:
- nếu DIRTY và autosave pending, cố flush bounded secure draft write;
- không indefinite wait;
- no Tcl callback after window destroyed.

Kill-process guarantee chỉ là:

```text
recover latest successfully persisted encrypted draft
```

không hứa recover mọi keystroke.

---

# 29. Test matrix

## Unit
- LocalDraft validation.
- strict serializer.
- DraftKeyProvider.
- recovery classification.
- revision ordering.
- sync-state transitions.

## Contract
- FakeDraftStore + real EncryptedLocalDraftStore same semantics.
- architecture boundary.

## Integration
- real encrypted file.
- fake keyring + real AES-GCM.
- atomic replace.
- Mongo reconnect/conflict.
- ACK-loss idempotency.

## UI
- debounce.
- local-only status.
- recovery dialog.
- stale result.
- close-before-result.

## E2E
- real process restart.
- Mongo fixture.
- actual encrypted draft file.

---

# 30. Core tests

### REC-U01
Model validation.

### REC-U02
Vietnamese serializer roundtrip.

### REC-U03
Stored file không chứa plaintext marker.

### REC-U04
Older revision không overwrite newer.

### REC-U05
Master key provisioning.

### REC-U06
Keyring unavailable → no file fallback.

### REC-U07
Tamper → AuthenticationFailed.

### REC-I01
Atomic replacement keeps old good draft.

### REC-I02
New-note restart keeps operation id.

### REC-I03
Existing-note restart keeps base version.

### REC-I04
Remote ACK deletes matching draft.

### REC-I05
Remote failure retains draft.

### REC-I06
Conflict retains both local and remote.

### REC-I07
ACK-loss retry creates one logical note.

### REC-UI01
Rapid edits debounce to latest snapshot.

### REC-UI02
Local-only status is not remote SAVED.

### REC-UI03
Secure autosave unavailable warning.

### REC-UI04
Recovery dialog deterministic.

### REC-UI05
Stale worker result ignored.

### REC-UI06
Window close safe.

---

# 31. TC-REC-001 system scenario

```text
1. Launch.
2. Create note.
3. Type unique marker.
4. Wait local encrypted autosave ACK.
5. Stop Mongo.
6. Click Save.
7. Verify not remote SAVED.
8. Terminate app.
9. Restart with Mongo down.
10. Recovery prompt appears.
11. Recover exact content.
12. Inspect draft file: no plaintext marker.
13. Start Mongo.
14. Save.
15. Restart.
16. Exactly one note persisted.
17. Draft removed after ACK.
```

---

# 32. TC-REC-002 system scenario

```text
1. Open existing version N.
2. Edit and autosave.
3. External actor updates remote to N+1.
4. Restart/recover.
5. Save.
```

Expected:
- conflict;
- remote remains;
- local draft remains.

---

# 33. TC-REC-003 system scenario

A — keyring unavailable:
- edit;
- autosave;
- no plaintext file;
- clear warning.

B — tamper:
- encrypted draft;
- flip ciphertext byte;
- restart;
- auth fail;
- no content display;
- no crash.

---

# 34. Desktop E2E

Add at least:

```text
test_r1_draft_recovers_after_restart_and_reconnects_without_duplicate
```

Optional second:

```text
test_r1_draft_conflict_preserves_local_and_remote_versions
```

Nếu E2E set thay đổi, update cùng lúc:
- `scripts/verify_desktop_e2e.py`
- `tests/contract/test_desktop_ci_report.py`

Giữ dynamic `len(EXPECTED_SCENARIOS)`.

---

# 35. File impact matrix

| Layer | Module | Change |
|---|---|---|
| DTO | `application/dto/local_draft.py` | new |
| Port | `application/ports/draft_store.py` | replace scaffold |
| Service | `application/services/draft_recovery.py` | replace scaffold |
| Service | `application/services/draft_autosave.py` | new |
| Security | R1-02 ports/adapters | reuse |
| Local infra | `infrastructure/local/encrypted_draft_store.py` | new |
| Local infra | path provider | new |
| Presentation | `state/sync_state.py` | new |
| Presentation | `editor_state.py` | integrate sync |
| Presentation | `editor_presenter.py` | autosave/recovery hooks |
| Presentation | `draft_presenter.py` | new |
| View | `recovery_dialog.py` | new |
| View | `app_window.py` | status/wiring |
| Bootstrap | `bootstrap.py` | local recovery independent from Mongo |
| Tests | unit/contract/integration/UI/E2E | FR-17 evidence |
| Docs | contract/ADR/RTM/report | release evidence |

---

# 36. Implementation slices

## R1-03.0 — Contract Freeze
Deliver:
- `03_R1_DRAFT_RECOVERY_CONTRACT_FREEZE.md`
- `ADR_R1_DRAFT_RECOVERY.md`

Exit:
- REC-D01..D14 reviewed.

## R1-03.1 — Model + serializer
Implement:
- `LocalDraft`;
- `DraftHeader`;
- strict payload serializer.

## R1-03.2 — DraftStore + key policy
Implement:
- DraftStore;
- FakeDraftStore;
- DraftKeyProvider;
- save-if-newer semantics.

## R1-03.3 — Encrypted local store
Implement:
- AES-GCM reuse;
- OS keyring reuse;
- atomic write;
- tamper/malformed handling.

## R1-03.4 — Autosave integration
Implement:
- debounce;
- immutable snapshot;
- TaskRunner;
- SyncState;
- stale-result protection.

## R1-03.5 — Restart recovery
Implement:
- discover;
- decrypt;
- recovery dialog;
- recover to DIRTY editor;
- Mongo-down startup.

## R1-03.6 — Reconnect/conflict
Implement:
- new note same operation id;
- existing note base-version CAS;
- ACK deletion;
- failure retain;
- conflict retain.

## R1-03.7 — E2E/RTM
Run:
- TC-REC-001;
- TC-REC-002;
- TC-REC-003.

Update:
- README;
- RTM;
- test report;
- CI verifier.

---

# 37. Commit sequence

```text
docs(recovery): freeze FR-17 recovery contract
test(recovery): add LocalDraft and DraftStore contracts
feat(recovery): add local draft model and strict serializer
feat(recovery): add draft key provisioning policy
feat(recovery): add encrypted atomic local draft store
feat(recovery): autosave editor drafts asynchronously
feat(recovery): restore drafts across restart
feat(recovery): add reconnect and conflict handling
test(recovery): add fault injection and desktop E2E
docs(recovery): record RTM and validation evidence
```

---

# 38. PR

Suggested title:

```text
feat(r1): add encrypted local draft recovery
```

PR body must include:
- FR-17;
- TC-REC-001/002/003;
- dependency on R1-02;
- encrypted local storage;
- OS keyring;
- operation-id persistence;
- version conflict;
- atomic writes;
- no plaintext fallback;
- tamper evidence;
- restart E2E;
- remote CI.

---

# 39. PR Entry Gate

- [ ] R1-02 merged.
- [ ] contract freeze committed.
- [ ] DraftStore contract pass.
- [ ] plaintext absence test pass.
- [ ] keyring unavailable test pass.
- [ ] tamper test pass.
- [ ] restart recovery pass.
- [ ] conflict keeps local draft.
- [ ] ACK-loss duplicate protection pass.
- [ ] no known P0/P1 bug.

---

# 40. PR Exit Gate

Remote:
```text
quality 3.10 PASS
quality 3.12 PASS
windows-ui PASS
integration PASS
```

Also:
- desktop E2E PASS;
- RTM updated;
- reviewer approval.

---

# 41. Definition of Done

FR-17 DONE only when:

- [ ] DraftStore scaffold replaced.
- [ ] DraftRecovery scaffold replaced.
- [ ] encrypted local file implemented.
- [ ] R1-02 AES-GCM reused, not duplicated.
- [ ] R1-02 SecretStore reused.
- [ ] master key safely provisioned.
- [ ] existing ciphertext + missing key does not silently regenerate.
- [ ] no plaintext fallback.
- [ ] no title/content plaintext in draft file.
- [ ] autosave non-blocking.
- [ ] revisions monotonic.
- [ ] older worker cannot overwrite newer draft.
- [ ] crash keeps last good draft.
- [ ] restart discovers recovery.
- [ ] recovery explicit.
- [ ] recovered note is DIRTY, not SAVED.
- [ ] operation id survives restart.
- [ ] base version survives restart.
- [ ] remote ACK required before draft deletion.
- [ ] remote save fail retains draft.
- [ ] conflict retains local draft.
- [ ] ACK-loss retry does not duplicate.
- [ ] Mongo-down startup still allows recovery.
- [ ] keyring unavailable warning exists.
- [ ] tamper → auth fail.
- [ ] no plaintext in log/traceback.
- [ ] TC-REC-001 PASS.
- [ ] TC-REC-002 PASS.
- [ ] TC-REC-003 PASS.
- [ ] restart E2E PASS.
- [ ] full remote CI green.
- [ ] RTM/report updated.

---

# 42. Non-goals

Không đưa vào FR-17:
- FR-14 Locked Note.
- KDF/passphrase.
- Mongo encrypted content.
- FR-15 Export.
- FR-16 Statistics.
- cloud sync.
- multi-device recovery.
- cross-device key sync.
- attachment binary recovery.
- password recovery.
- background daemon.

---

# 43. Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Phantom remote save | P0 | LOCAL_SAVED != SAVED |
| Older autosave overwrites newer | P0 | revision CAS/save_if_newer |
| Plaintext fallback | P0 | fail closed |
| Silent stale overwrite | P0 | base-version CAS |
| Lost existing draft key | P0 | no silent regeneration |
| Mongo blocks startup | P1 | local recovery independent from DB readiness |
| Duplicate new note | P1 | persist client_operation_id |
| Future FR-14 rework | P1 | source_locked/save-strategy extension point |

---

# 44. Demo Acceptance

Reliability demo:

```text
edit
→ encrypted autosave
→ Mongo down
→ save fails remote
→ crash
→ restart
→ recover
→ Mongo up
→ save
→ restart
→ exactly one note
```

Conflict demo:

```text
edit existing vN
→ local draft
→ remote becomes vN+1
→ recover
→ save
→ CONFLICT
→ remote preserved
→ local preserved
```

Security demo:

```text
encrypted draft
→ tamper
→ restart
→ auth fail
→ no plaintext
→ no crash
```

---

# 45. Immediate next action

```text
1. Finish R1-02 cleanup.
2. Open/merge R1-02 into develop.
3. Pull develop.
4. Create feature/r1-03-draft-recovery.
5. Commit Contract Freeze first.
6. Implement LocalDraft + DraftStore contracts before UI.
```

Không bắt đầu bằng recovery dialog.

Bắt đầu bằng:

```text
data contract
revision semantics
key lifecycle
storage contract
```

vì đây là nơi quyết định correctness của toàn FR-17.
