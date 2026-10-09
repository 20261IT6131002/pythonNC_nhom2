# NOTE APP — HỒ SƠ TRIỂN KHAI CHO TEAM 5

> Phiên bản hồ sơ: 0.9 — bản đề xuất để review/chốt yêu cầu, ngày 09/10/2026.  
> Tài liệu gốc: **SRS Ứng Dụng Ghi Chú.docx**, 27 trang, 16 FR, 4 NFR-PERF, 3 NFR-SEC, 5 CST.  
> **Chưa có xác nhận của Product Owner/Giảng viên; không xem đề xuất trong bộ này là yêu cầu đã được phê duyệt.**

## Dùng file nào để làm việc gì?

| File | Người đọc chính | Công dụng / đầu ra |
|---|---|---|
| `01_SRS_AUDIT_AND_DECISIONS.md` | PM, BA, Tech Lead | Mâu thuẫn, rủi ro, quyết định cần chốt (DEC) trước khi coding |
| `02_SRS_V2_OPTIMIZED.md` | Toàn team, người nghiệm thu | Yêu cầu kiểm thử được, phân phạm vi MVP/R1/R2, tiêu chí chấp nhận, quy tắc nghiệp vụ |
| `03_SYSTEM_ARCHITECTURE.md` | Tech Lead, Dev, QA | Sơ đồ C4-like, module, dependency rule, schema/index, workflows, security, hướng scale |
| `04_EXECUTION_PLAN_TEAM5.md` | PM, 5 thành viên | Phân vai, lịch 9 tuần, task theo mốc, phụ thuộc, năng lực, quality gates |
| `05_TEST_STRATEGY_AND_RTM.md` | QA, toàn team | RTM FR→module→test, test case, kiểm thử phi chức năng, release gates |
| `06_IMPLEMENTATION_BACKLOG.csv` | PM, GitHub Projects | Danh sách task nhập board; ước lượng **giờ công**, phụ thuộc, người chính |
| `07_TEAM5_BACKLOG_TRACKER.xlsx` | PM, Team 5 | Tracker Excel có tính tổng giờ, capacity và buffer theo owner/tuần |
| `SRS_v2_Optimized.docx` | Giảng viên / stakeholder | Bản Word trình bày SRS v2 dễ đọc, tương ứng file 02 |
| `Architecture_and_Delivery_Team5.docx` | Team / thuyết trình | Kiến trúc minh họa, phân vai, timeline và release gates ở dạng Word |
| `08_ARCHITECTURE_OVERVIEW.*`, `09_SCALE_ROADMAP.*` | Dev, báo cáo | Sơ đồ PNG/SVG, tệp DOT source có thể tái tạo |

## Cách áp dụng ngay

1. **Kickoff 60–90 phút:** đọc mục `DEC-01...` trong file 01, ghi người phê duyệt và quyết định. Chưa chốt thì giữ trạng thái `OPEN`.
2. **Đóng baseline:** cập nhật bảng phạm vi & điều khoản đã quyết vào file 02; không thay đổi FR gốc không có quyết định.
3. **Kỹ thuật:** team thống nhất module boundaries, data contract, DB access trong file 03; chạy architecture gate trước UI/DB implementation.
4. **PM:** nhập file 06 vào tracker, cân tải giờ mỗi người, lock Sprint 1.
5. **QA:** liên kết testcase theo file 05 và yêu cầu PR có kiểm thử; release theo gate.

## Quy mô và giả định lập kế hoạch

- Team **5 người**, mỗi người **~16 giờ/tuần**, **9 tuần** (tổng 720 giờ lý thuyết); đây là **giả định để lập kế hoạch**, không phải dữ liệu người dùng cung cấp.
- Python **3.10+**, Tkinter/ttkbootstrap, MongoDB/PyMongo tiếp tục là ràng buộc đầu vào.
- Bản MVP cho **người dùng cá nhân, một phiên desktop**, không cần authentication nhiều người dùng, cộng tác realtime, payment.
- Phạm vi MVP yêu cầu MongoDB kết nối trong mạng được kiểm soát, có backup; không phát hành app desktop chứa credential MongoDB có quyền rộng.
- Offline ở MVP là **khôi phục bản nháp an toàn**, chưa phải multi-device offline sync hoàn chỉnh.
- Packaging ưu tiên Windows 11; Ubuntu smoke trong CI; macOS test có điều kiện thiết bị/runner. SRS gốc yêu cầu cả 3 hệ điều hành, do đó **chưa thể claim CST-05 đạt** khi chưa test cả 3.

## Thống kê ước lượng hiện tại

Backlog hiện có **58 task / 571 giờ**, tổng capacity giả định **720 giờ**, buffer **149 giờ (~20,7%)**. Đây là estimate chưa có xác nhận năng lực và chỉ phản ánh phạm vi các task đã liệt kê. Tỷ lệ theo từng người có thể khác nhau; cần cân lại trong planning.

## Sản phẩm mong muốn ở cuối MVP

Tạo/sửa/xóa an toàn; danh mục; mức ưu tiên; tìm kiếm & lọc & sort; ảnh <=10 MB; lịch nhắc trong phiên đang chạy; lưu nháp khôi phục khi mất mạng; kiểm thử nghiệp vụ và môi trường kiểm thử tái lập. R1 bổ sung pin, mã hóa ghi chú, polish; R2 export & thống kê, tùy theo thời gian.

**Nguyên tắc:** Giữ đủ yêu cầu gốc trong baseline; tất cả thay đổi ưu tiên, kỹ thuật, KPI đều có mã/nhãn **Đề xuất** và Decision Log. Không ghi 'đã đạt' khi chưa đo.
