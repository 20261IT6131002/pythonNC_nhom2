# ADR — Phase 3B reminder configuration and delivery (FR-09, FR-10)

Trạng thái: **Proposed** (chưa Accepted; chờ M1 review). Hợp đồng chi tiết:
[02_PHASE3_REMINDER_CONTRACT_FREEZE](../srs/phase%203/02_PHASE3_REMINDER_CONTRACT_FREEZE.md).

## Quyết định

1. **Reminder nhúng trong document note** (`notes.reminder`) thay vì collection riêng: một
   note có tối đa một reminder, vòng đời gắn với note (soft-delete, restore, purge), và truy
   vấn đến hạn dùng một partial index. Tránh transaction nhiều collection (stop condition).
2. **Hai loại ghi, hai mức đồng thời**: cấu hình (set/reschedule/cancel) là CAS theo
   `version` và tăng `version`; chuyển trạng thái giao (claim, delivered, release) là cập
   nhật có điều kiện theo `claim_token` và **không** đổi `version`, để editor đang mở không
   bị conflict khi nhắc vừa hiện. Hệ quả: cấu hình mới luôn thắng claim cũ, vì nó thay cả
   sub-document.
3. **Claim lease thay vì trạng thái `CLAIMED` công khai**: giữ domain ba trạng thái; lease
   (2 phút) cho phép phục hồi sau crash; mỗi claim tăng `attempts`, tối đa 3 lần.
4. **Poller là hạ tầng mỏng**: một thread không-daemon, `Event.wait` giữa các lượt, `stop()`
   signal + join; chỉ gọi `ReminderDeliveryService.deliver_due`; kết quả chuyển về UI qua
   `TaskRunner.publish` → `queue.Queue` → `UIEventPump` (poller không chạm Tk). Lỗi job được
   log (không payload) và backoff gấp đôi tới 8 lần chu kỳ.
5. **Thứ tự khởi động**: dependency → khởi tạo DB/index → quét missed (worker) → khi quét xong
   mới start poller. Tắt: poller.stop → đóng window/runner → đóng Mongo client.
6. **plyer** chỉ nằm ở infrastructure, import lười; mọi lỗi provider quy về
   `NotificationFailure` đã làm sạch. Thêm phụ thuộc `plyer>=2.1,<3`.

## Phương án đã loại
- Collection `reminders` riêng: cần giữ nhất quán với trash/purge bằng transaction.
- Poll bằng `root.after` trên Tk: chạy Mongo trong worker vẫn cần thread; poller riêng dễ test
  và dừng đúng hơn, và không phụ thuộc vòng đời widget.
- Đổi `version` khi giao: gây `Conflict` giả với người đang sửa note.

## Hệ quả / rủi ro
- Không exactly-once; có thể trùng sau crash giữa notify và mark (đã tài liệu hóa).
- Hết 3 lượt retry vẫn `ACTIVE` và không được poll cho tới khi đặt lại lịch.
- Nhắc chỉ hoạt động khi app mở (DEC-05 OPEN).
- Thêm một index (`idx_notes_reminder_due`); `create_indexes` additive.
