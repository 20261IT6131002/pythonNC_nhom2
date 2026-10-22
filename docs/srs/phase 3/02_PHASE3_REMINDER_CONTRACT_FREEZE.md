# Phase 3B — P3B-00 Reminder Contract Freeze (FR-09, FR-10)

Trạng thái: **ĐỀ XUẤT — chờ M1 + owner liên quan review (Gate A)**. Các mục `ASSUMPTION`
bám DEC-05 còn OPEN (nhắc khi app đóng / giới hạn missed-reminder) và không được xem là
đã duyệt. Nguồn: `PHASE3_PLAN_02_REMINDER_DELIVERY.md`, SRS v2 FR-09/FR-10 (AC-09a/b,
AC-10a/b/c), kiến trúc §8. ADR: [ADR Phase 3B](../../adr/ADR_PHASE3_REMINDER_DELIVERY.md).

## 1. Quyết định

| # | Quyết định | Trạng thái |
|---|---|---|
| R1 | Lưu **UTC aware**; UI nhập/hiển thị giờ địa phương. Không lưu naive datetime | Chốt |
| R2 | Múi giờ lấy từ `NOTEAPP_TIMEZONE` hoặc OS (`resolve_timezone`). Không xác định được → từ chối (`ValidationError`), **không đoán offset** | Chốt |
| R3 | Giờ địa phương rơi vào **khoảng trống DST** (không tồn tại) hoặc **lặp DST** (mơ hồ) → từ chối, không đoán | Chốt (plan §10) |
| R4 | Trạng thái công khai tối thiểu: `ACTIVE`, `DELIVERED`, `CANCELLED`. Không có `SNOOZED/FAILED/RECURRING` | Chốt |
| R5 | Đặt/đổi lịch là **một thao tác**: thời điểm tương lai (`due_at > now`, so với `Clock`) → `ACTIVE`, từ bất kỳ trạng thái nào (kể cả `DELIVERED`/`CANCELLED`). Không cấm reschedule `DELIVERED` | `ASSUMPTION` (plan §9.2: PO chưa chốt) |
| R6 | Hủy chỉ có tác dụng với `ACTIVE` (idempotent no-op nếu không có gì chờ); lưu trạng thái `CANCELLED` bền vững; **không bao giờ ghi đè `DELIVERED`** | Chốt |
| R7 | Note trong **thùng rác không phát nhắc**. Khôi phục note có nhắc `ACTIVE` quá hạn → xử lý như missed reminder ở lần quét/poll kế tiếp. Xóa vĩnh viễn xóa luôn reminder | Chốt (khuyến nghị plan §12.1) |
| R8 | **Missed reminder**: khi mở app, reminder `ACTIVE` có `due_at <= now` được xử lý bằng *cùng* luồng giao như bình thường, theo thứ tự `due_at`; không âm thầm bỏ. Quét khởi động chạy xong **trước** khi poller bắt đầu | `ASSUMPTION` (DEC-05: SRS nói "có giới hạn"; ở đây mỗi lượt tối đa 20, các lượt sau tiếp tục) |
| R9 | Chỉ nhắc khi app đang mở; không daemon/Windows Service/push | Chốt (plan §3) |
| R10 | Cam kết giao là **best effort, không exactly-once**; `DELIVERED` nghĩa là *lời gọi thông báo OS đã được chấp nhận*, không chứng minh thông báo đã hiện | Chốt (plan §6.4, AC-10c) |
| R11 | Chu kỳ poll cấu hình qua `NOTEAPP_REMINDER_POLL_SECONDS` (mặc định 30, hợp lệ 5–3600) | Chốt |

## 2. State machine

```text
(none) --set(future)--> ACTIVE --claim+notify OK--> DELIVERED
ACTIVE --cancel--> CANCELLED
ACTIVE / DELIVERED / CANCELLED --set(future)--> ACTIVE   (reschedule, xóa claim đang giữ)
```

`CLAIMED` **không** là trạng thái công khai: là metadata nội bộ của adapter (lease).

## 3. Claim và giao (atomic, lease)

```text
claim_next_due : find_one_and_update(is_deleted=false, status=ACTIVE, due_at<=now,
                   không có lease còn hạn, không trong thời gian chờ retry, attempts<3)
                 -> set claim_token + claim_until(now+2min), attempts+1
notify         : NotificationGateway.notify(title, message)  (chỉ text)
ok             : mark_delivered(token)  -> DELIVERED (chỉ nếu token còn sở hữu)
fail           : release_claim(token, retry_at = now + 1 phút / 5 phút)
```

- Hai poller chạy đồng thời **không** nhận cùng một reminder (test 12 luồng, 4 service).
- Chuyển trạng thái giao **không đổi `version`/`updated_at`**: editor đang mở không bị
  `Conflict` chỉ vì nhắc vừa hiện. Cấu hình (set/cancel) là CAS theo `version`, thay cả
  sub-document → hủy claim đang giữ, nên **reschedule/cancel đã commit thắng claim cũ**:
  `mark_delivered` bằng token cũ trả `False`.
- Race chấp nhận được: claim xong, thông báo đã gọi, rồi người dùng hủy ngay → thông báo vẫn
  hiện nhưng trạng thái là `CANCELLED` (không có lời hứa "thu hồi" thông báo OS).
- Crash giữa `notify` và `mark_delivered`: sau khi lease hết hạn reminder được giao lại
  (tối đa 3 lần claim) → có thể trùng; tài liệu hóa là best effort.
- Thông báo OS lỗi: không crash, log marker đã làm sạch (không chứa đường dẫn/secret),
  retry có giới hạn (3 lần, backoff 1 → 5 phút). Hết lượt vẫn `ACTIVE` (không nói dối là
  đã giao), không còn được poll; UI hiển thị "chưa nhận thông báo, sẽ thử lại"; người dùng
  đặt lại lịch để reset bộ đếm.

## 4. Schema (additive, không migration, không đổi `schema_version`)

`notes.reminder` (tùy chọn): `{due_at, status, updated_at, delivered_at?}` cộng metadata nội
bộ của adapter khi đang giao: `{claim_token, claim_until, attempts, next_attempt_at}` (không
nằm trong entity). Index partial `idx_notes_reminder_due` trên
`(reminder.status, reminder.due_at)` với `partialFilterExpression {reminder.status: "ACTIVE"}`
phục vụ truy vấn đến hạn (có test `explain`). Purge/retention chấp nhận field `reminder`
(là dữ liệu thường, xóa cùng note). Rollback code: field thừa bị bỏ qua.

## 5. Lỗi public và UI

`ValidationError` (quá khứ, DST, không có múi giờ) · `Conflict` · `NotFound` (kể cả note đã
vào thùng rác) · `RepositoryUnavailable`. UI chỉ hiển thị thông điệp đã map. Trạng thái UI:
chưa đặt / `ACTIVE` (kèm "đã đến hạn, đang chờ gửi" khi quá hạn) / đang lưu / lỗi; trạng thái
giao nằm riêng, không lẫn với `EditorPhase`.

## 6. Checklist Gate A
- [x] state machine (R4–R6) · [x] timezone/DST (R1–R3) · [x] missed reminder (R8)
- [x] trash (R7) · [x] atomic claim (§3) · [x] schema/index/rollback
- [ ] M1/PO duyệt các `ASSUMPTION` R5, R8 (DEC-05)

## 7. Stop conditions (kế thừa plan §26)
Reminder lặp, thông báo khi app đóng, daemon theo OS, cloud notification, đổi schema lớn,
mã hóa nội dung reminder, transaction nhiều collection → dừng và hỏi Tech Lead/PO.
