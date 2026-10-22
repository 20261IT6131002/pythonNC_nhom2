# PHASE 3 — PLAN 01
## Contract Freeze → Category Management → Image Attachment

**Project:** NoteApp / `20261IT6131002/pythonNC_nhom2`  
**Baseline:** `develop` sau Phase 2  
**Target:** Phase 3A  
**Requirements:** FR-04, FR-08  
**Perspective:** Senior Developer + Tech Lead  
**Development style:** Vertical slice, contract-first, test-first ở core/data boundary  
**Merge target cuối:** `feature/phase-3` → `develop`

---

# 1. Mục tiêu

Phase 3A có hai mục tiêu theo đúng thứ tự phụ thuộc:

1. Hoàn tất FR-04 từ trạng thái **Partial → Done**.
2. Triển khai FR-08 theo vertical slice đầy đủ từ Domain → Application → Infrastructure → Presentation.

Không đưa FR-12/14/15/16 vào phase này. Không refactor lan sang module không liên quan.

Sau Plan 01, hệ thống phải có:

- Quản lý danh mục đầy đủ.
- Category reference ổn định bằng `category_id`.
- Đính kèm tối đa một ảnh cho một note.
- Ảnh nhỏ lưu inline, ảnh lớn lưu GridFS theo rule SRS.
- Replace/remove/purge không tạo orphan attachment.
- UI vẫn không block khi decode/upload/load ảnh.

---

# 2. Điểm xuất phát hiện tại

Repo đã có kiến trúc:

```text
src/noteapp/
├── domain/
├── application/
├── infrastructure/
├── presentation/tk/
├── bootstrap.py
└── main.py
```

Các thành phần liên quan đã tồn tại:

```text
src/noteapp/domain/entities/category.py
src/noteapp/application/ports/category_repository.py

src/noteapp/application/ports/attachment_store.py
src/noteapp/application/services/attachment_service.py
src/noteapp/domain/value_objects/attachment_ref.py

src/noteapp/infrastructure/attachment/
├── hybrid_store.py
├── image_validator.py
└── thumbnailer.py
```

Một số file attachment hiện mới là scaffold. Không coi scaffold là tính năng đã hoàn thành.

---

# 3. Nguyên tắc kiến trúc bắt buộc

Giữ dependency direction:

```text
Presentation
    ↓
Application
    ↓
Domain

Infrastructure ──implements──> Application Ports
Bootstrap ──wires dependencies──> all layers
```

Không được:

- import `pymongo`, `gridfs`, `PIL`, `tkinter` vào Domain.
- để UI thao tác Mongo/GridFS trực tiếp.
- để `AttachmentRef` chứa `ObjectId`.
- xóa ảnh cũ trước khi note mới được cập nhật thành công.
- xử lý decode/upload ảnh trên Tk main thread.
- thêm repository/service "generic" nếu chưa có use case thực tế.

---

# 4. Trình tự phát triển tổng thể

```text
P3A-00 Contract Freeze
       ↓
P3A-01 Category Core
       ↓
P3A-02 Category Persistence
       ↓
P3A-03 Category UI
       ↓
P3A-04 Attachment Domain + Ports
       ↓
P3A-05 Image Validation + Thumbnail
       ↓
P3A-06 Hybrid Storage
       ↓
P3A-07 Note Attachment Use Cases
       ↓
P3A-08 Attachment UI
       ↓
P3A-09 Delete/Restore/Purge Integration
       ↓
P3A-10 QA + Regression + Documentation
```

Không làm UI attachment trước khi storage contract ổn định.

---

# 5. P3A-00 — Contract Freeze

## 5.1 Mục tiêu

Chốt các quyết định ảnh hưởng schema, port và behavior trước khi sửa code.

## 5.2 Quyết định cần khóa

### Category delete policy

Chọn:

> Category đang được note sử dụng thì không cho xóa.

Lý do:

- tránh `updateMany` ngầm.
- tránh partial update.
- không cần transaction chỉ để xử lý category delete.
- hành vi rõ ràng với desktop app MVP.

### Category canonical data

- canonical reference trong Note: `category_id`.
- `None` = Uncategorized.
- không dùng `category_name` làm canonical field.

### Attachment cardinality

Phase 3 chỉ hỗ trợ:

```text
0..1 image / note
```

### Attachment size rule

```text
<= 1 MiB         → inline
>1 MiB <=10 MiB  → GridFS
>10 MiB          → reject
```

### Attachment lifecycle

```text
soft-delete note   → giữ attachment
restore note       → attachment vẫn còn
replace attachment → chỉ xóa old attachment sau khi swap thành công
permanent delete   → cleanup attachment
```

## 5.3 Deliverables

Tạo:

```text
docs/srs/phase 3/01_PHASE3_CONTRACT_FREEZE.md
docs/adr/ADR_PHASE3_CATEGORY_ATTACHMENT.md
```

Checklist:

- [ ] category delete policy
- [ ] attachment cardinality
- [ ] inline/GridFS boundary
- [ ] attachment cleanup semantics
- [ ] schema compatibility
- [ ] error mapping
- [ ] rollback strategy

---

# 6. P3A-01 — Category Core

## 6.1 Mục tiêu

Hoàn chỉnh FR-04 ở Application/Domain trước.

## 6.2 Mở rộng repository contract

Hiện contract chỉ có:

```python
create(...)
find_by_id(...)
list_all(...)
```

Bổ sung hành vi tương đương:

```python
update(...)
delete(...)
count_notes_by_category(...)
```

Tên method cụ thể có thể điều chỉnh theo style hiện tại, nhưng trách nhiệm phải rõ.

## 6.3 Use cases đề xuất

```text
CreateCategory
RenameCategory
UpdateCategoryColor
DeleteCategory
ListCategories
```

Không nhồi mọi hành vi vào một `CategoryService` khổng lồ nếu command/query riêng sẽ rõ hơn.

## 6.4 Validation

- name phải trim.
- blank → reject.
- `casefold()` để kiểm tra uniqueness.
- color format `#RRGGBB`.
- rename không thay `category_id`.

## 6.5 Error model

Tối thiểu:

```text
DuplicateCategory
CategoryNotFound
CategoryInUse
ValidationError
RepositoryUnavailable
```

Presentation chỉ map các lỗi public từ Application/Domain.

---

# 7. P3A-02 — Category Persistence

## 7.1 Mongo adapter

Implement các port mới trong infrastructure.

Yêu cầu:

- unique index theo normalized key.
- query count note theo `category_id`.
- delete phải check referenced notes trước.
- không để race tạo duplicate lọt qua app validation.

## 7.2 Concurrency

Uniqueness phải được đảm bảo ở DB, không chỉ:

```text
if not exists:
    insert
```

Ứng dụng phải map duplicate key từ Mongo → `DuplicateCategory`.

## 7.3 Integration tests

Tối thiểu:

```text
create category
duplicate normalized name
rename category
rename into duplicate
delete unused
delete referenced
list deterministic
```

---

# 8. P3A-03 — Category UI

## 8.1 UI flow

Thêm màn hình/dialog quản lý danh mục:

```text
Category list
 ├─ Add
 ├─ Rename
 ├─ Change color
 └─ Delete
```

## 8.2 State

Không thực hiện synchronous DB I/O trong callback Tk.

Flow:

```text
button click
   ↓
presenter
   ↓
worker
   ↓
application use case
   ↓
queue result
   ↓
UIEventPump
   ↓
render
```

## 8.3 Đồng bộ UI

Sau create/rename/delete:

- editor combobox refresh.
- filter category refresh.
- selected category không bị mất sai trạng thái.
- rename không làm note mất liên kết.

## 8.4 Acceptance

- [ ] create category.
- [ ] rename category.
- [ ] duplicate bị báo rõ.
- [ ] delete category chưa dùng.
- [ ] không delete category đang dùng.
- [ ] filter/editor cập nhật mà không restart app.

---

# 9. P3A-04 — Attachment Domain + Port

## 9.1 `AttachmentRef`

Value object không phụ thuộc GridFS/BSON.

Ví dụ conceptual:

```text
AttachmentRef
├── storage_key: str
├── storage_kind: INLINE | GRIDFS
├── mime_type: str
├── size_bytes: int
├── sha256: str
└── display_name: str
```

Không bắt buộc đúng tên field này nếu repo có naming convention khác.

## 9.2 Note entity

Mở rộng Note:

```text
attachment: AttachmentRef | None
```

Mọi mapper, DTO, fake, contract tests phải được cập nhật đồng bộ.

## 9.3 Attachment store port

Nên có capability tương đương:

```text
put(...)
get(...)
delete(...)
exists(...)
```

Không expose Mongo/GridFS type.

---

# 10. P3A-05 — Image Validation + Thumbnail

## 10.1 Validation pipeline

```text
raw bytes
  ↓
size check
  ↓
decode verify
  ↓
MIME detection/allowlist
  ↓
pixel/dimension guard
  ↓
hash
  ↓
thumbnail
```

## 10.2 Không tin extension

Không dùng `.png`, `.jpg` làm tiêu chí duy nhất.

## 10.3 Security guard

Chống:

- corrupt image.
- decompression bomb / pixel explosion.
- extension spoofing.
- unsupported format.
- >10 MiB.

## 10.4 Thumbnail

Thumbnail dùng cho UI, không mutate original bytes.

Decode/resize phải chạy worker thread.

---

# 11. P3A-06 — Hybrid Storage

## 11.1 Inline

Với ảnh `<=1 MiB`:

- lưu attachment payload inline theo schema đã freeze.
- mapper chịu trách nhiệm BSON.

## 11.2 GridFS

Với ảnh `>1 MiB && <=10 MiB`:

- upload GridFS.
- nhận storage identifier.
- convert sang opaque string cho `AttachmentRef`.

## 11.3 Idempotency / cleanup

Nếu upload xong nhưng note update fail:

```text
new upload
   ↓
note CAS fails
   ↓
delete new upload
```

Nếu replace:

```text
upload new
   ↓
CAS note to new ref
   ↓
success?
 ├─ yes → delete old
 └─ no  → delete new, retain old
```

Đây là invariants bắt buộc.

---

# 12. P3A-07 — Attachment Use Cases

Tách rõ:

```text
AttachImageToNote
ReplaceNoteImage
RemoveNoteImage
GetNoteImage
```

Hoặc một service có các operations rõ ràng nếu style hiện tại của project phù hợp hơn.

## 12.1 Update Note

Attachment update phải dùng optimistic concurrency / expected version tương tự edit note hiện tại.

Không silently overwrite attachment khi version stale.

## 12.2 Error mapping

Tối thiểu:

```text
UnsupportedImage
ImageTooLarge
CorruptedImage
AttachmentStoreFailure
VersionConflict
NoteNotFound
```

---

# 13. P3A-08 — Attachment UI

## 13.1 Editor behavior

Bổ sung:

```text
Choose image
Preview
Replace
Remove
Loading state
Error state
```

## 13.2 UX

Khi upload:

```text
DIRTY
  ↓
SAVING
  ↓
SAVED
```

Nếu fail:

```text
SAVING
  ↓
ERROR / UNSAVED
```

Không hiển thị preview mới như đã lưu nếu persistence thất bại.

## 13.3 Async safety

Dùng request sequence/request id.

Nếu user đổi note trước khi thumbnail trả về:

```text
stale result → discard
```

Không render thumbnail vào view đã destroy.

---

# 14. P3A-09 — Trash / Restore / Purge Integration

## 14.1 Soft delete

Không xóa attachment.

## 14.2 Restore

Không upload lại attachment; sử dụng ref cũ.

## 14.3 Permanent delete

Flow:

```text
claim/delete note
      ↓
cleanup attachment
      ↓
record completion
```

Nếu cleanup fail, phải có trạng thái retry/reconcile phù hợp với infrastructure hiện tại.

Không để permanent delete tạo orphan im lặng.

## 14.4 Retention

Retention hiện có của Phase 2 không được xóa attachment nếu chưa được nâng cấp đầy đủ.

Nếu chưa đủ khả năng cleanup an toàn:

> retention attachment phải bị disable hoặc skip explicit.

---

# 15. P3A-10 — Testing Strategy

## Unit

```text
test_category_rules.py
test_attachment_ref.py
test_attachment_service.py
test_image_validation.py
```

## Contract

```text
test_category_repository_contract.py
test_attachment_store_contract.py
```

## Integration

```text
test_category_mongo.py
test_attachment_inline.py
test_attachment_gridfs.py
test_attachment_cleanup.py
```

## UI

```text
test_category_management_ui.py
test_attachment_ui.py
```

## Fault injection

Bắt buộc có:

- GridFS upload fail.
- Mongo update fail sau upload.
- delete old attachment fail.
- corrupt input.
- stale version.

---

# 16. Acceptance Matrix

| Requirement | Case | Expected |
|---|---|---|
| FR-04 | Create | PASS |
| FR-04 | Rename | PASS |
| FR-04 | Duplicate normalized name | Reject |
| FR-04 | Delete unused | PASS |
| FR-04 | Delete referenced | Reject |
| FR-08 | 1 MiB | INLINE |
| FR-08 | >1 MiB <=10 MiB | GRIDFS |
| FR-08 | >10 MiB | Reject |
| FR-08 | Corrupt | Reject |
| FR-08 | Replace fail | Old ref retained |
| FR-08 | Trash/restore | Image preserved |
| FR-08 | Permanent delete | No orphan |

---

# 17. Git / Branch Strategy

Từ `develop`:

```bash
git switch develop
git pull origin develop
git switch -c feature/phase-3
```

Task branches:

```text
feature/p3-contract-freeze
feature/p3-category-management
feature/p3-image-domain
feature/p3-image-storage
feature/p3-image-ui
test/p3-image-acceptance
```

Mỗi PR chỉ nên giải quyết một vertical slice hoặc contract rõ ràng.

Không commit trực tiếp lên `develop`.

---

# 18. Commit Sequence Gợi Ý

```text
docs(p3): freeze category and attachment contracts
feat(core): complete category management use cases
feat(data): implement category update and guarded delete
feat(ui): add category management workflow
feat(core): add attachment reference and application contracts
feat(media): implement image validation and thumbnail pipeline
feat(data): implement inline and gridfs attachment storage
feat(core): implement note image lifecycle
feat(ui): integrate note image selection and preview
fix(data): reconcile attachment cleanup with purge
test(p3): cover category and attachment acceptance
docs(p3): record phase 3a evidence
```

---

# 19. PR Review Checklist

Reviewer cần kiểm:

### Architecture
- [ ] Domain không import infrastructure.
- [ ] UI không query Mongo/GridFS.
- [ ] bootstrap là composition root.

### Data
- [ ] category uniqueness ở DB.
- [ ] no attachment orphan.
- [ ] old attachment retained until successful swap.
- [ ] soft delete không xóa attachment.

### Concurrency
- [ ] expected version/CAS.
- [ ] UI không block.
- [ ] stale async result discarded.

### Security
- [ ] MIME/decode validation.
- [ ] size guard.
- [ ] pixel bomb guard.
- [ ] filename không được dùng làm trusted path.

### Test
- [ ] unit.
- [ ] contract.
- [ ] integration.
- [ ] UI.
- [ ] failure path.

---

# 20. Definition of Done — Plan 01

Plan 01 chỉ được đóng khi:

- [ ] FR-04 chuyển thành DONE.
- [ ] FR-08 chuyển thành DONE.
- [ ] category management end-to-end chạy thật.
- [ ] inline/GridFS boundaries pass.
- [ ] no orphan test pass.
- [ ] trash/restore/purge attachment pass.
- [ ] UI không freeze với ảnh lớn.
- [ ] architecture gate xanh.
- [ ] CI xanh.
- [ ] RTM cập nhật.
- [ ] Phase 3A test evidence được lưu.

---

# 21. Stop Conditions

Dừng và yêu cầu review Tech Lead nếu:

- cần đổi attachment cardinality >1.
- muốn đổi threshold 1/10 MiB.
- muốn tự động reassign note khi delete category.
- cần transaction Mongo nhiều collection.
- muốn đưa encryption FR-14 vào attachment.
- phải đổi public DTO/port lớn ngoài Phase 3.
- retention không thể đảm bảo cleanup an toàn.

---

# 22. Kết quả mong đợi

Sau Plan 01:

```text
Phase 2 baseline
     ↓
FR-04 complete
     ↓
FR-08 complete
     ↓
Stable category + media foundation
     ↓
Ready for Reminder subsystem
```

Đây là điểm bàn giao sang **PHASE3_PLAN_02_REMINDER_DELIVERY.md**.
