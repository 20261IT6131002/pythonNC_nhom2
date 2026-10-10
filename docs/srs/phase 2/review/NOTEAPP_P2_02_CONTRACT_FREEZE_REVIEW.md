# NoteApp — Tech Lead Review: P2-02 Contract Freeze

- **Ngày kiểm tra:** 10/10/2026
- **Repository:** `20261IT6131002/pythonNC_nhom2`
- **Nhánh:** `feature/p2-02-contract-freeze`
- **HEAD đã kiểm tra:** `1df944ca14d652853db8ed0354f84f040fcf16e8`
- **Base đối chiếu:** `develop` tại `16b4897eca1abd6e88870cc16d511c339a0efb20`
- **Compare:** ahead 2, behind 1 (diverged); 10 file Markdown mới, **không đổi production Python/CI**.
- **Kết luận:** **REQUEST CHANGES / chưa đóng P2-02**. Có thể dùng tài liệu làm đầu vào review và phát triển các phần không phụ thuộc vào các giá trị chưa đối chiếu. Chưa gọi là `Accepted/Frozen`.

## 1. Phạm vi và điểm đạt

1. Có ADR-0002, `PHASE2_PUBLIC_CONTRACTS.md`, `PHASE2_DATA_MIGRATION.md`, task board, hồ sơ review và đối chiếu plan.
2. Phân định rõ `SearchRepository` và `TrashRepository`; không sửa `NoteRepository`, `Note`, `NoteView`, các use case Phase 1. Giữ Hexagonal boundaries.
3. Search đi theo MongoDB `$text` với `title` và **`content_plain`** khớp schema hiện hữu; DTO typed; whitelist sort; phân trang bằng keyset + fingerprint.
4. Trash có hợp đồng CAS theo ID+version+state, xác nhận xóa vĩnh viễn, chống thao tác đua, bảo vệ note/ảnh chưa có cleanup adapter.
5. Có đề xuất schema v2 lazy tombstone, không backfill/xóa index, không TTL tự xóa notes, có dry-run và rollback giữ dữ liệu.
6. Báo cáo ở nhánh ghi nhận **143 tests passed**, **97% statement coverage** của core *hiện hữu* trên máy Windows. Tôi **chưa trực tiếp chạy lại** các lệnh này; không được diễn giải là Search/Trash đã được test hoặc hiện thực.

## 2. Findings cần xử lý

| ID | Ưu tiên | Vấn đề xác minh | Tác động | Chấp nhận khi |
|---|---|---|---|---|
| CF-01 | **P1 / chặn đóng Contract Freeze** | ADR-0002 bảng A2-Q01/Q02/Q03, A2-T01/T02, A2-D01/P01 vẫn là **assumption**, không gắn **giá trị cụ thể** của P2-01/DEC-02/07/09. | M3 có thể code một cách, M4 tạo index/adapter cách khác, M2 UI khác kỳ vọng; không đủ cơ sở freeze. | Điền links/giá trị từ quyết định **đã chốt**, giải quyết từng assumption bằng `MATCHED`, `ADJUSTED` hoặc `DEFERRED`, cập nhật 1 nguồn canonical. **Không yêu cầu họp duyệt lại quyết định cũ.** |
| CF-02 | **P1 / chặn đóng W3 nếu AC14 bắt buộc** | `P2-12` retention 30 ngày trong task board/RTM P2-AC14 nằm phạm vi W3, nhưng ADR/PHASE2_DATA_MIGRATION nói tự động retention **disabled pending W4 cleanup**. | Có thể merge partial feature nhưng không được claim toàn Phase 2/AC14 đạt; mâu thuẫn gate. | Phân định rõ `manual text-only purge = W3`, `automatic retention = W4` **kèm CR/carry-over phù hợp baseline**; hoặc giao triển khai auto retention với quy trình an toàn. Đồng bộ task board, RTM và DoD. |
| CF-03 | **P1 / chặn merge PR** | Chưa có PR và GitHub Actions run tại HEAD `1df944c`; báo cáo hiện là local-only. | Không có bằng chứng remote checks đối với SHA đang review. | Tạo PR vào `develop`, đồng bộ base nếu cần, tất cả required jobs xanh tại HEAD, reviewer đọc diff và xác nhận. |
| CF-04 | **P2 / cross-platform risk** | `SearchNotes(..., local_timezone: tzinfo)` yêu cầu timezone có DST, trong khi P2-04 mới **giao** việc tìm timezone hệ điều hành và không đưa chiến lược cụ thể cho Windows/IANA tzdata. | Dùng `datetime.now().astimezone().tzinfo` có thể chỉ là fixed offset; kết quả lọc ngày sai trên DST/historical zones. | Mô tả nguồn IANA ZoneInfo khả dụng trên Windows, phương án `tzdata`/fallback fail-closed, test hai ngày 23h/25h và DST ambiguous/nonexistent midnight. |
| CF-05 | **P2 / tài liệu** | ADR-0002, task board và review record ghi nhánh `docs/p2-02-contract-freeze`, trong khi nhánh remote thực tế là `feature/p2-02-contract-freeze`. | Reviewers/agent dễ checkout/PR nhầm. | Sửa nhãn nhánh và nguồn commit trong tài liệu, hoặc chú thích rõ nhánh nguyên thủy và nhánh đích. |
| CF-06 | **P2 / reproducibility** | Tool kiểm tra declaration `.venv/tools/p2_02_contract_check.py` trong review record là ignored, không commit. | CI không tái chạy được 5-block compile/link/contract check theo báo cáo trên clean checkout. | Đưa kiểm tra quan trọng vào `tests/contract/` hoặc `scripts/` có tracking, hoặc ghi rõ chỉ là kiểm tra một lần và không lấy làm CI gate. |
| CF-07 | **P2 / query performance proof** | CATEGORY sort cần `$lookup` tới `categories.name_key`, nhưng index trên `notes.category_id` không thể tự bảo đảm sorted category-name query, nhất là kết hợp `$text` + keyset. Contract có acknowledge EXPLAIN ở P2-06, chưa có execution strategy. | Rủi ro nặng query/aggregation với 10k notes; chưa có cơ sở PASS NFR-PERF-02 `<200ms`. | P2-05/06 có prototype/truy vấn cụ thể, `explain`, bộ seed 10k và mẫu tìm tiếng Việt + category sort, fallback kế hoạch tối ưu nếu cần. **Không cần sửa runtime ở P2-02**. |

### Ghi chú phân loại

- CF-01 và CF-02 là **blocker đối với việc đóng hợp đồng/đánh dấu Phase 2 đạt theo kế hoạch**, không phải bug runtime đã tái hiện.
- CF-03 là **required workflow gate**, không phải CI failed.
- CF-04..07 là nợ thiết kế/QA nên ghi cụ thể cho task tiếp theo; ưu tiên giải quyết sớm để tránh đổi contract sau khi M2/M3/M4 đã code.
- Quyết định ADR/DEC/UAT từ Phase 1 hoặc đã được người dùng xác nhận không cần duyệt lại; chỉ cần ánh xạ **giá trị thực tế** để team sử dụng thống nhất.

## 3. Phân định phạm vi công việc

| Task | Có thể bắt đầu? | Ràng buộc |
|---|---|---|
| P2-03 DTO và validation chung | **Có điều kiện** | Chỉ triển khai phần đã xác định, không hardcode các giả định A2-Qxx |
| P2-04 filter/timezone | **Có điều kiện** | Gắn chính sách date/timezone đã chốt và DST tests |
| P2-05 Mongo text index spike | **Có** | Bắt buộc có mẫu kỳ vọng từ DEC-07 trước khi freeze tokenizer/index options |
| P2-06 Mongo query | **Sau P2-03/04/05** | Thiếu phương pháp verified để làm category sort + `$text` + cursor |
| P2-07 Search UI | **Có thể mock song song** | Dùng DTO/enum canonical, không phụ thuộc query thật |
| P2-09/10 Trash core | **Có điều kiện** | Fix semantics Conflict/idempotency, retention and timestamp |
| P2-11/12 Trash adapter/retention | **Sau freeze lifecycle** | Strict CAS; unknown attachment/locked payload fail-closed, no notes TTL |
| P2-15..18 QA | **Viết test từ đầu song song** | Chưa claim green khi chưa có actual implementation |

## 4. Hướng sửa tối thiểu trên nhánh hiện tại

1. Trong `docs/adr/0002-phase2-query-trash-contract.md`: thêm cột `Agreed value / P2-01 evidence link` và trạng thái từng A2-*; các giá trị chưa có thì ghi BLOCKED theo task, không tự giả định để close ADR.
2. `docs/architecture/PHASE2_PUBLIC_CONTRACTS.md`: cập nhật rõ semantics đã chốt cho category, date, text, trash; thêm timezone/Windows test ownership và performance validation cho category lookup+text.
3. `docs/architecture/PHASE2_DATA_MIGRATION.md` và `docs/srs/phase 2/05_TEST_RTM_ACCEPTANCE.md`: chốt ranh giới W3 manual purge versus W4 retention hoặc đủ năng lực xử lý retention W3; không xóa FR/AC của SRS.
4. Sửa metadata branch trong `docs/adr`, `docs/srs/phase 2/02_PHASE2_TASK_BOARD.md`, `docs/testing/PHASE2_P2_02_REVIEW.md`.
5. Tạo PR `feature/p2-02-contract-freeze` → `develop`, chạy CI; ưu tiên reviewer M2, M3, M4, M5 kiểm tra từng contract (không tự approve).

**Exit gate P2-02:** ADR `Accepted`, bộ `P2-CONTRACT-1` không có assumption mâu thuẫn hoặc không có owner quyết định, PR/CI HEAD xanh, tài liệu ánh xạ chính xác P2-01 và P2-AC. Đây là gate để bắt đầu các task phụ thuộc mà không gây rework.

## 5. Source links

- [Nhánh review](https://github.com/20261IT6131002/pythonNC_nhom2/tree/feature/p2-02-contract-freeze)
- [So sánh với develop](https://github.com/20261IT6131002/pythonNC_nhom2/compare/develop...feature/p2-02-contract-freeze)
- [ADR-0002](https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/p2-02-contract-freeze/docs/adr/0002-phase2-query-trash-contract.md)
- [Public Contracts](https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/p2-02-contract-freeze/docs/architecture/PHASE2_PUBLIC_CONTRACTS.md)
- [Data Migration](https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/p2-02-contract-freeze/docs/architecture/PHASE2_DATA_MIGRATION.md)
- [Task Board](https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/p2-02-contract-freeze/docs/srs/phase%202/02_PHASE2_TASK_BOARD.md)
- [Review Evidence](https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/p2-02-contract-freeze/docs/testing/PHASE2_P2_02_REVIEW.md)

## 6. Theo dõi sau review

Nội dung trên giữ nguyên snapshot review tại `1df944c`, không phải xác nhận
reviewer đã chấp thuận các fixes. Bảng xử lý CF-01..07, kết quả kiểm tra thực tế
và các gate còn mở nằm trong
[follow-up evidence](../../../testing/PHASE2_P2_02_REVIEW.md).
Read-only verification mới tìm thấy PR #5 đã mở nhưng base `feature/phase-2`
nằm ngoài CI trigger; không diễn giải CF-03 thành CI failed. CF-01 tiếp tục cần
đối chiếu concrete values/artifact của quyết định đã chốt, không duyệt lại.
