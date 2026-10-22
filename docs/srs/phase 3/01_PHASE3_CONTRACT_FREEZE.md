# Phase 3A — P3A-00 Contract Freeze (FR-04, FR-08)

Trạng thái: **ĐỀ XUẤT — chờ M1 + owner liên quan review**. Các mục đánh dấu
`ASSUMPTION` bám DEC còn OPEN trong SRS v2 (DEC-06 một/nhiều ảnh; chính sách xóa
category ở AC-04b) và không được xem là đã duyệt cho tới khi PM/M1 xác nhận.
Nguồn: `PHASE3_PLAN_01_CATEGORY_IMAGE.md`, SRS v2 FR-04/FR-08/FR-03, AUD-02/13/19.
Quyết định kiến trúc đi kèm: [ADR Phase 3](../../adr/ADR_PHASE3_CATEGORY_ATTACHMENT.md).

## 1. Category (FR-04)

| # | Quyết định | Trạng thái |
|---|---|---|
| C1 | `category_id` là tham chiếu canonical trong note; `None` = Chưa phân loại; không lưu `category_name` trong note | Đã có từ Phase 1 |
| C2 | Tên trim + NFC + `casefold()` → `name_key`, unique bằng index `uq_categories_name_key`; app validation không thay thế DB | Đã có, giữ nguyên |
| C3 | Rename/đổi màu **không** đổi `category_id`; note không cần cập nhật | Chốt |
| C4 | Xóa category đang được note dùng (kể cả note trong thùng rác) → **từ chối** `CategoryInUse`; không `updateMany` ngầm | `ASSUMPTION` (AC-04b: "chuyển về Uncategorized hoặc từ chối") |
| C5 | Màu `#RRGGBB`; mặc định `#64748B` khi UI không chọn | Chốt |
| C6 | Rename/đổi màu last-writer-wins (category không có `version`); không phải dữ liệu nghiệp vụ nhạy cảm | Chốt, ghi rủi ro |

Lỗi public: `DuplicateCategory`, `CategoryNotFound` (là `NotFound`), `CategoryInUse`,
`ValidationError`, `RepositoryUnavailable`. Xóa dùng marker `deleting` → đếm note →
xóa có điều kiện (không transaction). Cửa sổ race còn lại: note được gán category giữa
lúc kiểm tra tồn tại và insert. Hậu quả giới hạn: tham chiếu treo, UI hiển thị
Chưa phân loại (Phase 2 đã có test dangling reference).

## 2. Attachment (FR-08)

| # | Quyết định | Trạng thái |
|---|---|---|
| A1 | Cardinality **0..1 ảnh / note** | `ASSUMPTION` (DEC-06 OPEN; AUD-13 đề xuất) |
| A2 | `<= 1 MiB` (1 048 576 byte, inclusive) → `INLINE`; `> 1 MiB` và `<= 10 MiB` → `GRIDFS`; `> 10 MiB` → từ chối | Chốt theo AC-08a |
| A3 | Chỉ nhận PNG/JPEG/GIF/WebP, xác định bằng **decode nội dung**, không tin đuôi file/MIME do client | Chốt |
| A4 | Giới hạn pixel (`<= 25 000 000` px, mỗi cạnh `<= 12 000`) kiểm tra từ header trước khi decode, chống decompression bomb | Đề xuất kỹ thuật |
| A5 | Thumbnail: width tối đa 400 px, giữ tỉ lệ, PNG, sinh theo yêu cầu từ ảnh gốc ở worker; không ghi đè bytes gốc | Chốt theo AC-08c |
| A6 | `display_name` chỉ là nhãn hiển thị (đã làm sạch), **không** bao giờ dùng làm đường dẫn | Chốt |

### Lifecycle (bất biến)

```text
attach/replace : put(new) -> CAS note.attachment -> (thành công) delete(old)
                                                 -> (thất bại)  delete(new), giữ old
remove         : CAS note.attachment=None -> delete(old)
soft-delete    : giữ attachment          restore : dùng lại ref cũ
permanent del  : CAS xóa note -> delete(blob)
                 delete(blob) lỗi => blob không còn note tham chiếu, reconciler dọn sau grace
```

Xóa blob thất bại (sau swap, remove hoặc purge) **không** làm thao tác đã hoàn tất thất
bại và được ghi log `attachment_cleanup_deferred`. Reconciler xóa mọi payload không còn
note nào tham chiếu (kể cả note trong thùng rác, vốn vẫn giữ ảnh) và cũ hơn grace 15
phút — đáp ứng AC-08d; grace giữ an toàn cho upload đang diễn ra. Reconciler chạy cùng
job retention (opt-in `NOTEAPP_ENABLE_RETENTION=1`) và `scripts/run_retention.py --apply`.
Purge/retention của note **có ảnh** chỉ chạy khi `MongoTrashRepository` được cấp
`AttachmentStore`; nếu không, hành vi fail-closed của Phase 2 được giữ nguyên.

### Schema (additive, không migration, không đổi `schema_version`)

`notes.attachment` (tùy chọn): `{storage_kind, storage_key, mime_type, size_bytes,
sha256, display_name}`. `INLINE`: bytes là BinData trong collection `attachment_blobs`
(`_id = storage_key`, kèm `owner_note_id`, `created_at`) — **không** nhúng vào document
note để các trang list/search không phải tải tới 1 MiB mỗi dòng. `GRIDFS`: file trong
bucket `attachments`, `storage_key` = hex của file id, metadata `owner_note_id`,
`created_at`. Index phụ `idx_notes_attachment_key` (partial) phục vụ reconciler. Code Phase 2 gặp note có `attachment` sẽ
**từ chối purge** (fail-closed), nên rollback code không làm mất ảnh.

### Lỗi public

`UnsupportedImage`, `ImageTooLarge`, `CorruptedImage`, `AttachmentStoreFailure`
(là `RepositoryUnavailable`), `Conflict` (version stale), `NotFound`.
Hộp thoại UI chỉ hiển thị thông điệp đã map, không lộ chi tiết nội bộ.

## 3. Rollback
Thay đổi additive: bỏ code Phase 3 → note có ảnh vẫn đọc được (field thừa bị bỏ qua),
purge bị chặn fail-closed. Không có migration cần đảo. Blob mồ côi có thể dọn
bằng reconciler sau khi tái triển khai.

## 4. Checklist freeze
- [x] category delete policy (C4, ASSUMPTION)
- [x] attachment cardinality (A1, ASSUMPTION)
- [x] inline/GridFS boundary (A2)
- [x] cleanup semantics (lifecycle)
- [x] schema compatibility (additive)
- [x] error mapping
- [x] rollback
- [ ] M1 + M3/M4/M2 review và duyệt các `ASSUMPTION`

## 5. Stop conditions (kế thừa plan §21)
Đổi cardinality > 1, đổi ngưỡng 1/10 MiB, tự gán lại note khi xóa category, cần
transaction nhiều collection, mã hóa ảnh (FR-14), hoặc retention không dọn an toàn
→ dừng và hỏi Tech Lead.
