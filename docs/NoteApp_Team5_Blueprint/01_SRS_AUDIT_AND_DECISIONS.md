# 01 — SYSTEM DESIGN + PM REVIEW: SRS GỐC

**Nguồn phân tích:** `SRS Ứng Dụng Ghi Chú.docx` (27 trang), các phần FR, NFR, CST, schema, UC, RTM.  
**Phân biệt:** `[GỐC]` = SRS đã gửi; `[ĐỀ XUẤT]` = bổ sung/điều chỉnh từ System Designer; `[CẦN CHỐT]` = không được tự coi đã phê duyệt.

## A. Đánh giá điều đang làm tốt

- Có **16 FR** với ưu tiên Shall/Should/May; **FR-01…FR-11 = Shall**, **FR-12…FR-14 = Should**, **FR-15…FR-16 = May**.
- Có đủ constraint Python 3.10+, Tkinter+ttkbootstrap, PyMongo/MongoDB; định hướng UI 3 pane 20/30/50; sơ đồ logic Presentation–Service–Repository.
- Đã nghĩ đến nonblocking I/O, search debounce, GridFS, UTC reminder, NFR hiệu năng, AES-GCM, RTM.
- Có UC-01...UC-08 và test codes hiện có, nhưng coverage RTM chưa đồng nhất giữa 16 FR với các edge/negative/NFR.

## B. Danh sách phát hiện cần xử lý

| Mã | Mức | Căn cứ SRS gốc | Vấn đề và hậu quả | Hành động kiến nghị |
|---|---|---|---|---|
| AUD-01 | **P0** | FR-03 Shall; FR-13 Should; đoạn vòng đời và Thùng rác | Xóa ghi chú bắt buộc, nhưng soft delete mặc định lại thuộc tính năng Should | Chốt soft delete thành P0 phụ thuộc FR-03; hard delete có xác nhận |
| AUD-02 | **P0** | deleted_at TTL 30 ngày + GridFS | TTL xóa BSON mà không cascade ảnh GridFS, sinh orphan data | **Không TTL trên notes**; purge job xóa ảnh rồi document có kiểm toán/retry |
| AUD-03 | **P0** | NFR reliability offline: cache local + UC-01 JSON | Không có contract bản nháp, mã hóa, idempotency, reconciliation → rò rỉ/mất/ghi đè dữ liệu | Local encrypted draft & recovery ở MVP; offline sync đa thiết bị đưa R2 |
| AUD-04 | **P0** | CST-03 + root.after từ worker | Tk main-thread rule chưa có thread ownership/boundary cụ thể, rủi ro crash/kẹt UI khi đóng cửa sổ | Worker chỉ đẩy `Queue`, **main thread** tự gọi `root.after()` để poll, shutdown/cancel rõ |
| AUD-05 | **P0** | FR-10 `reminder_triggered` sau `notify` | Không thể khẳng định OS đã thực sự hiển thị; crash giữa notify/update có thể nhắc lặp | Delivery = best effort, event id/dedup; đánh dấu attempted; explicit behavior khi app tắt |
| AUD-06 | **P0** | NFR-SEC-01 trực tiếp MongoDB | `.env` không bảo vệ credential khi đóng gói desktop hoặc truy cập DB public | Dev/test DB isolated; TLS, least-privilege; production từ xa dùng API/identity riêng ở phase scale |
| AUD-07 | **P0** | FR-14 PIN + AES; NFR-SEC-02 | PIN ngắn dễ brute force offline; thiếu key lifecycle, nonce, KDF params, thông báo lộ nội dung | PIN/passphrase strength policy; AES-GCM + KDF mạnh, per-note salt/nonce; không notify nội dung ghi chú khóa |
| AUD-08 | P1 | Schema `category_id` optional, `category_name` mandatory | Tên danh mục lưu lặp dễ lệch khi rename/delete category | Chọn `category_id` là canonical; `category_name` là snapshot/derived, quy tắc sync |
| AUD-09 | P1 | Sort `priority` String index -1 | Sắp xếp lexical HIGH/LOW/MEDIUM **không tương đương** HIGH/MEDIUM/LOW | Lưu `priority_rank` 3/2/1 hoặc aggregation order; tests |
| AUD-10 | P1 | FR-06 native Mongo `$text` | Hành vi search tiếng Việt, dấu, stop words, substring không xác định | Chốt semantics (full-word, accent behavior), seed Vietnamese benchmark; không hứa mọi substring |
| AUD-11 | P1 | NFR-PERF-01 2s/5k; -02 200ms/10k | Thiếu baseline máy, cold/warm, remote latency, p95, query timeout | Định nghĩa môi trường đo + p95; các target chưa verify là provisional |
| AUD-12 | P1 | NFR-PERF-03 60 FPS Tkinter | Tk widgets không có frame profiler phổ quát, claim 60FPS khó đo kiểm | Thay bằng main loop delay p95<=50ms, scroll smooth subjective + load test (cần phê duyệt) |
| AUD-13 | P1 | FR-08 Hybrid BinData/GridFS | Chưa khóa một hay nhiều ảnh/note; replace/delete/file orphan; 1MB boundary | MVP đúng **1 ảnh/note**, MIME sniff, size 10MB, compensating cleanup |
| AUD-14 | P1 | Scheduler 30s | App tắt không có scheduler, sự kiện lỡ hạn chưa rõ; timezone/DST | Chốt app-open-only + missed reminders khi mở lại; UTC storage & local display |
| AUD-15 | P1 | FR-01 content gần không giới hạn | Ngưỡng BSON 16MB bao gồm metadata và inline image; không có giới hạn UX | Đề xuất text cap 1 MiB UTF-8 cho MVP; nếu không được duyệt cần stream/design khác |
| AUD-16 | P1 | NFR-SEC-03 NoSQL injection | Chỉ kiểm tra kiểu là chưa đủ nếu truyền payload user thành query map | Repository chỉ nhận typed filter object, không nhận Mongo query dict từ UI |
| AUD-17 | P1 | CST-05 Windows/Ubuntu/macOS | Không có OS acceptance matrix / chi phí pack/notifications | Cross-platform smoke/packaging với ghi chú unverified OS |
| AUD-18 | P2 | RTM + dẫn chứng | FR-16 thiếu trong RTM hiện có; nguồn kỹ thuật pha trộn blog/FB/Scribd, vài claim là tuyệt đối | Bổ sung FR-16, negative tests; ưu tiên docs Python/Mongo chính thức khi rà soát kỹ thuật |
| AUD-19 | P1 | FR-01 insert GridFS trước insert note | Insert note thất bại sau ghi GridFS tạo tệp mồ côi | Commit unit-of-work bù trừ, orphan reconciler, rollback; transaction khi môi trường cho phép |
| AUD-20 | P1 | UI searches redraw every result | Race kết quả cũ về sau kết quả mới và rebuild card list gây lag | Request generation id, pagination/virtual scroll, drop stale response |

## C. Decision log — cần PM / PO / giảng viên chốt

| Quyết định | Nội dung cần ký duyệt | Đề xuất mặc định | Tình trạng / ảnh hưởng |
|---|---|---|---|
| DEC-01 | Phạm vi release? | MVP = FR-01..11 + FR-13 (được promote) + bảo toàn draft | **OPEN**; thay đổi mức Shall FR-13 |
| DEC-02 | Xóa note xử lý thế nào? | Delete = soft-delete mặc định; hard-delete xác nhận; purge sau 30 ngày | **OPEN**; ảnh hưởng FR-03,13 |
| DEC-03 | Offline đến mức nào? | V1 chỉ lưu nháp local mã hóa và recover; không có multi-device full sync | **OPEN**; ảnh hưởng NFR-reliability |
| DEC-04 | Chế độ MongoDB production? | Không cấp DB rộng cho desktop công khai; MVP LAN/private account tối thiểu | **OPEN**; production/security gate |
| DEC-05 | Nhắc nhở khi app đóng? | V1 chỉ nhắc khi app đang mở; mở lại xử lý quá hạn có giới hạn | **OPEN**; FR-10 |
| DEC-06 | Một hay nhiều ảnh? | V1 một ảnh/note; R2 nhiều ảnh | **OPEN**; FR-08/schema |
| DEC-07 | Tìm kiếm chính xác nghĩa gì? | Mongo text token search, không substring; kiểm thử tiếng Việt | **OPEN**; FR-06 |
| DEC-08 | Giới hạn nội dung? | 1 MiB UTF-8 / note, title 1..250 ký tự | **OPEN**; FR-01 |
| DEC-09 | Tiêu chí hiệu năng? | Giữ gốc để đánh giá; bổ sung p95/hardware testbed; 60FPS được đưa thành KPI chưa chốt | **OPEN**; NFR |
| DEC-10 | Mã PIN hay passphrase? | R1 dùng passphrase/password + PBKDF2HMAC 600k iterations (benchmark), AES-256-GCM; không mặc định PIN 4 chữ số | **OPEN**; FR-14 |
| DEC-11 | HĐH release? | Test Windows & Ubuntu tự động; macOS manual smoke bắt buộc trước claim CST-05 | **OPEN**; Release gate |
| DEC-12 | Thứ tự scope R1/R2? | R1 FR-12 & FR-14; R2 FR-15 & FR-16 | **OPEN**; schedule |
| DEC-13 | Backup/restore? | Tối thiểu tài liệu backup DB+GridFS, restore test staging; in-app export ngoài MVP | **OPEN** |
| DEC-14 | Gia hạn dự án khi phức tạp? | 7 tuần x 16h/người là baseline; cắt R1/R2, không cắt P0 security/data safety | **OPEN** |

## D. Đánh giá lựa chọn kiến trúc

| Phương án | Tốc độ làm MVP | Rủi ro | Khả năng scale | Quyết định |
|---|---:|---|---|---|
| Tkinter gọi thẳng PyMongo trong event handler | Nhanh ban đầu | Treo UI, khó test, business rule phân tán | Kém | Không chọn |
| Desktop 3-layer CRUD nhưng hard-bind MongoDB | Nhanh | Domain/test gắn DB chặt | Trung bình | Không ưu tiên |
| **Desktop Modular Monolith + Hexagonal Ports/Adapters** | **Phù hợp 5 người** | Cần discipline interface/gate | **Tốt (thay persistence/UI, chèn API sau)** | **Đề xuất chọn** |
| Microservices từ đầu + gateway/auth/queue | Chậm | Over-engineering, hạ tầng CI/CD cao | Cao nhưng không cần | Không chọn MVP |

## E. Những điều KHÔNG nên tự đưa vào bản phát hành đầu

- Login/SSO, phân quyền multi-tenant, chia sẻ và realtime collaboration, mobile app, AI/LLM, SaaS.
- MongoDB Sharding, Kafka, Celery/Redis, distributed scheduler khi chưa có backend và lưu lượng thực tế.
- Mã hóa tất cả dữ liệu bằng một master-key tự sinh nhưng không có cơ chế backup/recovery key.
- Kết luận chính xác các KPI 2s, 200ms, RAM/FPS khi chưa benchmark.

## F. Cách quản lý thay đổi SRS

Change Request tối thiểu: `CR-ID`, FR/NFR nguồn, trước/sau, mục tiêu, lựa chọn thay thế, ảnh hưởng kỹ thuật & estimate, tác động test, người phê duyệt, ngày quyết định. PM chỉ mở sprint với DEC liên quan đã xử lý. Không thay đổi baseline im lặng trong PR.
