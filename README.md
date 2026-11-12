# NoteApp

Ứng dụng ghi chú cá nhân trên desktop, xây dựng bằng **Python, Tkinter/ttkbootstrap
và MongoDB**. NoteApp hỗ trợ tổ chức ghi chú, ảnh đính kèm, nhắc việc, khóa nội dung,
khôi phục bản nháp mã hóa và xuất tài liệu tiếng Việt.

[Bắt đầu](#cài-đặt-và-chạy) · [Cấu hình](#cấu-hình) · [Kiểm thử](#kiểm-thử) ·
[Xử lý sự cố](#xử-lý-sự-cố) · [Tài liệu](#tài-liệu-dự-án)

## Tính năng

| Nhóm | Khả năng hiện có |
|---|---|
| Ghi chú | Tạo, chỉnh sửa, phân trang; phát hiện xung đột phiên bản và chống tạo trùng khi thử lưu lại. |
| Tổ chức | Danh mục, màu sắc, ba mức ưu tiên; ghim ghi chú lên đầu kết quả. |
| Tìm kiếm | Tìm theo token/phrase trong tiêu đề và nội dung; kết hợp danh mục, ưu tiên, khoảng ngày địa phương và sắp xếp. |
| Ảnh | Một ảnh PNG/JPEG/GIF/WebP mỗi ghi chú; tối đa 10 MiB; thumbnail giữ tỷ lệ, rộng tối đa 400 px. |
| Nhắc việc | Đặt, đổi, hủy lịch; xử lý lịch quá hạn khi mở lại ứng dụng. |
| Thùng rác | Xóa mềm, khôi phục và xóa vĩnh viễn có xác nhận; xử lý ảnh theo vòng đời ghi chú. |
| Bảo mật | Mã hóa tiêu đề/nội dung bằng AES-256-GCM; mở khóa trong phiên, đổi cụm mật khẩu và khóa lại khi không hoạt động. |
| Bản nháp | Lưu snapshot mã hóa trên máy, khóa trong credential store của OS; khôi phục có xác nhận khi khởi động lại. |
| Xuất và thống kê | Markdown UTF-8 kèm ảnh, PDF có font tiếng Việt; thống kê ghi chú active theo danh mục và ưu tiên. |

Đây là các chức năng đã có implementation và bằng chứng kiểm thử. Việc nghiệm thu
release vẫn phụ thuộc các gate QA, quyết định SRS và review còn mở;
[SRS v2](docs/NoteApp_Team5_Blueprint/02_SRS_V2_OPTIMIZED.md) hiện là bản dự thảo.

## Yêu cầu môi trường

- **Python 3.10+**; khuyến nghị Python 3.12. QA Windows đã chạy Python 3.11.9.
- **MongoDB 7.0** local; dùng Docker Compose trong repo hoặc MongoDB đã cài sẵn.
- **Desktop có Tkinter**. Trên Ubuntu, cài `python3-tk` nếu Python chưa có Tk.
- Credential store: Windows Credential Manager, macOS Keychain hoặc Linux Secret Service.
  Linux cần desktop notification service để phát thông báo.

CI kiểm tra Python 3.10/3.12, MongoDB, Linux Tk qua Xvfb và Windows UI.
Ma trận native desktop trên mọi OS chưa hoàn tất; xem
[báo cáo QA](docs/testing/QA_SRS_V2_2026-11-13.md) trước khi công bố nền tảng hỗ trợ.

## Cài đặt và chạy

### Windows — PowerShell

Các lệnh dưới đây dành cho môi trường phát triển mới:

```powershell
git clone https://github.com/20261IT6131002/pythonNC_nhom2.git
cd pythonNC_nhom2
git switch develop

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

docker compose -f compose.dev.yml up -d --wait
$env:NOTEAPP_MONGO_URI = "mongodb://127.0.0.1:27017"
$env:NOTEAPP_DB_NAME = "noteapp_dev"

.\.venv\Scripts\python.exe scripts/create_indexes.py
.\.venv\Scripts\python.exe -m noteapp.main
```

Nếu đã có MongoDB local, bỏ qua lệnh Docker và đặt URI đúng cổng đang dùng.
Để thêm dữ liệu mẫu, chạy tùy chọn:

```powershell
.\.venv\Scripts\python.exe scripts/seed_notes.py --count 35
```

### Linux / macOS

Sau khi clone repo và chuyển sang `develop`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"

docker compose -f compose.dev.yml up -d --wait
export NOTEAPP_MONGO_URI="mongodb://127.0.0.1:27017"
export NOTEAPP_DB_NAME="noteapp_dev"

python scripts/create_indexes.py
python -m noteapp.main
```

Sau khi cài package, cũng có thể dùng entry point `noteapp` trong venv
(Windows: `.\.venv\Scripts\noteapp.exe`).

### Dừng MongoDB phát triển

```powershell
docker compose -f compose.dev.yml stop
```

Lệnh này giữ dữ liệu trong named volume `mongo_dev_data`. MongoDB chỉ bind cổng
`127.0.0.1:27017`. Khi dùng DB cũ, đọc phần [Nâng cấp dữ liệu](#nâng-cấp-dữ-liệu)
trước khi mở ứng dụng.

## Cấu hình

Ứng dụng đọc biến môi trường; **không tự nạp file `.env`**.
[`.env.example`](.env.example) liệt kê các biến dùng được. Export biến trong
terminal chạy app; không đưa credential hoặc file `.env` thật vào Git.

| Biến | Mặc định / ý nghĩa |
|---|---|
| `NOTEAPP_MONGO_URI` | Bắt buộc; URI `mongodb://` tới `localhost`, `127.0.0.1` hoặc `::1`. |
| `NOTEAPP_DB_NAME` | `noteapp_dev`; chấp nhận `noteapp_dev`, `noteapp_dev_<suffix>` hoặc `noteapp_test_<suffix>`. |
| `NOTEAPP_MONGO_TIMEOUT_MS` | `3000`; khoảng hợp lệ 100–30000 ms. |
| `NOTEAPP_TIMEZONE` | Tự nhận từ OS; có thể đặt tên IANA, ví dụ `Asia/Ho_Chi_Minh`. |
| `NOTEAPP_REMINDER_POLL_SECONDS` | `30`; khoảng hợp lệ 5–3600 giây. |
| `NOTEAPP_DRAFT_DIR` | Thư mục bản nháp mặc định theo OS; nếu đổi phải là đường dẫn tuyệt đối. |
| `NOTEAPP_ENABLE_RETENTION` | Mặc định tắt; `1` bật purge/reconcile khi app mở, sau khi review an toàn dữ liệu. |

Cấu hình hiện tại chỉ cho phép MongoDB loopback và tên DB phát triển/test nêu trên.

## Sử dụng

### Ghi chú, tìm kiếm và danh mục

- **Ctrl+N** tạo ghi chú, **Ctrl+S** lưu, **Ctrl+F** đưa con trỏ vào ô tìm kiếm.
- Tiêu đề sau trim dài 1–250 ký tự. Chọn mức ưu tiên **Cao / Vừa / Thấp** và danh mục
  trong editor. **Quản lý danh mục** cho phép tạo, đổi tên, đổi màu hoặc xóa.
- Danh mục có tên duy nhất sau chuẩn hóa trim/NFC/casefold. Không xóa được danh mục
  còn ghi chú tham chiếu, kể cả ghi chú trong thùng rác.
- **Tải thêm** lấy trang tiếp theo, mặc định 30 ghi chú. **Ghim / Bỏ ghim** hoặc phím
  **P** trên card đưa ghi chú lên đầu các kết quả phù hợp bộ lọc.
- Tìm kiếm dùng token/phrase của MongoDB, không phải substring. Các test hiện tại
  ghi nhận `học` và `hoc` cùng khớp; ngữ nghĩa tiếng Việt đầy đủ vẫn chờ chốt AC-06d.
- Ngày lọc theo giờ địa phương, dữ liệu thời gian lưu UTC. Trường hợp múi giờ không
  xác định hoặc giờ DST mơ hồ bị từ chối thay vì tự đoán.

Chỉ hiển thị đã lưu sau khi MongoDB xác nhận. Lỗi lưu giữ nội dung trong editor;
xung đột phiên bản cần người dùng giải quyết, không tự ghi đè bản mới trên server.

### Ảnh, nhắc việc và thùng rác

Ảnh được xác minh bằng decode nội dung, giới hạn 25 megapixels và 10 MiB.
Ảnh ≤1 MiB dùng BSON BinData trong `attachment_blobs`; ảnh lớn hơn dùng GridFS.
Thay ảnh chỉ dọn ảnh cũ sau khi cập nhật ghi chú thành công.

Nhập lịch nhắc theo **dd/mm/yyyy, HH:MM**. Nhắc việc chỉ chạy khi ứng dụng đang mở;
khi mở lại, app quét các lịch quá hạn. Delivery là best effort: `DELIVERED` nghĩa là
lời gọi thông báo được chấp nhận, không bảo đảm người dùng đã nhìn thấy banner.
Lỗi gửi được thử lại tối đa 3 lần với khoảng chờ 1 rồi 5 phút; hết lượt vẫn giữ
`ACTIVE`, người dùng có thể đặt lại lịch. Xem cách xử lý Windows ở mục sự cố bên dưới.

**Thùng rác** cho phép khôi phục hoặc xóa vĩnh viễn có xác nhận. Purge sau 30 ngày
là tác vụ opt-in, không dùng TTL trên ghi chú. `scripts/run_retention.py` chỉ báo
số ghi chú đủ điều kiện; `--apply` thực hiện một batch purge và dọn ảnh mồ côi đủ
thời gian chờ. Việc xóa vĩnh viễn không thể hoàn tác bằng Git revert.

### Khóa nội dung và khôi phục bản nháp

Menu **Bảo mật** hỗ trợ khóa ghi chú, mở khóa trong phiên, khóa lại, đổi cụm mật
khẩu và bỏ khóa có xác nhận. Cụm mật khẩu tối thiểu 12 ký tự; quên mật khẩu không
thể khôi phục nội dung. Editor tự khóa lại sau 5 phút không hoạt động.

Tiêu đề/nội dung khóa được mã hóa; danh sách che nội dung và thông báo nhắc dùng
thông điệp chung. **Ảnh đính kèm và metadata không nằm trong phần nội dung mã hóa**;
backup/export cũ có thể vẫn chứa plaintext trước khi khóa.

Bản nháp được snapshot sau khoảng 750 ms không chỉnh sửa, mã hóa trước khi ghi
file và dùng khóa trong credential store của OS. **Bản nháp đã lưu local** khác
với **đã lưu MongoDB**. Khi mở lại, chọn **Bản nháp**, khôi phục nội dung và chủ động
nhấn **Lưu** để gửi lên DB. Snapshot giữ operation ID/base version để tránh tạo
trùng hoặc ghi đè thay đổi từ phiên khác.

Thư mục bản nháp mặc định:

| OS | Đường dẫn |
|---|---|
| Windows | `%LOCALAPPDATA%/NoteApp/drafts/<profile>` |
| macOS | `~/Library/Application Support/NoteApp/drafts/<profile>` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/NoteApp/drafts/<profile>` |

Chỉ một app được ghi vào cùng profile. Giữ ổn định đường dẫn profile và credential
store; mất khóa sẽ không tự tạo khóa thay thế cho ciphertext cũ. Nếu keyring không
khả dụng, app cảnh báo và giữ nội dung trong RAM, không ghi plaintext dự phòng.
Snapshot tối đa 1 MiB serialized UTF-8; thoát đột ngột chỉ khôi phục được snapshot
đã ghi thành công, không bảo đảm giữ các phím gõ trong cửa sổ debounce cuối.

### Xuất tài liệu và thống kê

Lưu ghi chú rồi chọn **Xuất ghi chú → Markdown và ảnh** hoặc **PDF**, sau đó chọn
thư mục đích đã tồn tại. App tạo thư mục `note-<id>` riêng cho mỗi lần xuất; PDF
nhúng DejaVu Sans để hiển thị tiếng Việt. Không xuất ghi chú khóa, kể cả khi đang
mở khóa trong editor, hoặc ghi chú trong thùng rác.

**Thống kê** trong sidebar hiển thị tổng và phân bố ghi chú active theo danh mục,
ưu tiên; tính cả ghi chú khóa và loại thùng rác. Mở lại dialog để lấy snapshot mới.

## Kiểm thử

Ví dụ PowerShell; trên Linux/macOS dùng `python` sau khi activate venv.

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m compileall -q src scripts
.\.venv\Scripts\python.exe -m pytest -q tests/unit tests/contract
```

Unit/contract không cần MongoDB hoặc màn hình. Integration cần MongoDB riêng;
fixture tạo DB UUID và chỉ dọn DB do nó sở hữu:

```powershell
$env:NOTEAPP_TEST_MONGO_URI = "mongodb://127.0.0.1:27017"
$env:NOTEAPP_TEST_DB_NAME = "noteapp_test_local"
$env:NOTEAPP_REQUIRE_MONGO = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration -m "not ui and not native_secret_store"
```

Desktop cần phiên GUI đang hoạt động. Bật cờ require để thiếu màn hình trở thành lỗi:

```powershell
$env:NOTEAPP_REQUIRE_UI = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/ui
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_desktop.py --junitxml=.pytest_cache/desktop.xml
.\.venv\Scripts\python.exe scripts/verify_desktop_e2e.py .pytest_cache/desktop.xml
```

Để kiểm tra credential store native, opt-in riêng. Test chỉ tạo và xóa một entry
UUID tổng hợp thuộc namespace NoteApp:

```powershell
$env:NOTEAPP_TEST_NATIVE_SECRET_STORE = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_native_secret_store.py
```

Kiểm tra wheel cài thật, mã hóa, bản nháp và font PDF:

```powershell
.\.venv\Scripts\python.exe -m pip wheel --no-deps --wheel-dir .pytest_cache/secure-wheels .
.\.venv\Scripts\python.exe scripts/verify_secure_storage_package.py .pytest_cache/secure-wheels
```

### Kết quả QA tham chiếu

[QA ngày 13/11/2026](docs/testing/QA_SRS_V2_2026-11-13.md) trên baseline `bfbaaa2`
ghi nhận **817 test đạt, 1 POSIX skip**. Sau sửa thông báo Windows: **586 unit/contract
và 7 UI đạt**, coverage domain/application khoảng **92%**; người chạy xác nhận popup thật.
[RTM từng AC](docs/testing/qa-srs-v2-2026-11-13/RTM.csv) có số đo và giới hạn tương ứng.

Các kết quả này không đồng nghĩa nghiệm thu toàn bộ SRS: RAM 15 phút bị gián đoạn,
FPS/cold-cache và ma trận native OS chưa hoàn tất. UI search P95 lần đầu 202,04 ms,
lần lặp 128,94 ms; báo cáo giữ cả hai, chưa cam kết ngưỡng trên mọi thiết bị.
CI đã xác minh cho baseline; patch tiếp theo cần CI/review riêng.

## Xử lý sự cố

| Hiện tượng | Cách kiểm tra |
|---|---|
| Không kết nối được MongoDB | Kiểm tra Docker/Mongo đang chạy, URI loopback, cổng và tên DB; export biến trong đúng terminal khởi chạy app. |
| Không thấy thông báo Windows | Mở **Settings → System → Notifications**, bật Notifications và tắt **Do not disturb** khi thử. Kiểm tra luật tự bật DND khi toàn màn hình/trình chiếu. Adapter phát hiện trạng thái bị chặn và trả lỗi để retry; app không tự đổi thiết lập OS. |
| Đã hết lượt thử gửi | Đặt lại lịch nhắc ở tương lai để reset số lần thử. Giữ app mở khi chờ nhắc. |
| Không lưu được bản nháp mã hóa | Kiểm tra quyền credential store, profile có đang bị app khác giữ và đường dẫn draft. Giữ nội dung editor để lưu lại; không xóa ciphertext hoặc khóa để “reset”. |
| Lỗi phiên bản khi lưu | Tải lại bản trên DB hoặc giữ nội dung thành một ghi chú khác; tránh ghi đè bản mới từ phiên khác. |
| Test local bị skip | Đọc lý do skip; cấu hình `NOTEAPP_REQUIRE_MONGO=1` hoặc `NOTEAPP_REQUIRE_UI=1` để bắt buộc dependency tương ứng. FIFO test chỉ chạy trên POSIX. |

## Nâng cấp dữ liệu

DB mới/rỗng không cần migration. Nếu DB từ bản cũ thiếu `is_pinned`, dừng các app
đang ghi, backup MongoDB cùng ảnh, xác nhận đúng DB rồi chạy:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_pinned.py --plan
.\.venv\Scripts\python.exe scripts/migrate_pinned.py --apply
.\.venv\Scripts\python.exe scripts/migrate_pinned.py --plan
.\.venv\Scripts\python.exe scripts/create_indexes.py
```

Migration chỉ bổ sung `is_pinned=false` khi thiếu và từ chối giá trị sai kiểu.
`python scripts/create_indexes.py --dry-run` kiểm tra index/schema mà không ghi.
Không tự xóa field, ciphertext, credential hoặc dữ liệu đã purge khi rollback;
xem các ADR/contract cho phiên bản dữ liệu đang dùng.

## Kiến trúc và cấu trúc repo

Hướng dependency: **Presentation → Application → Domain**. Application định nghĩa
ports; Infrastructure hiện thực MongoDB, GridFS, crypto, keyring và OS notifications.
`bootstrap.py` lắp ghép dependency. MongoDB/file I/O chạy trong worker pool;
Tk main thread đọc kết quả qua queue và cập nhật UI.

```text
src/noteapp/
├── domain/          # Entity, value object, validation và policy thuần Python
├── application/     # Use case, DTO và ports
├── infrastructure/  # MongoDB, ảnh, crypto, local draft, export và OS adapters
├── presentation/tk/ # Views, presenters, UI state và async bridge
├── bootstrap.py     # Composition root
└── main.py          # Startup, mainloop và shutdown
tests/               # Unit, contract, integration và UI
scripts/             # Index, seed, migration, retention và verification CLI
docs/                # SRS, ADR, kế hoạch và bằng chứng QA
```

## Tài liệu dự án

- [Quy tắc kỹ thuật](AGENTS.md) · [Base rules](docs/BASE_RULES.md).
- [SRS v2](docs/NoteApp_Team5_Blueprint/02_SRS_V2_OPTIMIZED.md) ·
  [Decision log](docs/NoteApp_Team5_Blueprint/01_SRS_AUDIT_AND_DECISIONS.md) ·
  [Kiến trúc](docs/NoteApp_Team5_Blueprint/03_SYSTEM_ARCHITECTURE.md).
- [Chiến lược test và RTM](docs/NoteApp_Team5_Blueprint/05_TEST_STRATEGY_AND_RTM.md) ·
  [QA hiện tại](docs/testing/QA_SRS_V2_2026-11-13.md).
- [Contract danh mục/ảnh](docs/srs/phase%203/01_PHASE3_CONTRACT_FREEZE.md) ·
  [Contract reminder](docs/srs/phase%203/02_PHASE3_REMINDER_CONTRACT_FREEZE.md):
  Gate A đã được duyệt trong từng tài liệu; decision log tổng cần đồng bộ.
- [Contract khóa nội dung](docs/srs/r1/04_R1_LOCKED_NOTE_CONTRACT_FREEZE.md) ·
  [Contract bản nháp](docs/srs/r1/03_R1_DRAFT_RECOVERY_CONTRACT_FREEZE.md):
  các quyết định đề xuất còn chờ review theo trạng thái tài liệu.
- [Bằng chứng export/thống kê](docs/testing/R2_EXPORT_STATISTICS_TEST_REPORT.md).

Các tài nguyên bên thứ ba có giấy phép riêng:
[Material Icons](src/noteapp/presentation/tk/assets/icons/NOTICE.md) và
[DejaVu Sans](src/noteapp/infrastructure/export/fonts/LICENSE-DejaVu.txt).

Khi đóng góp, tạo nhánh task từ `develop`, tuân thủ boundary và Conventional Commits,
đính kèm kết quả test thực tế; thay đổi cần reviewer độc lập trước khi merge.
