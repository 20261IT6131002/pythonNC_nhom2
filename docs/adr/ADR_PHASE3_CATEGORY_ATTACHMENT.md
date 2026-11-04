# ADR — Phase 3A: category management và image attachment

Status: **Accepted — Gate A approved 2026-10-22** (Nguyễn Mạnh Thi xác nhận đã thống nhất với Giang Lê Hoàng). Task: P3A-00. Ngày: 2026-10-22.
Chi tiết hợp đồng: [01_PHASE3_CONTRACT_FREEZE](../srs/phase%203/01_PHASE3_CONTRACT_FREEZE.md).

## Context
FR-04 mới có create/find/list; FR-08 mới là scaffold. DEC-06 và chính sách xóa category AC-04b đã được chốt: một ảnh/note; từ chối xóa category còn được tham chiếu.

## Decisions
1. Mở rộng `CategoryRepository` (update, delete, count) và thêm use case riêng
   `CreateCategory/RenameCategory/UpdateCategoryColor/DeleteCategory/ListCategories`.
2. Xóa category đang dùng bị từ chối; không `updateMany`, không transaction.
3. `Note.attachment: AttachmentRef | None` (mặc định `None`, không đổi chữ ký cũ).
   `AttachmentRef` không chứa `ObjectId`/BSON; `storage_key` là chuỗi opaque.
4. Port mới, tách khỏi port cũ: `AttachmentStore` (put/get/delete/exists),
   `NoteAttachmentRepository` (CAS đổi attachment), `ImageProcessor` (validate +
   thumbnail, hiện thực bằng Pillow ở infrastructure). Presentation chỉ nhận bytes PNG
   từ use case, không import PIL.
5. Inline = BinData trong collection `attachment_blobs`; GridFS cho ảnh > 1 MiB.
6. Cleanup: xóa blob best-effort sau khi note đã đổi/xóa; reconciler xóa payload không
   còn note nào tham chiếu và cũ hơn grace 15 phút. Không dùng collection intent riêng.
7. Retention/purge Phase 2 được nâng cấp để dọn attachment qua đúng luồng trên.
8. Thêm dependency runtime `Pillow` (chỉ import ở `infrastructure/attachment`).

## Consequences
+ Không đổi schema_version, rollback an toàn, UI không chạm Mongo/GridFS.
− Thêm collection `attachment_blobs` + bucket GridFS; cần reconciler chạy định kỳ/CLI.
− Race xóa category còn một cửa sổ rất hẹp (xem contract freeze §1).

## Rejected
Nhúng bytes inline vào document note (làm nặng list/search); tự gán note về
Uncategorized khi xóa category (ghi nhiều document, cần transaction).
