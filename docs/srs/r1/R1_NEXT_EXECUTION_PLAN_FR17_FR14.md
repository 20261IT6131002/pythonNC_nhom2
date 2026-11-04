# R1_NEXT_EXECUTION_PLAN_FR17_FR14.md

## Kế hoạch thực thi tiếp theo — Secure Storage Foundation → FR-17 Draft Recovery → FR-14 Locked Notes

**Project:** `20261IT6131002/pythonNC_nhom2`

**Baseline:** `develop` sau PR #15 (FR-12 Pin)

**Baseline merge commit:** `60f608524aa79839e45d1e714c88493861f48ddd`

**Target:** R1 / Release 0.2

**Ưu tiên:** FR-17 P0 trước, FR-14 P1 sau

**RTM chính:** TC-REC-001/002/003, TC-SEC-001/002/003/004

```text
develop @ 60f6085
      │
      ├── R1-02 Secure Storage Foundation
      │       ↓
      ├── R1-03 FR-17 Encrypted Local Draft Recovery
      │       ↓
      ├── R1-04 FR-14 Locked Notes
      │       ↓
      └── R1-05 Security / Reliability Hardening + R1 release gate
```

---

# 1. Mục tiêu

Tài liệu này là **execution plan**, không phải báo cáo hoàn thành.

Mục tiêu:
- Triển khai FR-17 trước vì SRS xếp P0 reliability.
- Dựng một secure-storage boundary nhỏ dùng chung trước FR-17 và FR-14.
- Không viết crypto trực tiếp trong Tkinter/presenter/domain.
- Không lưu local draft plaintext nếu keyring unavailable.
- Không để locked content xuất hiện trong Mongo text index, log, notification hoặc temp/cache không mã hóa.
- Giữ optimistic concurrency/version hiện tại.
- Không phá FR-08 Image, FR-09/10 Reminder, FR-12 Pin, FR-13 Trash.


# 2. Yêu cầu trực tiếp từ SRS

## FR-17 — Recovery bản nháp

SRS yêu cầu:
- **AC-17a:** mất Mongo hoặc app đóng đột ngột → restart vẫn khôi phục draft gần nhất đã ghi local thành công.
- **AC-17b:** local draft luôn mã hóa at-rest bằng khóa OS keyring/credential store; nếu keyring không khả dụng phải báo rõ secure autosave bị vô hiệu hóa và **không silently ghi plaintext**.
- **AC-17c:** reconnect phải có user-confirmed save, chống duplicate bằng `client_operation_id`, và không mất bản local khi server save fail.

## FR-14 — Ghi chú khóa

SRS yêu cầu:
- AES-256-GCM.
- Salt/nonce/KDF params lưu kèm.
- Không lưu plaintext content khi locked.
- Sai passphrase không decrypt.
- Tampering → authenticated decryption fail, không crash.
- Đổi passphrase → re-encrypt.
- Không log content/key/PIN.
- Encrypted content không nằm trong Mongo `$text` index.
- Notification không leak locked content.

## BR/NFR liên quan

- BR-09: DB unavailable → encrypted local draft; không tự claim `SAVED`.
- BR-10: versioned editing; không silent stale overwrite.
- BR-12: locked note không ghi plaintext vào log/search/temp cache không mã hóa.
- BR-14: I/O chạy worker; safe nếu window bị destroy trước khi result về.
- NFR-SEC-02: AES-256-GCM, salt 16-byte random, nonce 12-byte unique, KDF params + version metadata.
- NFR-SEC-04: local draft encryption hoặc fail-closed.
- NFR-REL-01: retry/backoff rồi Offline; không phantom save.
- NFR-REL-02: `client_operation_id`, version conflict, graceful termination.


# 3. Những gì SRS chưa chốt

Phải coi là **implementation proposal / decision pending**, không tự coi là requirement:
- Python crypto package.
- Python keyring package.
- KDF algorithm cụ thể.
- KDF cost parameters.
- autosave debounce.
- local draft directory/file format.
- title của locked note có mã hóa hay không.
- title search policy.
- unlock session duration.
- remove-lock behavior.
- password strength policy.
- nhiều local drafts cho cùng note.
- draft retention policy.

Các mục trên phải được đưa vào Contract Freeze / Decision Log.


# 4. Trạng thái code hiện tại

## Đã có
- Immutable `Note`.
- `version` CAS.
- `client_operation_id` cho create.
- `EditorState` với DIRTY/SAVING/SAVED/ERROR/CONFLICT.
- Dirty edits được giữ trong lúc I/O.
- TaskRunner / result-error envelope.
- Mongo `content_plain`.
- Pin metadata CAS.
- Image / reminder / trash integration.

## Chưa có
- `application/services/draft_recovery.py` mới chỉ là scaffold.
- `application/ports/draft_store.py` mới chỉ là scaffold.
- `EditorState` hiện còn ghi rõ không persist draft xuống disk.
- `pyproject.toml` chưa có dependency crypto/keyring chuyên dụng.
- `Note` / `NoteView` giả định content luôn plaintext.

=> FR-17 chưa có implementation và FR-14 chưa thể chỉ thêm một nút Lock.


# 5. Kiến trúc tổng thể

```text
                ┌──────────────────────────┐
                │ R1-02 Secure Foundation │
                │ AEAD boundary            │
                │ SecretStore boundary     │
                │ encrypted envelope       │
                └────────────┬─────────────┘
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
  FR-17 Local Draft                FR-14 Locked Content

 key source: OS keyring            key source: passphrase + KDF
 storage: encrypted local file     storage: Mongo encrypted payload
```

Dùng chung:
- AES-256-GCM primitive.
- nonce generation.
- envelope versioning.
- AAD policy.
- tamper handling.
- secret-safe logging.

Không dùng chung cách quản lý khóa:
- FR-17: key từ OS keyring.
- FR-14: key derive từ passphrase + KDF.


# 6. Branch / PR sequence

## R1-02
`feature/r1-02-secure-storage-foundation`

Scope:
- crypto/keyring boundary;
- error model;
- contract tests;
- chưa autosave;
- chưa locked-note UI.

## R1-03
`feature/r1-03-draft-recovery`

Base: develop sau khi R1-02 merge.

Scope:
- FR-17 end-to-end.

## R1-04
`feature/r1-04-locked-notes`

Base: develop sau khi R1-03 merge.

Scope:
- FR-14 end-to-end.

Không khuyến nghị gộp tất cả vào một `feature/r1-security-all`.


# 7. R1-02 — Secure Storage Foundation

## 7.1 Contract Freeze

Tạo:
- `docs/srs/r1/02_R1_SECURE_STORAGE_CONTRACT_FREEZE.md`
- `docs/adr/ADR_R1_SECURE_STORAGE.md`

Quyết định:
- SEC-D01: AES-256-GCM là algorithm bắt buộc.
- SEC-D02: nonce 12-byte unique mỗi encryption.
- SEC-D03: salt 16-byte random cho locked-note KDF.
- SEC-D04: KDF là abstraction; algorithm cụ thể freeze trước FR-14.
- SEC-D05: FR-17 secret source = OS keyring / credential store.
- SEC-D06: keyring unavailable → fail closed, không plaintext fallback.
- SEC-D07: application error không leak secret.

## 7.2 Port đề xuất

`application/ports/content_cipher.py`

```python
class ContentCipher(Protocol):
    def encrypt(self, plaintext: bytes, key: bytes, aad: bytes) -> EncryptedEnvelope: ...
    def decrypt(self, envelope: EncryptedEnvelope, key: bytes, aad: bytes) -> bytes: ...
```

`application/ports/secret_store.py`

```python
class SecretStore(Protocol):
    def get(self, name: str) -> bytes | None: ...
    def put(self, name: str, secret: bytes) -> None: ...
    def delete(self, name: str) -> None: ...
```

## 7.3 Envelope

Fields tối thiểu:
- `format_version`
- `algorithm`
- `nonce`
- `ciphertext`

FR-14 mở rộng:
- `kdf_algorithm`
- `kdf_params`
- `salt`

Secret-bearing bytes phải `repr=False` nếu dùng dataclass.

## 7.4 Infrastructure

Đề xuất:
```text
infrastructure/security/
    aes_gcm.py
    secret_store.py
    serializers.py
```

Không để domain/presenter import crypto/keyring package.

## 7.5 Dependency review

Trước implementation:
1. Chọn maintained AES-GCM library.
2. Chọn maintained cross-platform keyring library.
3. Xác minh Python 3.10/3.12.
4. Xác minh Windows CI.
5. Xác minh packaging.
6. Pin dependency range.
7. Ghi rationale trong ADR.

Không ghi version giả trong plan.

## 7.6 Tests

- SEC-U01 encrypt/decrypt roundtrip.
- SEC-U02 same plaintext + fresh nonce → ciphertext khác.
- SEC-U03 tamper ciphertext → auth fail.
- SEC-U04 wrong key → auth fail.
- SEC-U05 invalid nonce → validation fail.
- SEC-U06 invalid key length → validation fail.
- SEC-U07 AAD mismatch → auth fail.
- SEC-K01 fake keyring get/put.
- SEC-K02 backend unavailable → normalized error.
- SEC-K03 không tạo plaintext fallback.

## 7.7 Exit gate

- AES-256-GCM covered.
- tamper/wrong-key tests pass.
- SecretStore port exists.
- keyring errors normalized.
- no domain crypto import.
- no presenter crypto import.
- no secret in repr/log.
- Python 3.10/3.12 PASS.
- Windows CI unaffected.
- ADR approved.


# 8. R1-03 — FR-17 Encrypted Local Draft Recovery

## 8.1 LocalDraft model

SRS model:
- `note_id` hoặc `draft_id`
- `revision/base_version`
- encrypted payload
- `updated_at`
- sync/recovery state
- local-only

Đề xuất `application/dto/local_draft.py`:

```text
draft_id
note_id | None
client_operation_id
base_version
revision
updated_at
state
encrypted_payload
```

## 8.2 Sensitive payload

Payload mã hóa chứa ít nhất:
- title
- content
- priority
- category_id
- client_operation_id
- note_id
- base_version
- revision

Không cần recovery image-picker state ở task đầu nếu SRS không yêu cầu.

## 8.3 Plain metadata tối thiểu

Đề xuất file chỉ để plaintext:
- format version
- opaque draft id
- updated time
- crypto metadata
- nonce
- ciphertext

Không lưu title/content plaintext trong file.

## 8.4 DraftStore

Replace scaffold:

```python
class DraftStore(Protocol):
    def save(self, draft: LocalDraft) -> None: ...
    def load_latest(self) -> LocalDraft | None: ...
    def list_recoverable(self) -> tuple[LocalDraft, ...]: ...
    def delete(self, draft_id: str) -> None: ...
```

## 8.5 EncryptedLocalDraftStore

`infrastructure/local/encrypted_draft_store.py`

Flow:
```text
payload
 ↓ serialize UTF-8
 ↓ obtain app draft key from SecretStore
 ↓ AES-GCM encrypt
 ↓ write temp
 ↓ flush/fsync where supported
 ↓ atomic replace
```

Không write trực tiếp vào final file.

## 8.6 Draft master key

First secure autosave:
```text
lookup keyring
 ↓ missing
generate 32 random bytes
 ↓
store OS keyring
```

Không store key:
- cạnh draft file;
- `.env`;
- config JSON;
- Mongo;
- log.

## 8.7 AAD

Proposal:
```text
app-id + envelope-version + draft-id
```

AAD mismatch phải fail authentication.

## 8.8 Autosave

SRS chưa chốt debounce.

Proposal:
```text
Editor change
 ↓ debounce
TaskRunner worker
 ↓ encrypted local save
```

Candidate range: 500–1500ms, chỉ freeze sau UI/performance test.

Crypto/file I/O không chạy trên Tk main thread.


# 9. FR-17 State model

Không nên nhồi mọi persistence state vào `EditorPhase`.

Đề xuất thêm:

```python
class SyncState(Enum):
    REMOTE = "REMOTE"
    LOCAL_ONLY = "LOCAL_ONLY"
    OFFLINE = "OFFLINE"
    RECOVERY_AVAILABLE = "RECOVERY_AVAILABLE"
    SECURE_AUTOSAVE_DISABLED = "SECURE_AUTOSAVE_DISABLED"
```

Ví dụ hợp lệ:
```text
phase=DIRTY
sync=LOCAL_ONLY
```

SRS UI contract cần label dirty/saving/saved/local-only/conflict.


# 10. FR-17 Main flows

## New note

```text
New
 ↓ edit
DIRTY
 ↓ encrypted draft
LOCAL_ONLY
 ↓ user Save
CreateNote(client_operation_id)
 ↓ Mongo ACK
delete acknowledged draft
 ↓
REMOTE / SAVED
```

Mongo unavailable:
```text
Save fails
 ↓
không claim SAVED
 ↓
LOCAL_ONLY / OFFLINE
 ↓
retain draft
```

Restart:
```text
DraftRecoveryService
 ↓ decrypt
 ↓ recovery UI
 ↓ Recover
Editor restored
```

## Existing note

```text
open version=7
 ↓ edit revision=3
 ↓ encrypted draft(base_version=7)
 ↓ crash
 ↓ restart
```

Nếu remote vẫn v7:
- restore draft DIRTY;
- save bằng expected_version=7.

Nếu remote >7:
- CONFLICT;
- không overwrite;
- không xóa draft local.

## New-note idempotency

`client_operation_id` phải persist trong draft và được reuse sau restart.

Nếu request đã tới Mongo nhưng ACK bị mất:
- retry cùng operation id;
- không tạo duplicate.

## Draft deletion

Không xóa khi user vừa click Save.

Chỉ delete khi:
- remote ACK thành công;
- ACK cover đúng revision snapshot;
- không có newer local revision.

Remote save fail → retain draft.


# 11. FR-17 Failure handling

## Keyring unavailable

Required:
- secure autosave disabled;
- no plaintext file;
- UI warning rõ.

Message đề xuất:
> Không thể bật lưu nháp an toàn trên thiết bị này. Nội dung chưa được ghi xuống ổ đĩa.

## Corrupt/tampered draft

Cases:
- invalid envelope;
- unknown format;
- bad nonce;
- tampered ciphertext;
- wrong/missing key.

Expected:
- không render partial plaintext;
- không crash;
- không log payload;
- giữ file để xử lý/discard có chủ đích.

## Atomic write

```text
temp file
 ↓ write
 ↓ flush
 ↓ fsync best effort
 ↓ os.replace(final)
```

Write failure không được phá old good draft.


# 12. FR-17 Startup / Recovery UI

Mongo ping fail không được ngăn app nhìn thấy recoverable local draft.

Nên tách:
```text
startup shell
 ├── local secure-storage probe
 └── Mongo probe async
```

Recovery UI đề xuất:
```text
Phát hiện bản nháp chưa đồng bộ

[Khôi phục] [Bỏ qua] [Xóa bản nháp]
```

Conflict:
```text
Bản trên máy chủ đã thay đổi từ khi bản nháp này được tạo.

[Khôi phục thành bản đang sửa]
[Giữ bản nháp để xử lý sau]
```

Không có overwrite server trực tiếp không qua CAS.


# 13. FR-17 Modules

## New
```text
application/dto/local_draft.py
application/services/draft_recovery.py
application/services/draft_autosave.py
application/ports/draft_store.py
application/ports/secret_store.py
application/ports/content_cipher.py

infrastructure/local/encrypted_draft_store.py
infrastructure/security/aes_gcm.py
infrastructure/security/keyring_store.py

presentation/tk/presenters/draft_presenter.py
presentation/tk/state/sync_state.py
presentation/tk/views/recovery_dialog.py
```

## Existing affected
```text
EditorState
EditorPresenter
AppWindow
bootstrap
CreateNote
UpdateNote
Config
TaskRunner
shutdown flow
README
RTM
CI
```


# 14. FR-17 Tests

## RTM
- TC-REC-001: offline draft → terminate/restart → encrypted recovery; không remote-saved giả.
- TC-REC-002: remote version đổi → conflict; không mất local copy.
- TC-REC-003: keyring unavailable hoặc ciphertext tampered → fail closed.

## Additional
- REC-U01 serialization roundtrip.
- REC-U02 plaintext bytes không xuất hiện trong stored draft.
- REC-U03 operation id sống qua restart.
- REC-U04 stale autosave completion không overwrite newer revision.
- REC-U05 close window trước worker result không gọi Tcl widget đã destroy.
- REC-I01 atomic replacement giữ old good draft khi write fail.
- REC-I02 successful remote save chỉ xóa acknowledged revision.
- REC-I03 remote save fail giữ draft.
- REC-I04 restart idempotent.
- REC-E2E01 edit → kill → restart → recover → save → restart.

Nếu thêm desktop E2E:
- update `scripts/verify_desktop_e2e.py`;
- update `tests/contract/test_desktop_ci_report.py`;
- verifier dùng `len(EXPECTED_SCENARIOS)`, không hard-code số bằng chữ.


# 15. FR-17 Definition of Done

- DraftStore scaffold được thay bằng contract thật.
- DraftRecovery scaffold được implement.
- Draft encrypted at rest.
- Production key chỉ qua SecretStore.
- Không plaintext fallback.
- Keyring unavailable được báo rõ.
- New-note operation id sống qua restart.
- Existing-note base version sống qua restart.
- Local revision tracked.
- Remote ACK mới được xóa draft.
- Remote save fail giữ draft.
- Stale remote version → conflict.
- Restart recovery UI có thật.
- Main thread không làm file/crypto I/O.
- Không plaintext trong log.
- TC-REC-001/002/003 PASS.
- Restart E2E PASS.
- quality 3.10/3.12 PASS.
- windows-ui PASS.
- integration PASS.
- RTM + README cập nhật.


# 16. R1-04 — FR-14 Locked Notes

## 16.1 Contract Freeze

Tạo:
- `docs/srs/r1/04_R1_LOCKED_NOTE_CONTRACT_FREEZE.md`
- `docs/adr/ADR_R1_LOCKED_CONTENT.md`

Decisions bắt buộc:
- LOCK-D01 KDF algorithm.
- LOCK-D02 KDF parameters.
- LOCK-D03 passphrase policy.
- LOCK-D04 title privacy.
- LOCK-D05 title search.
- LOCK-D06 unlock session duration.
- LOCK-D07 remove-lock behavior.
- LOCK-D08 lock + trash.
- LOCK-D09 lock + export future behavior.
- LOCK-D10 notification title policy.
- LOCK-D11 locked preview.
- LOCK-D12 locked update commands.
- LOCK-D13 schema compatibility.
- LOCK-D14 key lifecycle.

Không code UI final trước LOCK-D04/05/10.


# 17. FR-14 Mongo schema

Target theo SRS:
```text
content_plain OR content_encrypted
```

Locked document proposal:
```text
{
  ...
  "is_locked": true,
  "content_encrypted": {
    "format_version": 1,
    "algorithm": "AES-256-GCM",
    "ciphertext": <bytes>,
    "nonce": <12 bytes>,
    "salt": <16 bytes>,
    "kdf": {
      "name": "...",
      "params": {...}
    }
  }
}
```

Locked doc phải:
```text
content_plain ABSENT
```

Không dùng:
```text
content_plain = ""
```
nếu acceptance cần chứng minh không lưu plaintext.

Unlocked:
```text
is_locked=false
content_plain="..."
content_encrypted absent
```


# 18. FR-14 KDF

SRS chỉ yêu cầu:
- salt 16-byte random;
- KDF params stored.

Algorithm chưa chốt.

Port đề xuất:

```python
class PassphraseKdf(Protocol):
    def derive(self, passphrase: str, salt: bytes, params: KdfParams) -> bytes: ...
```

Output 32 bytes cho AES-256.

Không persist:
- passphrase;
- derived key.


# 19. FR-14 Lock / Unlock

## Lock

```text
LockNote(note_id, expected_version, passphrase)
 ↓
load active unlocked note
 ↓ version check
 ↓ fresh salt 16
 ↓ fresh nonce 12
 ↓ derive key
 ↓ encrypt UTF-8 content
 ↓ Mongo CAS:
      set content_encrypted
      set is_locked=true
      unset content_plain
      inc version
 ↓
safe locked view
```

## Unlock for session

Unlock không mặc định đồng nghĩa remove lock.

```text
passphrase
 ↓ derive
 ↓ authenticate/decrypt
 ↓ plaintext chỉ trong trusted editor memory
```

Mongo vẫn encrypted.

## Wrong passphrase / tamper

Return generic authentication/integrity failure:
- không partial plaintext;
- không crash;
- không persist gì;
- không raw traceback ra UI.


# 20. Change passphrase

```text
old passphrase
 ↓ authenticate/decrypt
 ↓ fresh salt
 ↓ derive new key
 ↓ fresh nonce
 ↓ re-encrypt
 ↓ CAS expected_version
```

Bắt buộc fresh salt + nonce.

Không reuse old envelope.


# 21. Critical: Save locked note

Không cho unlocked editor của locked note gọi normal `UpdateNote` rồi ghi `content_plain`.

Khuyến nghị use case riêng:
```text
UpdateLockedNote
```

Flow:
```text
plaintext in memory
 ↓ encrypt
 ↓ CAS update content_encrypted
 ↓ content_plain vẫn absent
```

Defense in depth:
- normal `UpdateNote`/repository plaintext update phải guard `is_locked != true`.

Nếu UI bug gọi nhầm:
- DB guard vẫn phải ngăn plaintext downgrade.


# 22. Read-model refactor

Current `Note` / `NoteView` giả định plaintext content.

Không nên bắt mọi locked document đi qua constructor cần plaintext.

Khuyến nghị tách:
```text
List/Search -> NoteSummaryView
Editor detail -> UnlockedNoteView | LockedNoteView
```

`NoteSummaryView`:
- note_id
- safe title
- priority
- category
- version
- timestamps
- attachment/reminder metadata theo policy
- is_pinned
- is_locked
- content_preview | None

Locked:
```text
content_preview = None / "Đã khóa"
```

List không decrypt.


# 23. Search / Notification / Logs

## Search
Index hiện có:
```text
title + content_plain
```

Khi lock:
```text
unset content_plain
```

=> locked content tự bị loại khỏi content text search.

Title behavior phụ thuộc LOCK-D05.

Test:
```text
secret token chỉ nằm trong locked content
search token
=> không match từ content
```

## Notification
Tuyệt đối không content.

Nếu title sensitive theo decision:
```text
"Bạn có một ghi chú đã đến hạn."
```

## Logs
Không log:
- passphrase;
- key;
- plaintext locked content;
- plaintext draft payload.

Secret-bearing dataclass field nên `repr=False`, nhưng không coi đó là lớp bảo vệ duy nhất.


# 24. Cross-feature integration FR-14

## Pin
Pin metadata-only:
- không decrypt;
- không rewrite encrypted payload.

Test:
```text
locked note
pin/unpin
ciphertext byte-for-byte unchanged
```

## Reminder
Set/cancel reminder phải giữ encrypted payload.

## Trash
Trash/restore giữ locked state.
Purge phải support `is_locked` / `content_encrypted` trong whitelist.

## Image
FR-14 source requirement nói về content, không tự suy ra ảnh được encrypt.
Nếu ảnh vẫn plaintext/GridFS:
- ghi limitation rõ;
- không claim lock bảo vệ attachment.

## Draft Recovery
Locked note đã unlock + edit + Mongo down:
- local autosave vẫn dùng OS-keyring draft encryption;
- reconnect không được gọi plaintext UpdateNote;
- phải route qua locked-save flow.


# 25. FR-14 Tests

## RTM
- TC-SEC-001: lock/unlock correct passphrase; Mongo ciphertext at rest.
- TC-SEC-002: wrong passphrase/tampered tag → auth fail.
- TC-SEC-003: log/search/notification/temp không leak locked content.
- TC-SEC-004: same plaintext re-encrypt → fresh salt/nonce, ciphertext khác, decrypt đúng.

## Additional
- LOCK-U01 envelope validation.
- LOCK-U02 unknown format rejected.
- LOCK-U03 malformed KDF params rejected.
- LOCK-U04 normal UpdateNote không plaintext-write locked doc.
- LOCK-I01 Pin preserves ciphertext.
- LOCK-I02 Reminder preserves ciphertext.
- LOCK-I03 Trash/restore preserves locked state.
- LOCK-I04 Purge locked note succeeds.
- LOCK-I05 Search excludes encrypted content.
- LOCK-E2E01 create → lock → restart → wrong pass fail → correct pass → edit/save → restart → verify.


# 26. FR-14 Definition of Done

- AES-256-GCM through approved adapter.
- 16-byte salt.
- 12-byte unique nonce.
- KDF choice/params frozen and stored.
- plaintext content absent from locked Mongo docs.
- wrong passphrase fails closed.
- tamper fails auth.
- change passphrase re-encrypts.
- fresh salt/nonce on re-encrypt.
- passphrase/derived key never persisted.
- locked content absent from text search.
- notification content generic.
- title privacy follows approved policy.
- normal update không downgrade locked note to plaintext.
- Pin/Reminder metadata operations preserve ciphertext.
- Trash/restore preserve locked state.
- Purge works.
- Draft-recovery integration safe.
- TC-SEC-001..004 PASS.
- remote CI full green.
- RTM/security report updated.


# 27. R1-05 Hardening

Không thêm feature mới.

Focus:
- failure injection;
- security audit;
- regression;
- packaging;
- backup/restore evidence.

Failure matrix:

| Failure | Expected |
|---|---|
| Mongo down while DIRTY | encrypted local draft retained |
| Mongo returns after restart | user-controlled reconnect save |
| Keyring unavailable | no plaintext |
| Draft tampered | auth fail |
| Draft key missing | recovery unavailable, no plaintext |
| Wrong locked passphrase | unlock fail |
| Locked ciphertext tampered | auth fail |
| Close while draft write pending | safe close / old good draft retained |
| Close while remote save pending | no phantom SAVED |
| Remote version changed | conflict |
| Pin locked note | metadata CAS only |
| Reminder locked note | encrypted content unchanged |
| Trash locked note | encrypted state preserved |


# 28. Regression matrix

Phải rerun:
```text
FR-01 Create
FR-02 Edit
FR-03 Delete
FR-04 Category
FR-05 Priority
FR-06 Search
FR-07 Date
FR-08 Image
FR-09 Reminder config
FR-10 Reminder delivery
FR-11 Sort
FR-12 Pin
FR-13 Trash
FR-17 Recovery
FR-14 Lock
```

Đặc biệt:
```text
Pin + Locked
Trash + Locked
Reminder + Locked
Recovery + Locked
Search + Locked
```


# 29. Evidence

Tạo:
```text
docs/testing/R1_SECURE_STORAGE_TEST_REPORT.md
docs/testing/R1_DRAFT_RECOVERY_TEST_REPORT.md
docs/testing/R1_LOCKED_NOTES_TEST_REPORT.md
```

Mỗi report phải có:
- commit SHA;
- OS;
- Python;
- Mongo;
- commands;
- pass/fail counts;
- CI links;
- known limitations.

Không fabricated measurement.


# 30. Suggested commit sequence

## R1-02
```text
docs(sec): freeze secure storage boundary
test(sec): add AEAD and secret-store contracts
feat(sec): add authenticated encryption boundary
feat(sec): add OS secret-store adapter
test(sec): add tamper and unavailable-keyring coverage
docs(sec): record secure foundation evidence
```

## R1-03
```text
docs(recovery): freeze FR-17 local draft contract
test(recovery): add draft store and recovery contracts
feat(recovery): add encrypted local draft store
feat(recovery): persist editor drafts asynchronously
feat(recovery): recover drafts across restart
feat(recovery): preserve operation id and base version
feat(recovery): add reconnect/conflict flow
test(recovery): add restart and fault-injection E2E
docs(recovery): update RTM and evidence
```

## R1-04
```text
docs(lock): freeze FR-14 security/privacy contract
test(lock): add crypto/persistence security contracts
refactor(lock): split safe summary from plaintext editor detail
feat(lock): persist encrypted content envelope
feat(lock): add lock/unlock session flow
feat(lock): save locked edits without plaintext downgrade
feat(lock): add change-passphrase re-encryption
feat(lock): enforce search/notification privacy
test(lock): add tamper, wrong-passphrase and cross-feature E2E
docs(lock): update RTM and security evidence
```


# 31. CI / PR gates

Mỗi PR:
```text
ruff check
ruff format --check
compileall
unit
contract
UI
Mongo integration
desktop E2E
```

Remote:
```text
quality 3.10
quality 3.12
windows-ui
integration
```

Không merge dựa chỉ trên local PASS.

FR-17 PR entry:
- R1-02 merged.
- contract freeze committed.
- keyring unavailable automated.
- no plaintext fallback test.
- restart recovery integration PASS.
- conflict test PASS.

FR-14 PR entry:
- FR-17 merged.
- LOCK-D01..14 reviewed.
- KDF choice documented.
- title privacy decision documented.
- safe read-model design reviewed.
- plaintext downgrade guard test exists.


# 32. Team ownership đề xuất

| Role | Primary |
|---|---|
| M1 / TL | contract, ADR, integration, merge gate |
| M2 / UI | recovery UI, lock UI, state machine |
| M3 / Application | DraftRecovery, Lock/Unlock use cases |
| M4 / Infrastructure | crypto, keyring, local store, Mongo encrypted persistence |
| QA | RTM, fault injection, E2E, evidence |

Security review nên có người độc lập với người implement crypto adapter.


# 33. Scope control

Không đưa vào R1-02/03/04:
- FR-15 Export.
- FR-16 Statistics.
- cloud sync.
- collaboration.
- login/account.
- remote key escrow.
- password recovery.
- rich text.
- encrypted attachment.
- encrypted title trừ khi change request mở scope.

Đặc biệt: SRS không hứa recovery khi quên passphrase.
Không tự invent recovery key.


# 34. Critical invariants

1. **No plaintext draft on disk.**
2. **No locked content plaintext in Mongo.**
3. **No silent stale overwrite.**
4. **No phantom SAVED.**
5. **No secret in log/notification.**
6. **No crypto/file/DB I/O on Tk main thread.**
7. **Metadata mutation must not rewrite encrypted content.**
8. **Failed remote save never deletes the last good local draft.**


# 35. Checklist bắt đầu ngay

```bash
git checkout develop
git pull
git checkout -b feature/r1-02-secure-storage-foundation
```

Verify `develop` chứa merge commit `60f6085` hoặc newer.

Sau đó:
1. Tạo secure-storage Contract Freeze + ADR.
2. Review dependency.
3. Viết AEAD/SecretStore contract tests trước.
4. Implement R1-02.
5. Full CI.
6. Merge R1-02.
7. Tạo `feature/r1-03-draft-recovery`.
8. Implement FR-17 end-to-end.
9. Chỉ merge FR-17 sau restart E2E.
10. Tạo `feature/r1-04-locked-notes`.
11. Freeze KDF/privacy/read model.
12. Implement FR-14.
13. Hardening + release candidate.


# 36. First concrete engineering task

**R1-02.1 — Freeze authenticated-encryption and secret-store contracts**

Deliverables:
1. `ContentCipher` Protocol.
2. `SecretStore` Protocol.
3. `EncryptedEnvelope` model.
4. security error types.
5. AEAD contract tests.
6. keyring fake contract tests.
7. ADR với dependency decision.

Không Mongo schema change.

Không UI change.

Không user-visible feature claim.

Acceptance:
- Domain crypto-library free.
- Application chỉ biết ports/models.
- Infrastructure sở hữu crypto/keyring implementation.
- Tests chứng minh authenticated failure.
- Không plaintext fallback.
- CI green.


# 37. Roadmap cuối

```text
NOW
│
├── R1-02.1 Contract + ADR
├── R1-02.2 AEAD adapter
├── R1-02.3 OS SecretStore adapter
├── R1-02.4 CI / packaging compatibility
│
▼
MERGE R1-02
│
├── R1-03.1 LocalDraft model/store
├── R1-03.2 Encrypted autosave
├── R1-03.3 Restart recovery
├── R1-03.4 Reconnect + idempotency
├── R1-03.5 Conflict / failure injection
├── R1-03.6 Desktop E2E + RTM
│
▼
MERGE FR-17
│
├── R1-04.1 Lock contract/privacy/KDF
├── R1-04.2 Safe read model
├── R1-04.3 Locked Mongo persistence
├── R1-04.4 Lock/unlock session
├── R1-04.5 Update locked content
├── R1-04.6 Change passphrase
├── R1-04.7 Search/notification/log hardening
├── R1-04.8 Cross-feature E2E
│
▼
MERGE FR-14
│
├── R1-05 Security audit
├── R1-05 Reliability regression
├── R1-05 Backup/restore
├── R1-05 Packaging
│
▼
R1 RELEASE CANDIDATE
```

Sau khi R1 hoàn tất mới chuyển sang:
```text
FR-15 Export
FR-16 Statistics
```
ở R2 / Release 0.3.
