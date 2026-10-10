# AGENTS.md — NOTEAPP TEAM 5: BASE ENGINEERING RULE

> **Áp dụng:** toàn repo `20261IT6131002/pythonNC_nhom2`, các AI coding agents (Codex/Cursor/Claude) và lập trình viên.  
> **Baseline:** `develop` tại `339ca282a1a80a0698e8922a82187fa1fc9b9508` (09/10/2026). Kiểm tra lại `git status`, `git log -1`, cây thư mục trước khi làm.  
> **Trạng thái:** quy tắc **đề xuất chờ team review**; không tự nhận các quyết định SRS đang OPEN là đã được duyệt.

## 0. Contract của agent — đọc trước khi viết code

1. **Đọc theo thứ tự:** `AGENTS.md` → `docs/BASE_RULES.md` → `docs/srs/phase 1/PHASE1_FOUNDATION_CRUD.md` → `docs/NoteApp_Team5_Blueprint/02_SRS_V2_OPTIMIZED.md` → `docs/NoteApp_Team5_Blueprint/03_SYSTEM_ARCHITECTURE.md` → `docs/NoteApp_Team5_Blueprint/01_SRS_AUDIT_AND_DECISIONS.md`.
2. **Đầu mỗi task:** nêu ID task, FR/NFR/CST/DEC liên quan, phạm vi file, dependency, AC và test dự kiến; kiểm tra nhánh/dirty tree. Nếu thiếu quyết định nghiệp vụ quan trọng, đánh dấu `BLOCKED/ASSUMPTION`; không tự mở rộng scope.
3. **Một PR giải quyết một lát cắt rõ ràng.** Chỉ sửa file cần thiết; không refactor lan sang module khác, không thêm framework và không đổi kiến trúc vì tiện code.
4. **Không tạo code giả có vẻ hoàn thành:** cấm `pass`, `...`, `NotImplementedError` ở code được quảng bá là đã hoàn thiện; scaffold được giữ với TODO gắn issue, không báo chức năng đã chạy.
5. **Mỗi thay đổi hành vi phải kèm tests.** Không xóa/skip/xdisable test để làm CI xanh. Nếu không chạy được Mongo/GUI, nêu chính xác bài test nào chưa chạy và tại sao.
6. **Trước khi kết thúc:** liệt kê file đổi, lệnh chạy và kết quả thực tế, test coverage liên quan, rủi ro mở, hướng rollback. Không tự merge `develop`/`main`, tạo release, thay secrets hoặc phá dữ liệu người dùng.

## 1. Ranh giới kiến trúc — bắt buộc

Hướng dependency: **Presentation → Application → Domain**; `Application` định nghĩa **ports**; `Infrastructure` hiện thực ports; `bootstrap.py` lắp ghép dependency.

| Vùng | Được sử dụng | Cấm |
|---|---|---|
| `src/noteapp/domain/` | stdlib, entity, value object, policy, domain error | `tkinter`, `pymongo`, `bson`, `gridfs`, `infrastructure`, `presentation`, network, file I/O |
| `src/noteapp/application/` | `domain`, DTO, ports/Protocol, use cases | `tkinter`, `pymongo`, `gridfs`, `PIL`, `plyer`, concrete adapters, UI widgets |
| `src/noteapp/infrastructure/` | concrete Mongo/GridFS/config/storage adapters; domain + ports | UI widget/callback; business decision nằm sai tầng |
| `src/noteapp/presentation/tk/` | Tk/ttkbootstrap, presenters/state, **public application use cases/DTO** | raw Mongo query, trực tiếp khởi tạo `MongoClient`, import infrastructure internals |
| `src/noteapp/bootstrap.py` | đọc cấu hình, khởi tạo adapter/use case, inject presenters | nhét quy tắc nghiệp vụ, widget logic, xử lý lỗi bừa bãi |
| `src/noteapp/main.py` | startup, lifecycle, mainloop, shutdown | Mongo CRUD, policy, data migrations bên trong |

- **Không tạo API backend/microservices ở Phase 1.** Port phải hữu ích cho thay UI / thay adapter sau này, nhưng không thêm abstraction chung chung nếu chưa có use case.
- Domain entity không chứa `ObjectId`, Tk widget hoặc BSON data; ID trao đổi với core dưới dạng opaque string/VO; Mongo mapper chuyển tại infrastructure.
- `domain`/`application` phải chạy unit test **không cần MongoDB và không cần màn hình**. Không được import Tk trong package init của core.
- Thay đổi public port/DTO/schema bắt buộc review bởi M1 (architect), liên hệ M3/M4/M2 và cập nhật contract tests + ADR khi thực sự đổi quyết định.

## 2. Luật dữ liệu và hành vi đã có cơ sở

- `title`: trim, từ 1 tới 250 ký tự; không ghi blank. `priority`: `HIGH|MEDIUM|LOW`, so sánh qua rank `3|2|1`, **không** sắp xếp chuỗi alphabet.
- Date/time lưu **timezone-aware UTC**, hiển thị local trong UI; không dùng `datetime.now()` naive để lưu. Inject `Clock` khi logic cần thời gian để test được.
- Note có `id`, `version`, `created_at`, `updated_at`; `CreateNote` cần idempotency key (`client_operation_id`); update dùng `expected_version` để phát hiện conflict.
- Category name chuẩn hóa trim/casefold và unique bằng DB index; canonical reference = `category_id`; không hard-code tên danh mục ở domain.
- Không tin dữ liệu GUI; validate ở application/domain, compile whitelist filters tại repository. Không nhận raw Mongo query/filter/operator từ presentation.
- Thao tác DB thất bại **không được hiển thị `SAVED`**. Trong Phase 1 hiển thị `ERROR/UNSAVED` và giữ nội dung trong editor; chỉ hiển thị `LOCAL_DRAFT` sau khi encrypted draft adapter ghi thành công (Phase 1 chưa cam kết adapter đó).
- Không cài TTL trên `notes.deleted_at`: xóa note phải xử lý GridFS, thùng rác và purge đúng trạng thái ở giai đoạn sau.
- MongoDB credential qua config/runtime; `.env` thật **không commit**; không nhúng URI/password vào desktop binary; dev DB cô lập, remote cần TLS + quyền tối thiểu. Tránh dùng production DB trong tests.
- Ảnh >1 MiB qua GridFS, <=1 MiB inline, giới hạn 10 MiB là nghiệp vụ theo SRS; Phase 1 **không triển khai ảnh**, không viết demo giả. Đừng lưu ảnh trong note text.

## 3. Luật concurrency / Tkinter

- **Tất cả `Tk`, widget, `root.after()` được tạo/gọi từ main UI thread.** Worker không bao giờ cập nhật UI hay gọi `root.after` trực tiếp.
- Các I/O Mongo, filesystem, decode ảnh, scheduler làm trong bounded worker pool; chuyển **DTO/result/error** qua `queue.Queue` đến main-thread `UIEventPump` poll bằng `root.after`.
- Async request có `request_id/sequence` và trạng thái view còn sống; bỏ kết quả đến trễ và không callback vào widget đã destroy. `ThreadPoolExecutor` đóng đúng lifecycle; không sinh daemon thread tự phát mỗi click.
- Hộp thoại lỗi phải diễn giải được; không để exception raw, secrets, stack trace lộ ra UI.
- UI state tối thiểu: `CLEAN → DIRTY → SAVING → SAVED`; lỗi `SAVING → ERROR/UNSAVED`; optimistic conflict → `CONFLICT`. Không giả định nhấn nút Lưu là đã lưu.

## 4. Quy ước layout và naming

Giữ **nguyên cấu trúc `src/noteapp/{domain,application,infrastructure,presentation/tk}` đã scaffold**. Ưu tiên điền logic vào file sẵn có; chỉ tạo file mới nếu có trách nhiệm mới rõ ràng. Tên `snake_case.py`, class `PascalCase`, function `snake_case`, hằng số `UPPER_SNAKE_CASE`, type hints cho public function; hạn chế circular imports và mutable globals. Tests nằm trong `tests/{unit,contract,integration,ui,performance}` đúng cấp độ. Không bỏ file chỉ để “dọn” scaffold khi chưa rõ người phụ trách.

## 5. Git, review, release

- `main`: chỉ bản release đã đạt gate; `develop`: tích hợp; nhánh task `feature/p1-<id>-<slug>`, `fix/p1-<id>-<slug>`, `chore/p1-<id>-<slug>` tạo từ `develop` và tạo PR về `develop`.
- Conventional Commit `feat(core): ...`, `fix(data): ...`, `test(core): ...`, `chore(ci): ...`, `docs(plan): ...`; không commit file generated cache/`.env`/credentials.
- PR phải có: task/FR ID, mục tiêu, ảnh hưởng file/module, cách test, kết quả test thực tế, screenshot/GIF nếu UI, cách rollback, checklist security/data migration. **Ít nhất 1 reviewer khác tác giả**; contract/schema/core boundary cần M1 và owner liên quan review.
- Chỉ merge khi CI chạy thực sự (không phải workflow `echo`), lint/format/unit/architecture gate xanh; integration tests xanh khi thay Mongo adapter.
- Không force-push `develop`/`main`, không merge PR của chính mình nếu chưa review, không tự tạo tag/release trong Phase 1.

## 6. Lệnh chuẩn cần triển khai trong W1

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest -q tests/unit tests/contract
# W2: chạy với NOTEAPP_TEST_MONGO_URI chỉ trỏ DB test
python -m pytest -q tests/integration
```

**Lưu ý:** `pyproject.toml` tại baseline hiện **chưa có** `[project.optional-dependencies] dev`; `ci.yml` chỉ placeholder. Những lệnh trên là **mục tiêu sau khi task P1-03/P1-04 hoàn tất**, không phải lệnh đã xác nhận chạy tại baseline.

## 7. Stop conditions / yêu cầu xác nhận

Dừng và hỏi PM/M1 trước khi: đổi FR Shall/Should/May; biến dự thảo SRS v2 thành APPROVED; thay stack Python/Tkinter/MongoDB; triển khai public Mongo/remote service; lưu draft plaintext; đổi format lưu dữ liệu không có migration; bật TTL xóa ghi chú; dùng key/PIN cố định; dùng production data hoặc xóa DB; bổ sung authentication, web API, realtime sync, SaaS hoặc microservices ngoài Phase 1.

**Nguồn chuẩn khi có mâu thuẫn:** SRS gốc (yêu cầu đã được người có thẩm quyền duyệt) → Decision Log đã phê duyệt → SRS v2 approved → ADR approved → kế hoạch sprint → hướng dẫn code. Các đề xuất còn OPEN là giả định, không được tự nâng thành yêu cầu đã duyệt.
