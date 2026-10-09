# SRS v2.0 — ỨNG DỤNG QUẢN LÝ GHI CHÚ CÁ NHÂN

**Trạng thái:** DRAFT FOR REVIEW / đề xuất kỹ thuật và phạm vi.  
**Nguồn:** SRS gốc 27 trang, FR-01..FR-16, NFR-PERF-01..04, NFR-SEC-01..03, CST-01..05.  
**Biên soạn:** System Designer + PM review, 09/10/2026.  
**Quy ước:** `[G]` giữ ý nghĩa yêu cầu gốc; `[ĐX]` thay đổi/bổ sung; `[PENDING]` chờ người có thẩm quyền duyệt. Chỉ bản approved được coi là baseline nghiệm thu.

## 1. Mục tiêu & phạm vi

### 1.1 Mục tiêu sản phẩm
- Tạo, tổ chức, tìm kiếm và theo dõi ghi chú cá nhân trên máy tính bằng giao diện 3 vùng, dễ sử dụng, ổn định khi I/O chậm.
- Lưu chính trên MongoDB; hỗ trợ ảnh, nhắc việc khi ứng dụng hoạt động, giảm nguy cơ mất nội dung chưa lưu.
- Codebase tách domain độc lập UI/storage để bổ sung web/API, đồng bộ, hoặc thay database trong giai đoạn sau.

### 1.2 Bối cảnh/người dùng [G]
Một người sử dụng tại một phiên desktop; nhóm nhân viên văn phòng, sinh viên/nghiên cứu, kỹ thuật viên. V1 không bao gồm làm việc cộng tác realtime, SaaS multi-tenancy, thanh toán.

### 1.3 Ràng buộc [G]
CST-01 Python 3.10+; CST-02 Tkinter + ttkbootstrap; CST-03 UI Tk main thread, I/O >100ms ở worker; CST-04 Mongo BSON <=16MB, ảnh <=1MB inline BinData, >1MB qua GridFS; CST-05 Windows 10/11, Ubuntu 22.04 LTS, macOS Sonoma+ cần xác minh tương thích.

### 1.4 Phân pha đề xuất [ĐX/PENDING]

| Pha | Mục tiêu | Yêu cầu nguồn |
|---|---|---|
| MVP / Release 0.1 | Luồng ghi chú end-to-end, không làm mất dữ liệu, testable | FR-01..11 (Shall gốc), **FR-13 soft-delete promote P0 đề xuất**, NFR bảo mật/cứu bản nháp, CST |
| R1 / Release 0.2 | Trải nghiệm và an toàn nâng cao | FR-12, FR-14 (Should gốc), hardening, packaging |
| R2 / Release 0.3 | Xuất bản và báo cáo | FR-15, FR-16 (May gốc), multi-attachment nếu được duyệt |

**Quy tắc:** Việc chia pha không xóa yêu cầu gốc. Bất kỳ trì hoãn FR Shall nào làm MVP không đủ scope phải thông qua CR.

## 2. Mô hình nghiệp vụ & dữ liệu

### 2.1 Đối tượng
- `Note`: id, title, content, category_id, priority, is_pinned, timestamps, deletion state, reminder state, locking state, image pointer, version.
- `Category`: id, normalized name, display name, color_hex, description, timestamps.
- `Attachment`: metadata ảnh, inline bytes hoặc GridFS file_id, hash, validation status. MVP tối đa một ảnh/note `[ĐX/PENDING]`.
- `LocalDraft`: note_id hoặc draft_id, revision/base_version, encrypted payload, updated_at, sync/recovery state; chỉ lưu máy người dùng `[ĐX]`.

### 2.2 Quy tắc nghiệp vụ (BR)

| Mã | Quy tắc kiểm thử được |
|---|---|
| BR-01 [G] | Tiêu đề sau trim dài **1..250** ký tự; không được rỗng. |
| BR-02 [G+ĐX] | Timestamps lưu UTC, render theo timezone của OS; kiểm tra range khi chuyển đổi. |
| BR-03 [G] | Priority thuộc `{HIGH, MEDIUM, LOW}`; sort theo thứ tự này, không theo lexical. |
| BR-04 [G+ĐX] | Category name unique sau chuẩn hóa (trim, casefold); note không có danh mục dùng trạng thái `Uncategorized`, không để trường bắt buộc mâu thuẫn. |
| BR-05 [G] | Ảnh chỉ `png`, `jpeg/jpg`, `webp`, tối đa **10 MiB**; <=1 MiB inline, >1 MiB đến 10 MiB GridFS. MIME phải kiểm tra bytes, không tin extension. |
| BR-06 [ĐX/PENDING] | Một ảnh tại một thời điểm; thay ảnh phải dọn tham chiếu cũ có kiểm soát. |
| BR-07 [G+ĐX/PENDING] | Xóa thường = chuyển Thùng rác, ghi `deleted_at`; xóa vĩnh viễn cần xác nhận, xử lý cả blob. |
| BR-08 [G+ĐX] | Các query mặc định không trả note đã xóa; trash không xuất hiện trong search/dashboard. |
| BR-09 [ĐX/PENDING] | Khi chưa thể lưu Mongo, bản nháp mã hóa lưu bền vững local với trạng thái `LOCAL_DRAFT`; không tự khẳng định đã `SAVED`. |
| BR-10 [ĐX] | Một phiên edit có `version`, tránh stale save ghi đè im lặng; conflict hiện lựa chọn giữ cả hai bản. |
| BR-11 [G+ĐX] | Nhắc chỉ với `active=true`, time UTC trong tương lai lúc tạo; on app open scheduler quét trễ và chống lặp theo best effort. |
| BR-12 [G+ĐX] | Locked note không ghi plaintext vào log/search index/cache tạm không mã hóa, popup notification chỉ ghi thông điệp chung. |
| BR-13 [ĐX/PENDING] | Content tối đa **1 MiB UTF-8** ở MVP để giới hạn memory/BSON; mức này chờ duyệt vì nguồn gốc nói không giới hạn lý thuyết. |
| BR-14 [ĐX] | Tác vụ I/O nền trả result/error envelope, luôn an toàn khi cửa sổ bị hủy trước khi kết quả về. |

## 3. Yêu cầu chức năng có tiêu chí chấp nhận

`P0/P1/P2` dưới đây là **mức ưu tiên triển khai đề xuất**, không thay mức Shall/Should/May gốc.

### FR-01 [G] Tạo ghi chú — Shall / P0
- Input: title, content, category, priority, optional image/reminder.
- **AC-01a:** nhập title trắng hoặc >250 ký tự → không tạo; giữ nội dung đang soạn.
- **AC-01b:** ghi thành công → sinh id, created_at/updated_at UTC, xuất hiện đúng trong list.
- **AC-01c:** gửi lưu khi DB không sẵn → hiển thị chưa đồng bộ và khôi phục được draft sau restart (BR-09, `[ĐX]`).

### FR-02 [G] Chỉnh sửa — Shall / P0
- **AC-02a:** edit chuyển trạng thái `DIRTY`; lưu thành công chuyển `SAVED`, updated_at đổi.
- **AC-02b:** lỗi kết nối không làm mất text; thao tác UI không bị block.
- **AC-02c `[ĐX]`:** khi version DB khác `base_version`, không overwrite âm thầm; tạo conflict notification/copy.

### FR-03 [G] Xóa ghi chú — Shall / P0
- **AC-03a:** xóa thông thường chuyển note sang trash theo DEC-02.
- **AC-03b:** hủy hộp thoại xác nhận hard delete → dữ liệu và ảnh không bị thay đổi.
- **AC-03c:** hard delete thành công → note và ảnh không còn tham chiếu; retry purge khi I/O thất bại.

### FR-04 [G] Danh mục — Shall / P0
- **AC-04a:** tạo/đổi tên danh mục không trùng sau chuẩn hóa; chọn danh mục áp dụng đúng.
- **AC-04b `[ĐX]`:** rename category không khiến category_name của note bị sai; xóa category chuyển notes về Uncategorized hoặc từ chối xóa khi có note (DEC cần chốt).

### FR-05 [G] Ưu tiên — Shall / P0
- **AC-05a:** chỉ nhận HIGH/MEDIUM/LOW; UI màu đỏ/cam/lục theo bản gốc.
- **AC-05b:** sort ưu tiên ra HIGH → MEDIUM → LOW.

### FR-06 [G] Tìm kiếm — Shall / P0
- **AC-06a:** tìm trên title/content được lưu theo token full-text; delay debounce ~300ms.
- **AC-06b:** kết quả cũ đến sau request mới không được hiển thị thay request mới.
- **AC-06c `[ĐX]`:** locked/encrypted content không tìm trong nội dung plaintext; title search theo chính sách bảo mật đã chốt.
- **AC-06d `[PENDING]`:** cần chốt matching có dấu, không dấu, từ ghép tiếng Việt trước UAT.

### FR-07 [G] Lọc ngày — Shall / P0
- **AC-07a:** start_date <= end_date, phạm vi lọc inclusive theo ngày địa phương; chuyển query thành `[start_utc, end_exclusive_utc)`.
- **AC-07b:** kết hợp category, full-text, range cùng lúc; không trả soft-deleted notes.

### FR-08 [G] Ảnh — Shall / P0
- **AC-08a:** 1 MiB inclusive → INLINE; >1 MiB đến 10 MiB inclusive → GRIDFS.
- **AC-08b:** sai MIME/ảnh hỏng/>10 MiB → từ chối, giữ note và ảnh cũ.
- **AC-08c:** hiển thị thumbnail max width 400px, giữ aspect ratio; không block main thread.
- **AC-08d:** khi insert note/attachment lỗi giữa chừng, job cleanup không để orphan GridFS kéo dài quá thời gian reconciliation được chốt.

### FR-09 [G] Cài nhắc — Shall / P0
- **AC-09a:** đặt reminder >now (theo UTC) → lưu active/time; thay lịch reset trạng thái chưa xử lý.
- **AC-09b:** hủy reminder khiến scheduler không phát kỳ đã hủy.

### FR-10 [G] Phát nhắc — Shall / P0
- **AC-10a:** quét mỗi ~30s khi app đang hoạt động, nhắc đến hạn theo best effort, ưu tiên không trùng trong một phiên.
- **AC-10b:** lúc mở lại ứng dụng, note quá hạn được xử lý theo rule missed-reminder đã chốt.
- **AC-10c:** OS notification bị chặn → trạng thái ứng dụng hiển thị retry/failure hợp lý, không claim đã hiển thị notification.

### FR-11 [G] Sắp xếp — Shall / P0
- **AC-11a:** sort theo pinned (nếu bật R1), priority, category, updated_at, created_at theo lựa chọn.
- **AC-11b:** sort được thực hiện bởi repository có index, pagination; không sort toàn bộ >10k records client side.

### FR-12 [G] Ghim — Should / P1
- **AC-12a:** toggle pin/unpin; pinned xuất hiện trước unpinned trong mọi chế độ sort.

### FR-13 [G + ĐX] Thùng rác — Should gốc / **P0 đề xuất**
- **AC-13a:** soft-delete, restore, hard-delete hoạt động với đúng quyền và xác nhận.
- **AC-13b:** policy 30 ngày áp dụng purge scheduler, không dùng TTL trực tiếp nếu GridFS vẫn phụ thuộc note.
- **AC-13c:** phục hồi trước purge hoạt động; không hứa purge đúng đến giây, có cửa sổ xử lý.

### FR-14 [G + ĐX] Ghi chú khóa — Should / P1
- **AC-14a:** trước khi lưu locked note, content mã hóa AES-256-GCM với salt/nonce/KDF params lưu kèm; không lưu plaintext content.
- **AC-14b:** sai passphrase → không giải mã; tampering → auth failed; không crash.
- **AC-14c:** đổi passphrase re-encrypt thành công; không log content/key/PIN.
- **AC-14d `[ĐX]`:** encrypted content bị loại khỏi Mongo `$text` index; không tiết lộ nội dung trong toast/notification.

### FR-15 [G] Export — May / P2
- **AC-15a:** export Markdown giữ UTF-8, ảnh (kèm folder asset), đường dẫn an toàn.
- **AC-15b:** export PDF có font tiếng Việt; lỗi quyền ghi không hỏng note.

### FR-16 [G] Thống kê — May / P2
- **AC-16a:** tổng số active, theo category, theo priority; không tính trash; validate bằng seed DB.
- **AC-16b:** không mô tả là 'tiến độ công việc' nếu không có trạng thái completed; chỉ biểu đồ phân bố notes.

### FR-17 [ĐX] Recovery bản nháp — P0 theo NFR reliability
- **AC-17a:** sau mất Mongo/đóng đột ngột, restart vẫn khôi phục draft gần nhất đã ghi local thành công.
- **AC-17b:** local draft luôn mã hóa ở trạng thái nghỉ bằng khóa OS keyring/credential store; nếu OS keyring không khả dụng, hiển thị rõ rằng secure autosave bị vô hiệu hóa; không silently ghi JSON plaintext.
- **AC-17c:** khi reconnect, người dùng xác nhận lưu; có chống tạo bản ghi trùng qua `client_operation_id`; không mất bản local khi server save fail.

## 4. Use case ưu tiên

| UC | Main path | Exception quan trọng |
|---|---|---|
| UC-01 Create | open new→edit→validate→optional image→save→list refresh | invalid title, DB timeout, orphan upload |
| UC-02 Edit | open note→dirty→save with version→success | concurrent stale save/conflict, close while saving |
| UC-03 Image | choose file→MIME/size validation→thumbnail→persist mode | corrupt/giant/bomb file, GridFS interrupted |
| UC-04 Reminder configure | pick local date/time→UTC→persist | past date/DST ambiguity/invalid zone |
| UC-05 Notify | scheduler due query→claim→notify→record outcome | app closed/permission denied/crash/restart |
| UC-06 Search | debounce→typed criteria→worker→query index→paged cards | stale result, no result, complex Vietnamese query |
| UC-07 Trash | soft-delete→browse→restore or confirmed permanent purge | GridFS fail, expired note, stale UI |
| UC-08 Lock | choose passphrase→derive key→encrypt→save→unlock | wrong passphrase, tampered ciphertext, forgotten passphrase |
| UC-09 `[ĐX]` Local recovery | DB outage→encrypted draft→restart→recover→reconnect | keyring denied, conflicting revision |

## 5. Yêu cầu phi chức năng & điều kiện đo

### 5.1 Hiệu năng

| Mã | SRS gốc | Cách đo / tinh chỉnh đề xuất |
|---|---|---|
| NFR-PERF-01 | startup <2.0s khi 5,000 notes | **Giữ target gốc**; đo `launch→main shell interactive` p95/20 runs, cache cold/warm; không chờ tải toàn bộ notes; report máy/OS/DB |
| NFR-PERF-02 | search <200ms khi 10,000 notes | **Giữ target gốc**; đo DB query time riêng và UI end-to-end p95/100 queries; báo network RTT/seed/index |
| NFR-PERF-03 | >=60 FPS khi scroll | **Giữ làm yêu cầu gốc cần xác minh**; `[ĐX/PENDING]` chuyển metric khả thi: main-thread event delay p95<=50ms & no stall >250ms trong test scroll/search |
| NFR-PERF-04 | RAM <=150MB normal, <=300MB ảnh lớn | **Giữ target gốc**; đo RSS process 15 phút sau warmup tại 5k notes, 30 ảnh mẫu, test Windows + Linux |

**Testbed đề xuất:** i5/Ryzen 5, RAM 8GB, SSD, MongoDB local Docker cùng máy hoặc private LAN RTT <=10ms, dataset 5k/10k note và 1k ảnh; báo rõ trạng thái release nếu số liệu chưa đo. Các ngưỡng mới chỉ hiệu lực khi DEC-09 được phê duyệt.

### 5.2 Security

- **NFR-SEC-01 [G]:** URI không hardcode; `[ĐX]` mật khẩu ứng dụng production lưu bằng keyring/secret injection; không log; TLS bật với Mongo từ xa.
- **NFR-SEC-02 [G]:** AES-256-GCM cho locked content; `[ĐX]` salt 16-byte random, nonce 12-byte unique mỗi lần encrypt, KDF params + version metadata, authenticate before display; test tampering.
- **NFR-SEC-03 [G]:** chống NoSQL injection; `[ĐX]` typed `NoteQuery`, whitelist sort/filter, compile repository filters, không nhận raw `$` dict từ user input.
- **NFR-SEC-04 [ĐX]:** local draft encryption hoặc fail-closed; log scrub, crash report không lộ plaintext.
- **NFR-SEC-05 [ĐX]:** giới hạn upload 10 MiB trước decode, kiểm tra pixel max, chống decompression bomb; hash SHA-256.

### 5.3 Reliability/compatibility

- **NFR-REL-01 [G+ĐX]:** thử kết nối DB có backoff theo số lần (ví dụ 0.5/1/2s + jitter), sau 3 lần chuyển trạng thái Offline, **không** đánh dấu đã save khi chỉ ở draft local.
- **NFR-REL-02 [ĐX]:** lưu dữ liệu idempotent (`client_operation_id`), conflict detection (`version`), graceful termination drains/blocks appropriately.
- **NFR-REL-03 [ĐX]:** weekly backup DB/GridFS ở môi trường demo; thực hiện ít nhất một restore exercise trước release.
- **NFR-PORT-01 [G]:** Windows 10/11, Ubuntu 22.04, macOS Sonoma+; có matrix test Tk widgets, OS notification, icon, assets, paths, package executable; trừ platform chưa test khỏi claim release.
- **NFR-MAIN-01 [G+ĐX]:** domain không import `tkinter`/`pymongo`/`gridfs`/`plyer`; unit tests chạy không cần GUI và MongoDB thật.

## 6. UI/UX contract

- Three-pane sidebar 20% / list 30% / editor 50% `[G]`, có min-width/adaptive khi cửa sổ nhỏ `[ĐX]`.
- Search debounce ~300ms, error/loading/empty/offline states, editor dirty/saving/saved/local-only/conflict labels.
- Shortcut đề xuất: Ctrl+N, Ctrl+S, Ctrl+F, Delete; khi close unsaved/draft có xác nhận.
- Chỉ load một trang notes ban đầu (e.g. 30), scroll paginate; ảnh thumbnail cache bounded.
- Notification locked note che title nếu title nhạy cảm (quyết định privacy cần chốt), tuyệt đối che content.

## 7. Giao diện mô-đun & nguyên tắc kiến trúc

Client-side Presentation → Application Use Cases → Domain → Ports → Persistence Adapter MongoDB / Local Draft Adapter / OS Notification Adapter. Chỉ composition root wiring các implementation. Domain không phụ thuộc Mongo/GUI. Chi tiết trong file `03_SYSTEM_ARCHITECTURE.md`.

## 8. Dữ liệu & lifecycle

- `notes`: `_id`, `title`, `content_plain` **hoặc** `content_encrypted`, category_id, priority, priority_rank, is_pinned, version, reminder, attachment metadata, is_deleted/deleted_at, created_at/updated_at, schema_version.
- `categories`: `_id`, `name`, `name_key`, color_hex, description, timestamps.
- `fs.files`, `fs.chunks` chuẩn GridFS cho ảnh >1MiB.
- `purge_jobs`/state metadata để xử lý cleanup (đề xuất); `client_operation_id` unique trong `notes` cho retry create.
- **Không dùng TTL notes** nếu xóa có đính kèm; purge thực hiện theo state machine và job idempotent.
- Chỉ mục: `{title:'text', content_plain:'text'}` và indexes dashboard/category/reminder; phân biệt locked content và migration.

## 9. Định nghĩa hoàn tất/ngoại lệ

**Definition of Ready:** FR có AC, DEC đã đóng, mẫu UI, data impact, positive/negative test, estimate.  
**Definition of Done:** code reviewed, typed service API, unit+integration tests xanh, no P0/P1 bug mở, tương thích schema, logs scrubbed, demo video/GIF hoặc ảnh chụp màn hình, README cập nhật.  
**Release gates:** smoke create→edit→search→image→reminder→trash→restore; DB disconnect/recovery; test locked note nếu scope R1; backup restore; hiệu năng công bố kèm môi trường; platform matrix.

## 10. Câu hỏi còn mở bắt buộc chốt

DEC-01..DEC-14 trong file 01. Đặc biệt: promote FR-13, giới hạn nội dung, 1 ảnh/note, offline expectation, UX khi app đóng, cơ chế khóa ghi chú, Mongo remote security. Không tự giải quyết bằng cách viết code trước.

## 11. Quản trị yêu cầu và ký duyệt

Baseline ID `SRS-v2.0-DRAFT`; change requests `CR-xxx`; owner PM/BA; approver PO/giảng viên; link each requirement to tests via `05_TEST_STRATEGY_AND_RTM.md`. Bản này là dự thảo tối ưu hóa, **chưa thay thế SRS đầu vào** cho đến khi được chấp thuận.
