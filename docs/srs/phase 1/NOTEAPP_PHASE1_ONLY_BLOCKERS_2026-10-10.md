# NoteApp — Báo cáo chỉ các blocker còn mở (Phase 1 Foundation)

- **Repo:** `20261IT6131002/pythonNC_nhom2`
- **Branch:** `feature/foundation`
- **HEAD đã kiểm tra:** `02690ff5c10a6e0653c6cc3de6a7d1c2903d3ed1`
- **Ngày rà soát:** 10/10/2026
- **Phạm vi:** Chỉ những tồn đọng kỹ thuật/quality gate chưa được xác nhận hoặc chưa được khắc phục trên GitHub.
- **Đã loại khỏi báo cáo:** ADR/DEC, ký duyệt yêu cầu, UAT và các mục review mà người dùng xác nhận **đã chốt duyệt**; các module intentionally deferred sang Phase 2.

> **Nhận định:** Chưa phát hiện blocker CRUD logic mới được chứng minh chỉ bằng đọc source. Có 01 release/merge quality gate P0 cần kiểm chứng, 01 khoảng trống kiểm thử E2E và 02 vấn đề nhất quán tài liệu cần khắc phục. Bản thân kết quả `97 passed` được ghi trong `docs/testing/PHASE1_IMPLEMENTATION.md` là **bằng chứng local do branch tự báo cáo**, không phải GitHub Actions run.

## Tóm tắt blocker

| ID | Ưu tiên | Trạng thái | Blocker được xác minh | Owner đề xuất |
|---|---|---|---|---|
| BLK-01 | **P0 — chặn merge** | OPEN | Chưa có Pull Request từ `feature/foundation` và GitHub Actions run tương ứng; không có bằng chứng CI remote pass | M5 + M1 |
| BLK-02 | **P1 — chặn quality gate E2E nếu yêu cầu CI bao phủ** | OPEN | `tests/integration/test_desktop.py` không được chạy bởi workflow hiện tại: Linux loại `ui`; Windows chỉ chạy `tests/ui` | M5 + M2/M4 |
| BLK-03 | **P1 — quy tắc AI/Developer không truy xuất được** | OPEN | `AGENTS.md` trỏ đến `docs/engineering/BASE_RULES.md` và `docs/plans/PHASE1_FOUNDATION_CRUD.md`, nhưng các file thật nằm ở `docs/BASE_RULES.md` và `docs/srs/phase 1/PHASE1_FOUNDATION_CRUD.md` | M1 |
| BLK-04 | **P1 — thiếu nguồn theo dõi task chuẩn** | OPEN | Kế hoạch tham chiếu `PHASE1_TASK_BOARD.md` như file thật nhưng file không tồn tại trong cây `feature/foundation` | M1 + M5 |

## BLK-01 — Chưa có remote CI verification

**Bằng chứng:** Tại commit nêu trên, GitHub Actions API trả về `total_count = 0` khi lọc branch `feature/foundation`; GitHub PR API trả về danh sách rỗng đối với `head=20261IT6131002:feature/foundation`. `.github/workflows/ci.yml` chỉ chạy trên `push` vào `main/develop`, `pull_request` nhắm `main/develop` hoặc `workflow_dispatch`: push riêng feature **không tự kích hoạt** CI. Không thể coi đây là lỗi CI đã fail; đúng hơn là **CI chưa được chạy/kiểm chứng từ GitHub**.

**Cách gỡ:**
1. Tạo Draft PR `feature/foundation` → `develop` (không merge trước khi gate pass).
2. Chờ CI chạy trên sự kiện `pull_request`; kiểm tra ba job `quality`, `integration`, `windows-ui`.
3. Với mỗi job, lưu run URL, SHA, thời điểm và kết luận; xử lý failure nếu có.
4. Nếu P1-AC12 vẫn yêu cầu negative pipeline test, tạo thay đổi thử nghiệm trên branch/PR riêng để xác minh lỗi Ruff/pytest khiến status đỏ, sau đó revert và bảo đảm xanh trở lại.

**Điều kiện đóng:** PR đã chạy và **tất cả required checks xanh tại HEAD**, có links kết quả; không chấp nhận chỉ log chạy local.

## BLK-02 — Thiếu Desktop ↔ Mongo E2E trên workflow

**Bằng chứng source:**
- `.github/workflows/ci.yml`: `integration` chạy `python -m pytest -q tests/integration -m "not ui"`, loại các bài test có marker `ui`.
- `tests/integration/test_desktop.py` có cả `pytest.mark.integration` **và** `pytest.mark.ui`, trong đó kiểm thử create→restart→edit, lỗi kết nối và launcher bằng process riêng.
- `windows-ui` chỉ chạy `tests/unit tests/contract tests/ui`, **không** gọi `tests/integration/test_desktop.py`.

**Tác động:** CI có thể xanh nhưng không hề kiểm tra luồng desktop thực tế lưu và mở lại từ Mongo. Báo cáo nhánh cho biết các scenario này pass local trên Windows; đây không thay thế kiểm chứng CI nếu project gate yêu cầu.

**Cách gỡ khuyến nghị:** Bổ sung stage Linux `xvfb-run` có Mongo service để chạy riêng `tests/integration/test_desktop.py`; hoặc dùng Windows self-hosted runner có Mongo và display hoạt động. Không cần đổi code nghiệp vụ. Giữ job Windows UI hiện tại để bảo đảm giao diện Windows.

Ví dụ ý tưởng cho CI Linux (cần điều chỉnh dependency Tk/Xvfb của runner):

```yaml
- name: Install virtual display dependencies
  run: sudo apt-get update && sudo apt-get install -y xvfb python3-tk
- name: Desktop + real Mongo E2E
  env:
    NOTEAPP_REQUIRE_UI: "1"
  run: xvfb-run -a python -m pytest -q tests/integration/test_desktop.py
```

**Điều kiện đóng:** job E2E thực sự execute (không `SKIPPED`), pass trên CI với Mongo thật, lưu log xác minh 3 kịch bản.

## BLK-03 — Đường dẫn quy tắc trong AGENTS.md sai

**Bằng chứng:** `AGENTS.md` dòng 9 yêu cầu đọc `docs/engineering/BASE_RULES.md` và `docs/plans/PHASE1_FOUNDATION_CRUD.md`. Tree của `feature/foundation` chỉ có `docs/BASE_RULES.md` và `docs/srs/phase 1/PHASE1_FOUNDATION_CRUD.md`.

**Cách gỡ:** Chỉ sửa đường dẫn trong `AGENTS.md` (tránh duplicate tài liệu):

```markdown
1. `AGENTS.md`
2. `docs/BASE_RULES.md`
3. `docs/srs/phase 1/PHASE1_FOUNDATION_CRUD.md`
4. `docs/NoteApp_Team5_Blueprint/02_SRS_V2_OPTIMIZED.md`
5. `docs/NoteApp_Team5_Blueprint/03_SYSTEM_ARCHITECTURE.md`
6. `docs/NoteApp_Team5_Blueprint/01_SRS_AUDIT_AND_DECISIONS.md`
```

**Điều kiện đóng:** tất cả file/path được dẫn chiếu từ `AGENTS.md` tồn tại trên branch và không còn path lỗi.

## BLK-04 — Thiếu PHASE1_TASK_BOARD.md được plan tham chiếu

**Bằng chứng:** `docs/srs/phase 1/PHASE1_FOUNDATION_CRUD.md` dòng 215 liên kết tới `PHASE1_TASK_BOARD.md` cùng thư mục, nhưng tree nhánh không có file đó; `docs/testing/PHASE1_IMPLEMENTATION.md` cũng xác nhận task board absent và mapping theo ID có phần provisional.

**Cách gỡ:** Commit bản task board đã chốt (hoặc sửa liên kết thành vị trí file tracker thật, **nếu** team đã dùng tài liệu khác làm source of truth). Không dựng lại task ID hoặc owner theo suy đoán.

**Điều kiện đóng:** link task board hoạt động; 20 mã P1-01…P1-20 có owner, reviewer, AC, bằng chứng và trạng thái thực tế; mapping trong implementation report không còn provisional.

## Thứ tự xử lý nhanh

1. **M1** sửa `AGENTS.md` và bổ sung/chỉnh link task board trên feature branch.
2. **M5** bổ sung E2E workflow và/hoặc xác định chính xác gate chấp nhận thay thế (nếu đã được nhóm phê duyệt thì có thể đóng BLK-02 bằng bằng chứng tương đương; **không claim CI E2E**).
3. Tạo Draft PR vào `develop`; sau đó xử lý mọi CI failure thực tế nếu xảy ra và lưu link các checks.
4. Chỉ merge khi điều kiện đóng các blocker *áp dụng* đã có bằng chứng.

**Lưu ý không đưa thành blocker độc lập:** compare API báo nhánh `ahead_by=11`, `behind_by=1` so với `develop`; chưa có bằng chứng merge conflict hoặc bắt buộc up-to-date. Việc đồng bộ branch chỉ cần xử lý nếu PR yêu cầu cập nhật hoặc phát sinh conflict.

## Đường dẫn nguồn để xác minh

- Branch: https://github.com/20261IT6131002/pythonNC_nhom2/tree/feature/foundation
- Workflow: https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/foundation/.github/workflows/ci.yml
- E2E tests: https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/foundation/tests/integration/test_desktop.py
- Rules: https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/foundation/AGENTS.md
- Plan: https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/foundation/docs/srs/phase%201/PHASE1_FOUNDATION_CRUD.md
- Implementation evidence: https://github.com/20261IT6131002/pythonNC_nhom2/blob/feature/foundation/docs/testing/PHASE1_IMPLEMENTATION.md

## Cập nhật xử lý

Báo cáo trên giữ nguyên kết quả rà soát tại HEAD `02690ff`. Kết quả sửa và
bằng chứng mới nằm trong [hồ sơ xử lý blocker](../../testing/PHASE1_BLOCKER_FIXES_2026-10-10.md).
BLK-04 được hoãn theo yêu cầu trực tiếp của người dùng trong lúc đang lập kế hoạch;
không tự dựng task board hoặc suy đoán owner/reviewer.

Đã xác minh [PR #2](https://github.com/20261IT6131002/pythonNC_nhom2/pull/2) và
[CI run 38018848284](https://github.com/20261IT6131002/pythonNC_nhom2/actions/runs/38018848284)
pass cả bốn job tại SHA `96f5ec9`; log integration xác nhận **3 E2E passed, skipped=0**.
BLK-01/02/03 đã có bằng chứng xử lý; trạng thái OPEN ở bảng đầu là snapshot trước
khi sửa, không phải trạng thái hiện tại. BLK-04 vẫn hoãn theo yêu cầu người dùng.
