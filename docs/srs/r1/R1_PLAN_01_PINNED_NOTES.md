# R1_PLAN_01_PINNED_NOTES.md

## Task R1-01 — Ghim / Bỏ ghim ghi chú (FR-12)

**Project:** `20261IT6131002/pythonNC_nhom2`

**Target release:** R1 / Release 0.2 — Trải nghiệm và an toàn nâng cao

**Baseline:** `develop` @ `ea9c557f8c0bbd0233d2dc9067046cad3e06e73a` — Phase 3 đã merge qua PR #14

**Suggested branch:** `feature/r1-01-pin-notes`

**Requirement:** FR-12 [G] — Ghim — Should / P1

**Primary acceptance:** AC-12a — toggle pin/unpin; pinned xuất hiện trước unpinned trong mọi chế độ sort.

**Related requirements:** FR-11, BR-10, BR-14, UI/UX contract, NFR-MAIN-01, Definition of Done.
**RTM:** TC-ADV-001, TC-ADV-002.

---

# 1. Mục tiêu task

Triển khai chức năng **Pin / Unpin** cho note theo đúng SRS và kiến trúc hiện tại, không biến Pin thành một thao tác chỉ ở giao diện.

Sau khi hoàn thành:

1. Người dùng có thể ghim hoặc bỏ ghim một note đã lưu.
2. Trạng thái ghim được lưu bền vững trong MongoDB.
3. Note đã ghim luôn đứng trước note chưa ghim trong **mọi chế độ sort của active notes**:
   - Updated newest.
   - Created newest.
   - Created oldest.
   - Priority.
   - Category.
4. Search/filter vẫn giữ quy tắc pinned-first.
5. Pagination vẫn ổn định, không duplicate/missing note khi đi qua ranh giới pinned → unpinned.
6. Pin/unpin không ghi đè một phiên edit stale.
7. UI theo đúng hướng sketch NoteFlow:
   - pin indicator trên card;
   - Pin/Unpin action trong editor toolbar;
   - trạng thái rõ nhưng không làm thay đổi kiến trúc 3-pane.
8. Không sort toàn bộ dữ liệu ở client.
9. Existing notes trước R1 vẫn được đọc đúng là `is_pinned = false`.

---

# 2. Căn cứ SRS

## 2.1 Scope Release

SRS xếp R1 / Release 0.2 vào nhóm:

- FR-12 Pin.
- FR-14 Locked Note.
- hardening.
- packaging.

Task này chỉ xử lý **FR-12** và phần thay đổi bắt buộc của FR-11 để hỗ trợ pinned-first.

## 2.2 Data model

SRS định nghĩa `Note` có trường:

```text
is_pinned
```

Và schema Mongo dự kiến:

```text
notes:
  _id
  title
  content_plain | content_encrypted
  category_id
  priority
  priority_rank
  is_pinned
  version
  reminder
  attachment
  is_deleted
  deleted_at
  created_at
  updated_at
  schema_version
```

## 2.3 Acceptance liên quan

### FR-12 / AC-12a

```text
toggle pin/unpin;
pinned xuất hiện trước unpinned trong mọi chế độ sort.
```

### FR-11

Khi R1 bật Pin, ordering phải xét `pinned` trước các sort field khác.

### BR-10

Một edit session có version và stale save không được overwrite im lặng.

=> Pin là một mutation của note và phải tôn trọng optimistic concurrency.

### BR-14

I/O chạy nền và trả result/error envelope.

=> Mongo update của Pin không chạy trực tiếp trên Tk main thread.

### UI/UX

Giữ layout:

```text
Sidebar ~20% | List ~30% | Editor ~50%
```

Không thay kiến trúc UI chỉ để thêm Pin.

---

# 3. Trạng thái code hiện tại

Baseline sau Phase 3 chưa có Pin.

## Domain

`Note` hiện có:

```text
id
title
content
priority
category_id
version
created_at
updated_at
attachment
reminder
```

Chưa có:

```text
is_pinned
```

## Input DTO

`note_input.py` chưa có command/input cho Pin.

## Output DTO

`NoteView` chưa expose `is_pinned`.

## Mongo serializer

`note_to_document()` chưa ghi `is_pinned`.

`note_from_document()` chưa đọc `is_pinned`.

## Repository

`MongoNoteRepository.list_recent()` hiện sort:

```text
updated_at DESC
_id DESC
```

Chưa có pinned partition.

## Search repository

Các sort tuple hiện tại:

```text
UPDATED_AT:
  updated_at DESC, _id DESC

CREATED_AT:
  created_at ASC|DESC, _id ASC|DESC

PRIORITY:
  priority_rank DESC, updated_at DESC, _id DESC

CATEGORY:
  category_sort_key ASC, _id ASC
```

## UI

`NoteList` đang vẽ card bằng Canvas nhưng chưa có pin indicator/hit target.

`NoteEditor` chưa có Pin button.

## RTM

FR-12:

```text
TC-ADV-001 — NOT RUN
TC-ADV-002 — NOT RUN
```

---

# 4. Quyết định contract phải freeze trước code

Task không bắt đầu implementation cho đến khi các quyết định dưới đây được chốt.

| ID | Quyết định | Đề xuất |
|---|---|---|
| PIN-D01 | Kiểu dữ liệu | `is_pinned: bool`, default `False` |
| PIN-D02 | API mutation | `SetPinned(target=True/False)`, không dùng command `TogglePin` |
| PIN-D03 | Concurrency | CAS bằng `expected_version` |
| PIN-D04 | Version | Pin/unpin thành công tăng `version` đúng 1 |
| PIN-D05 | `updated_at` | **Không đổi `updated_at` khi chỉ Pin/Unpin** |
| PIN-D06 | Active vs trash | Chỉ cho thao tác Pin ở active mode |
| PIN-D07 | Trash lifecycle | Trash giữ nguyên `is_pinned`; restore phục hồi trạng thái Pin |
| PIN-D08 | Trash ordering | Trash không dùng pinned-first; vẫn theo trash lifecycle/order hiện tại |
| PIN-D09 | Same target | `SetPinned(True)` trên note đã pinned là no-op ở application layer |
| PIN-D10 | Existing data | Legacy document thiếu field được coi là `False` |
| PIN-D11 | DB normalization | Migration idempotent bổ sung `is_pinned:false` cho document thiếu field |
| PIN-D12 | Pagination | Cursor chứa pin partition để page boundary ổn định |
| PIN-D13 | UI placement | Card indicator + Editor toolbar action |
| PIN-D14 | Sort semantics | `is_pinned DESC` luôn là sort key đầu tiên của active list/search |

## Vì sao dùng `SetPinned` thay vì `TogglePin`

`TogglePin` không an toàn khi request bị retry:

```text
request 1: false -> true
retry:   true  -> false   # sai intent
```

`SetPinned(True)` giữ intent rõ ràng:

```text
false -> true
retry target vẫn = true
```

## Vì sao không đổi `updated_at`

Mục tiêu AC-12a là:

```text
PIN PARTITION
    ↓
selected sort
```

Nếu pin đồng thời đổi `updated_at`, thao tác ghim sẽ thay cả hai khóa sort và làm note nhảy vị trí thêm một lần trong chính pinned group.

Đề xuất:

```text
version    += 1
is_pinned   = target
updated_at  = giữ nguyên
```

Như vậy:

- concurrency vẫn an toàn;
- ordering phụ vẫn đúng theo sort user đã chọn;
- Pin là metadata ordering, không giả thành content edit.

Nếu PO muốn Pin được coi là một lần "updated", phải đổi PIN-D05 trước implementation và update test contract.

---

# 5. Luồng nghiệp vụ chuẩn

## 5.1 Pin từ Editor

```text
User click Pin
   ↓
NoteEditor
   ↓
AppWindow event
   ↓
PinPresenter
   ↓
TaskRunner.submit()
   ↓ worker
SetPinned.execute(
    note_id,
    expected_version,
    target=True
)
   ↓
NoteRepository.find_by_id()
   ↓
Domain Note.with_pinned(True)
   ↓
Mongo CAS update
   ↓
NoteView
   ↓ main-thread event
PinPresenter
   ├── update EditorState version + is_pinned
   └── invalidate/refresh NotesPresenter
```

Không được gọi PyMongo từ Tk callback.

## 5.2 Unpin

Giống Pin nhưng:

```text
target=False
```

Sau thành công, note trở lại partition unpinned và list phải refresh.

## 5.3 Pin khi editor đang DIRTY

Ví dụ:

```text
DB version = 8
Editor đang version = 8
User sửa content chưa save
User click Pin
```

Pin thành công:

```text
DB:
version 8 -> 9
is_pinned false -> true

Editor:
giữ nguyên text DIRTY
version 8 -> 9
is_pinned -> true
```

Sau đó Save phải dùng:

```text
expected_version = 9
```

=> không tạo conflict giả chỉ vì chính UI vừa Pin note.

Pattern này phải tương tự `apply_attachment()` / `apply_reminder()` hiện có:

```text
apply_pin(saved)
    adopt version
    adopt is_pinned
    keep unsaved text edits
```

## 5.4 Concurrent mutation

Ví dụ:

```text
Editor base version = 8

Thread A:
SetPinned(... expected=8)

Thread B:
Save edit(... expected=8)
```

Chỉ một mutation được quyền thắng CAS đầu tiên.

Mutation còn lại:

```text
CONFLICT
```

Không retry bằng cách overwrite version mới.

UI:

```text
"Note đã thay đổi ở một thao tác khác. Hãy tải lại trạng thái mới."
```

## 5.5 Trash

Active note pinned:

```text
is_pinned = true
```

Trash:

```text
is_deleted = true
is_pinned  = true
```

Trash UI không hiện Pin action.

Restore:

```text
is_deleted = false
is_pinned  = true
```

Note sau restore lại vào pinned partition.

---

# 6. Domain design

## 6.1 `Note`

Thêm:

```python
is_pinned: bool = False
```

Validation:

```text
type(is_pinned) must be bool
```

Không chấp nhận:

```text
0
1
"true"
None
```

nếu đi qua domain constructor typed contract.

## 6.2 Domain transition

Đề xuất:

```python
def with_pinned(self, pinned: bool) -> "Note": ...
```

Semantics:

```text
target == current
    -> return self hoặc application no-op

target != current
    -> is_pinned = target
    -> version += 1
    -> updated_at không đổi
```

Không đưa Mongo/Tk dependency vào domain.

---

# 7. Application layer

## 7.1 Input contract

Thêm:

```python
@dataclass(frozen=True)
class SetPinnedInput:
    note_id: str
    expected_version: int
    pinned: bool
```

Validation:

```text
note_id hợp lệ
expected_version >= 1
type(pinned) is bool
```

## 7.2 Use case

File đề xuất:

```text
src/noteapp/application/commands/set_pinned.py
```

Class:

```text
SetPinned
```

Pseudo-flow:

```text
validate input
    ↓
repo.find_by_id(note_id)
    ↓ not found
NOT_FOUND
    ↓
if current.version != expected_version
    ↓
CONFLICT
    ↓
if current.is_pinned == target
    ↓
return current NoteView
    ↓
updated = current.with_pinned(target)
    ↓
repo.set_pinned_if_version(updated, expected_version)
    ↓ false
CONFLICT
    ↓
return NoteView.from_note(updated)
```

Không dùng `UpdateNoteInput` để đổi Pin vì:

- UpdateNote đang mô tả text/category/priority edit;
- ghim không nên bắt UI gửi lại content;
- gửi lại content làm tăng nguy cơ stale overwrite;
- Pin cần action riêng để chạy độc lập.

---

# 8. Repository port

Có hai lựa chọn.

## Option A — mở rộng `NoteRepository` — KHUYẾN NGHỊ

```text
find_by_id()
list_recent()
update_if_version()
set_pinned_if_version()
```

Lý do:

- Pin vẫn là mutation trực tiếp của Note.
- Không có storage subsystem riêng như Attachment.
- Không cần tạo port nhỏ chỉ có một Mongo method nếu chưa có lý do tách adapter.

Signature đề xuất:

```python
def set_pinned_if_version(
    self,
    note: Note,
    expected_version: int,
) -> bool: ...
```

Contract:

```text
active note only
expected version exact
note.version == expected_version + 1
update only:
    is_pinned
    version
```

Không `$set` title/content/category/priority.

---

# 9. Mongo persistence

## 9.1 New document

`note_to_document()` thêm:

```python
"is_pinned": note.is_pinned
```

New note mặc định:

```text
false
```

## 9.2 Read compatibility

`note_from_document()`:

```python
document.get("is_pinned", False)
```

Điều này giúp application đọc legacy document trước migration.

## 9.3 CAS mutation

Mongo filter:

```javascript
{
  _id: note_id,
  version: expected_version,
  is_deleted: false
}
```

Update:

```javascript
{
  $set: {
    is_pinned: target
  },
  $inc: {
    version: 1
  }
}
```

Không set:

```text
title
content
category
priority
attachment
reminder
updated_at
```

## 9.4 Không pin trashed note

Guard bắt buộc:

```javascript
is_deleted: false
```

---

# 10. Migration và backward compatibility

Chỉ `document.get(..., False)` là chưa đủ cho ordering.

Lý do:

Legacy docs:

```text
is_pinned missing
```

New unpinned docs:

```text
is_pinned false
```

Nếu Mongo sort trực tiếp theo `is_pinned`, missing và false là hai BSON states khác nhau, có thể làm secondary ordering không còn đồng nhất.

## 10.1 Migration required

Thêm migration idempotent:

```javascript
updateMany(
  { is_pinned: { $exists: false } },
  { $set: { is_pinned: false } }
)
```

## 10.2 Preflight

Mở rộng `schema_report()`:

```text
missing_is_pinned
invalid_is_pinned
pinned_true
pinned_false
```

Ví dụ:

```text
missing_is_pinned = count({is_pinned: {$exists:false}})
invalid_is_pinned = count({is_pinned: {$exists:true, $not: {$type:"bool"}}})
```

## 10.3 Migration safety

Yêu cầu:

```text
--plan
    chỉ báo số record

--apply
    thực hiện updateMany

rerun --apply
    modified_count = 0
```

Không sửa:

```text
version
updated_at
content
attachment
reminder
deleted_at
```

## 10.4 `schema_version`

Không tự tăng `schema_version` trong task này.

Lý do:

- code hiện có mới chỉ report v1/v2;
- chưa có policy rõ rằng mỗi additive field bắt buộc bump schema_version;
- tự bump một phần document có thể tạo semantic version không nhất quán.

Nếu team muốn dùng `schema_version=2` cho R1, phải thành quyết định riêng trước code.

---

# 11. Ordering contract

Đây là phần quan trọng nhất của FR-12.

Mọi active query phải có dạng:

```text
is_pinned DESC
    ↓
selected sort
    ↓
stable tie-breaker
```

## 11.1 Updated sort

```text
is_pinned DESC
updated_at DESC
_id DESC
```

## 11.2 Created newest

```text
is_pinned DESC
created_at DESC
_id DESC
```

## 11.3 Created oldest

```text
is_pinned DESC
created_at ASC
_id ASC
```

## 11.4 Priority

```text
is_pinned DESC
priority_rank DESC
updated_at DESC
_id DESC
```

## 11.5 Category

```text
is_pinned DESC
category_sort_key ASC
_id ASC
```

---

# 12. Keyset pagination

## 12.1 Không được chỉ sort Pin ở UI

Sai:

```text
Mongo page 1:
  30 unpinned

Mongo page 2:
  contains pinned

FE sort page 1
```

Pinned note vẫn nằm page 2 => vi phạm AC-12a.

Ordering phải diễn ra trong repository trước `$limit`.

## 12.2 Cursor mới

Ví dụ Updated:

```json
{
  "keys": [
    true,
    "2026-11-04T07:00:00+00:00"
  ],
  "id": "..."
}
```

Tức cursor sort tuple:

```text
[is_pinned, updated_at, _id]
```

Created:

```text
[is_pinned, created_at, _id]
```

Priority:

```text
[is_pinned, priority_rank, updated_at, _id]
```

Category:

```text
[is_pinned, category_sort_key, _id]
```

## 12.3 Cursor validation

`is_pinned` cursor key:

```text
type(value) is bool
```

Không chấp nhận:

```text
0 / 1 / "true" / null
```

## 12.4 Old cursor invalidation

Cursor của Phase 2/3 không có pin key.

Sau R1 deployment, cursor cũ nên fail:

```text
ValidationError("Cursor sort tuple does not match.")
```

Đây là acceptable vì cursor chỉ là transient UI pagination state, không phải persisted business data.

---

# 13. CATEGORY sort — điểm cần xử lý riêng

Current category query tối ưu bằng cách:

```text
group category
    ↓
lookup category name
    ↓
lookup limited notes per category
```

Nó không thể chỉ đơn giản prepend:

```text
is_pinned DESC
```

vào `fields`, vì `is_pinned` là thuộc tính của note nhưng pipeline đã group theo category trước khi note được lấy lại.

## 13.1 Không làm

Không:

```text
fetch all category results
sort pinned in Python
```

vì vi phạm FR-11/AC-11b.

## 13.2 Hướng triển khai đề xuất

Repository xử lý CATEGORY theo hai bounded partitions:

```text
PARTITION 1:
    is_pinned = true
    category ASC
    _id ASC

PARTITION 2:
    is_pinned = false
    category ASC
    _id ASC
```

Page builder:

```text
query pinned partition trước
    ↓
nếu đủ limit
    return
    ↓
nếu thiếu
    lấy unpinned với remaining limit
```

Cursor mang:

```text
partition is_pinned
category_sort_key
_id
```

Khi cursor ở:

```text
is_pinned = true
```

repository tiếp tục pinned partition trước; khi hết pinned mới chuyển false.

Khi cursor ở:

```text
is_pinned = false
```

repository chỉ tiếp tục false partition.

## 13.3 Case bắt buộc test

Dataset:

```text
20 pinned
40 unpinned
limit=30
```

Expected:

```text
page 1:
20 pinned + 10 unpinned

page 2:
30 unpinned
```

Không:

```text
duplicate
missing
pinned ở page 2
```

---

# 14. Mongo indexes

Không sửa index bằng cách drop nóng trong application startup.

Indexes phải additive + preflight.

## 14.1 Recent

Đề xuất:

```text
idx_notes_pinned_recent

is_deleted ASC
is_pinned DESC
updated_at DESC
_id DESC
```

## 14.2 Priority

```text
idx_notes_pinned_priority

is_deleted ASC
is_pinned DESC
priority_rank DESC
updated_at DESC
_id DESC
```

## 14.3 Category partition lookup

```text
idx_notes_pinned_category_seek

is_deleted ASC
is_pinned DESC
category_id ASC
_id ASC
```

Vì category partition sẽ dùng:

```text
is_deleted = false
is_pinned = fixed
category_id = fixed
_id seek
```

## 14.4 Created sort

Đây là điểm phải benchmark kỹ.

Pinned phải luôn DESC, trong khi `created_at` hỗ trợ cả ASC và DESC.

Không được giả định một compound index duy nhất support tối ưu cả hai hướng.

Candidate:

```text
idx_notes_pinned_created_desc
is_deleted ASC
is_pinned DESC
created_at DESC
_id DESC
```

và nếu explain cho ASC không đạt:

```text
idx_notes_pinned_created_asc
is_deleted ASC
is_pinned DESC
created_at ASC
_id ASC
```

Quyết định index thứ hai dựa trên `explain()` evidence, không đoán.

## 14.5 Search text

Mongo `$text` + custom sort có thể cần blocking sort.

Task phải:

- giữ sort server-side;
- không client-sort;
- chạy benchmark/explain trên dataset test;
- không claim NFR search <200ms nếu chưa có đo lường.

---

# 15. Query implementation changes

## `list_recent()`

Old:

```text
(updated_at DESC, _id DESC)
```

New:

```text
(is_pinned DESC, updated_at DESC, _id DESC)
```

Cursor cũ:

```text
timestamp + id
```

Cursor mới:

```text
pinned + timestamp + id
```

Không tiếp tục dùng `encode_cursor()` Phase 1 nếu format không chứa pin key.

Khuyến nghị thống nhất list recent với versioned seek cursor hiện dùng trong search.

## `query_pipeline()`

Non-category sorts:

```python
fields = {
    UPDATED_AT: [
        ("is_pinned", -1),
        ("updated_at", -1),
        ("_id", -1),
    ],
    CREATED_AT: [
        ("is_pinned", -1),
        ("created_at", direction),
        ("_id", direction),
    ],
    PRIORITY: [
        ("is_pinned", -1),
        ("priority_rank", -1),
        ("updated_at", -1),
        ("_id", -1),
    ],
}
```

Cursor conversion thêm bool handler.

CATEGORY dùng dedicated partition path ở §13.

---

# 16. Presentation / UI plan

## 16.1 Card design

Theo sketch NoteFlow:

Pinned card có:

```text
📌 / push_pin icon
```

Vị trí:

```text
top-left hoặc top-right card header
```

Không dùng emoji làm asset release cuối.

Dùng icon cùng family hiện có và cập nhật license/NOTICE.

### Visual states

Unpinned:

```text
outline pin / neutral
```

Pinned:

```text
filled pin / accent
```

Không chỉ dùng màu để truyền đạt state; icon shape/state phải đủ rõ.

## 16.2 Canvas hit target

`NoteList` hiện vẽ card bằng Canvas.

Cần tag riêng:

```text
pin-action:<note_id>
```

Không để click Pin vô tình trigger card select/open.

Event contract:

```text
click pin
    -> consume event
    -> on_pin(note)
```

## 16.3 Editor toolbar

Header hiện có Save/Delete.

Thêm:

```text
Pin
```

hoặc:

```text
Unpin
```

dựa trên `EditorState.is_pinned`.

Button disabled khi:

```text
new unsaved note
trash mode
pin request pending
note mutation conflict
window closing
```

## 16.4 No modal

Pin/unpin không cần confirm dialog.

## 16.5 Loading state

Không freeze UI.

Trong lúc pending:

```text
disable pin action
giữ editor usable nếu mutation policy cho phép
show lightweight status
```

Nếu common mutation guard hiện tại không cho phép parallel CAS mutation, Pin phải tham gia cùng guard.

---

# 17. Presenter/state integration

## 17.1 `NoteView`

Thêm:

```text
is_pinned: bool
```

## 17.2 `EditorState`

Thêm:

```text
is_pinned: bool = False
```

## 17.3 `EditorPresenter.open()`

Adopt:

```text
note.is_pinned
```

## 17.4 `apply_pinned(saved)`

Thêm method:

```text
adopt:
    version
    is_pinned

preserve:
    title
    content
    priority
    category
    dirty revision
    attachment
    reminder
```

Không reload toàn editor.

## 17.5 `NotesPresenter`

Sau pin/unpin:

```text
invalidate current paging
refresh page 1
```

Không giữ `next_cursor` cũ vì ordering partition vừa thay đổi.

## 17.6 Dedicated presenter

Khuyến nghị:

```text
presentation/tk/presenters/pin_presenter.py
```

Pattern giống:

```text
AttachmentPresenter
ReminderPresenter
```

Nó chịu trách nhiệm:

```text
submit
pending request id
stale result discard
success callback
error callback
busy callback
```

---

# 18. Interaction với các feature Phase 3

## 18.1 Attachment

Pin không được làm mất:

```text
attachment
```

## 18.2 Reminder

Pin không được reset:

```text
reminder.status
due_at
claim metadata
```

## 18.3 Category

Pin không đổi:

```text
category_id
```

Category rename không ảnh hưởng pin.

## 18.4 Trash

Pin preserved through:

```text
trash
restore
```

Hard delete xóa note như bình thường.

## 18.5 Search

Search result:

```text
matching pinned first
matching unpinned after
```

Không đưa pinned non-match vào result.

---

# 19. Test strategy

Không merge nếu chỉ test UI.

## 19.1 Unit tests — Domain

### PIN-U01 default

```text
new Note
is_pinned = false
```

### PIN-U02 pin transition

```text
false -> true
version +1
updated_at unchanged
```

### PIN-U03 unpin

```text
true -> false
version +1
updated_at unchanged
```

### PIN-U04 invalid type

Reject:

```text
1
0
"true"
None
```

### PIN-U05 no unrelated mutation

Pin không đổi:

```text
title
content
priority
category
attachment
reminder
created_at
updated_at
```

---

# 20. Application tests

## PIN-A01 pin

```text
version 4 false
SetPinned(True, expected=4)
=> version 5 true
```

## PIN-A02 unpin

```text
version 5 true
SetPinned(False, expected=5)
=> version 6 false
```

## PIN-A03 conflict

```text
DB version 6
request expected 5
=> CONFLICT
```

## PIN-A04 missing note

```text
=> NOT_FOUND
```

## PIN-A05 trashed note

```text
=> NOT_FOUND / rejected by active repository contract
```

## PIN-A06 same target

Theo PIN-D09:

```text
already true
SetPinned(True)
=> no-op
=> no unnecessary version increment
```

---

# 21. Repository contract tests

Shared fake + Mongo contract.

## PIN-R01 CAS success

Exactly one update.

## PIN-R02 stale CAS

No write.

## PIN-R03 deleted guard

No pin on trash.

## PIN-R04 legacy read

Document missing `is_pinned`:

```text
Note.is_pinned == False
```

## PIN-R05 persistence

Restart/read:

```text
pinned remains true
```

---

# 22. Ordering tests — RTM core

## TC-ADV-001

Seed mixed notes:

```text
pinned HIGH
unpinned HIGH
pinned LOW
unpinned MEDIUM
...
```

For each sort:

```text
UPDATED
CREATED DESC
CREATED ASC
PRIORITY
CATEGORY
```

Assert:

```text
all pinned positions < all unpinned positions
```

Sau đó assert ordering bên trong mỗi partition đúng selected sort.

## TC-ADV-002

```text
pin note
assert pinned partition

unpin note
assert normal ordering restored

change sort
assert unpinned follows selected sort
```

---

# 23. Pagination tests

Bắt buộc vì đây là vùng dễ sai nhất.

## PIN-P01 all pinned > limit

```text
50 pinned
limit 30
```

Page1 + Page2:

```text
50 unique IDs
no missing
no duplicate
```

## PIN-P02 partition crossing

```text
20 pinned
40 unpinned
limit 30
```

Expected:

```text
P1 = 20 pinned + 10 unpinned
P2 = remaining unpinned
```

## PIN-P03 no pinned

Legacy behavior equivalent.

## PIN-P04 one pinned inserted before refresh

Old cursor phải không được dùng tiếp sau local pin mutation.

Presenter phải invalidate.

## PIN-P05 category boundary

Pinned category Z vẫn phải đứng trước unpinned category A.

Ví dụ:

```text
pinned:   Z
unpinned: A
```

Expected:

```text
Z(pinned)
A(unpinned)
```

vì pinned partition ưu tiên cao hơn category ordering.

---

# 24. Search/filter integration tests

Matrix tối thiểu:

```text
text only + pin
category + pin
priority + pin
date + pin
text + category + priority + date + pin
```

Trong mỗi query:

```text
filter correctness
then pinned-first
then selected sort
then stable cursor
```

Negative:

```text
pinned note không match text
=> không xuất hiện chỉ vì pinned
```

---

# 25. UI tests

## PIN-UI01 editor button

Saved note:

```text
Pin visible/enabled
```

New note:

```text
disabled
```

## PIN-UI02 visual state

Pin:

```text
button -> Unpin
card indicator -> pinned
```

## PIN-UI03 list action

Click card pin target:

```text
runs pin
does not accidentally open different action twice
```

## PIN-UI04 dirty editor

Dirty content + Pin:

```text
dirty text preserved
version adopted
next Save succeeds using new version
```

## PIN-UI05 conflict

Remote version changed:

```text
show error/conflict
do not fake pinned success
```

## PIN-UI06 trash

No Pin action in trash mode.

---

# 26. Desktop E2E

Thêm scenario mới:

```text
test_r1_pin_persists_and_orders_across_restart
```

Flow:

```text
launch
↓
create note A
create note B
create note C
↓
pin C
↓
verify C first
↓
change sort priority/category
↓
verify C still in pinned partition
↓
restart app
↓
verify C remains pinned
↓
unpin C
↓
verify C returns selected normal ordering
↓
trash pinned note A
↓
restore A
↓
verify pin state preserved
```

E2E phải dùng real Mongo fixture.

Nếu thêm E2E scenario vào `tests/integration/test_desktop.py`, đồng thời phải cập nhật:

```text
scripts/verify_desktop_e2e.py
tests/contract/test_desktop_ci_report.py
```

**Không lặp lại lỗi Phase 3:** thay expected scenario count nhưng quên update contract test.

Khuyến nghị refactor verifier trong task này để error message không hard-code số bằng chữ:

```text
expected = len(EXPECTED_SCENARIOS)
```

Output:

```text
Desktop E2E must execute exactly {expected} required scenarios.
```

Test match semantic phrase thay vì `"six required"`.

---

# 27. CI gates

PR không được merge nếu thiếu bất kỳ gate sau.

```text
ruff check
ruff format --check
compileall
unit
contract
Mongo integration
UI
desktop E2E
migration/preflight test
```

Đặc biệt:

```text
quality 3.10 = PASS
quality 3.12 = PASS
windows-ui = PASS
integration = PASS
```

Không push "fix theo đoán" vào branch integration chính.

Local targeted tests phải chạy trước push của từng slice.

---

# 28. Implementation slices / PR strategy

Có thể làm trong một feature branch, nhưng chia commits theo slice rõ ràng.

## R1-01.0 — Contract Freeze

Artifacts:

```text
R1_PLAN_01_PINNED_NOTES.md
docs/srs/r1/01_R1_PIN_CONTRACT_FREEZE.md
RTM update: FR-12 planned
```

Exit:

```text
PIN-D01..D14 approved
```

Không code trước khi D05/D07/D08 chốt.

---

## R1-01.1 — Domain + DTO

Files:

```text
domain/entities/note.py
application/dto/note_input.py
application/dto/note_view.py
presentation/tk/state/editor_state.py
```

Tests first:

```text
PIN-U01..U05
```

Exit:

```text
unit PASS
no Mongo/UI dependency added to domain
```

---

## R1-01.2 — Application command + repository CAS

Files:

```text
application/commands/set_pinned.py
application/ports/note_repository.py
infrastructure/mongo/repositories.py
```

Tests:

```text
PIN-A01..A06
PIN-R01..R03
```

Exit:

```text
stale mutation cannot overwrite
```

---

## R1-01.3 — Persistence + migration

Files:

```text
infrastructure/mongo/models.py
infrastructure/mongo/migrations.py
scripts/<pin migration script>
```

Tests:

```text
legacy read
migration plan
migration apply
rerun idempotence
invalid bool preflight
```

Exit:

```text
all notes normalized to explicit boolean in release DB
```

---

## R1-01.4 — Query ordering + cursor

Files:

```text
infrastructure/mongo/query_cursor.py
infrastructure/mongo/note_query_repository.py
infrastructure/mongo/repositories.py
infrastructure/mongo/indexes.py
```

Tests:

```text
all sorts
all filters
partition crossing
category special path
cursor corruption
legacy cursor rejected
```

Exit:

```text
TC-ADV-001 automated PASS
TC-ADV-002 automated PASS
```

Đây là slice có rủi ro cao nhất của task.

---

## R1-01.5 — Presentation

Files:

```text
presentation/tk/presenters/pin_presenter.py
presentation/tk/views/note_list.py
presentation/tk/views/note_editor.py
presentation/tk/views/app_window.py
presentation/tk/assets/icons/*
```

Tests:

```text
PIN-UI01..UI06
```

Exit:

```text
Pin interaction non-blocking
dirty editor preserved
```

---

## R1-01.6 — E2E + CI + docs

Files:

```text
tests/integration/test_desktop.py
tests/r1_desktop_scenarios.py
scripts/verify_desktop_e2e.py
tests/contract/test_desktop_ci_report.py
docs/NoteApp_Team5_Blueprint/05_TEST_STRATEGY_AND_RTM.md
README.md
```

Exit:

```text
full CI green
RTM FR-12 PASS evidence
screenshot/demo evidence
```

---

# 29. File-level impact matrix

| Layer | File/module | Change |
|---|---|---|
| Domain | `domain/entities/note.py` | `is_pinned`, transition |
| DTO | `application/dto/note_input.py` | `SetPinnedInput` |
| DTO | `application/dto/note_view.py` | expose flag |
| Use case | `application/commands/set_pinned.py` | new |
| Port | `application/ports/note_repository.py` | CAS pin contract |
| Mongo model | `infrastructure/mongo/models.py` | serialize/legacy default |
| Mongo repo | `infrastructure/mongo/repositories.py` | CAS update |
| Query | `infrastructure/mongo/note_query_repository.py` | pinned-first |
| Cursor | `infrastructure/mongo/query_cursor.py` | bool key validation/use |
| Index | `infrastructure/mongo/indexes.py` | pinned indexes |
| Migration | `infrastructure/mongo/migrations.py` | pin preflight |
| Editor state | `presentation/tk/state/editor_state.py` | flag |
| Presenter | `presentation/tk/presenters/pin_presenter.py` | async operation |
| Editor | `presentation/tk/views/note_editor.py` | Pin/Unpin action |
| List | `presentation/tk/views/note_list.py` | pin indicator/action |
| Composition | `presentation/tk/views/app_window.py` / bootstrap | wiring |
| Tests | unit/contract/integration/ui/E2E | FR-12 evidence |
| Docs | RTM/README/contract | release evidence |

---

# 30. Error mapping

Use existing `OperationResult/ErrorCode` pattern.

Expected:

```text
VALIDATION
NOT_FOUND
CONFLICT
REPOSITORY_UNAVAILABLE
BUSY
```

Không expose raw:

```text
PyMongoError
ObjectId exception
Mongo write result
```

UI message ngắn:

```text
CONFLICT:
"Ghi chú vừa thay đổi. Hãy tải lại trước khi ghim."

REPOSITORY_UNAVAILABLE:
"Chưa thể cập nhật trạng thái ghim."

BUSY:
"Đang xử lý một thay đổi khác."
```

---

# 31. Observability

Log metadata được phép:

```text
operation=set_pinned
note_id
target
result
duration_ms
```

Không log:

```text
content
attachment bytes
reminder message payload
future locked plaintext
```

Điều này giữ tương thích với R1 FR-14 sau này.

---

# 32. Performance validation

Không cần benchmark kiểu UI đẹp; cần benchmark phần query bị Pin thay đổi.

Dataset:

```text
10,000 notes
~5–20% pinned
multiple categories
HIGH/MEDIUM/LOW distribution
mix created/updated timestamps
```

Đo:

```text
list first page
next page
priority sort
created asc
created desc
category
text search + pin ordering
combined filter
```

Evidence:

```text
Mongo explain
keys examined
docs examined
blocking sort presence
p95 query
environment
```

Không claim SRS threshold nếu chưa đo.

---

# 33. Security / future FR-14 compatibility

Pin không được thiết kế theo cách khiến FR-14 phải rewrite.

Future locked note vẫn có:

```text
is_pinned
```

nhưng Pin UI/List không cần decrypt content.

Khi FR-14 đến:

```text
pinned locked note
```

card có thể hiển thị safe metadata theo policy mà không đọc plaintext.

Do đó:

- Pin query chỉ dùng metadata.
- Pin index không phụ thuộc `content_plain`.
- Pin mutation không đọc/ghi content.

---

# 34. Rollback

Feature additive.

Rollback application code:

```text
old code ignore is_pinned
```

Mongo field có thể giữ lại an toàn:

```text
is_pinned
```

Không cần `$unset` ngay.

Indexes mới có thể drop sau khi xác nhận rollback, nhưng:

```text
không drop trong app startup
không drop tự động khi deploy
```

Nếu rollback giữa migration:

```text
is_pinned false/true vẫn là harmless unknown field với old serializer
```

---

# 35. Definition of Ready cho R1-01

Chỉ bắt đầu code khi:

- [ ] FR-12 và AC-12a được team xác nhận scope.
- [ ] PIN-D01..PIN-D14 chốt.
- [ ] UI vị trí Pin được duyệt.
- [ ] Quyết định `updated_at` chốt.
- [ ] Quyết định trash/restore chốt.
- [ ] Migration behavior chốt.
- [ ] Test cases TC-ADV-001/002 map xong.
- [ ] Branch tạo từ latest `develop`.
- [ ] Baseline CI của `develop` xanh.

---

# 36. Definition of Done cho R1-01

Task chỉ DONE khi:

- [ ] `Note.is_pinned` có typed domain contract.
- [ ] Legacy docs đọc thành unpinned.
- [ ] Migration explicit boolean hoàn tất trên test DB.
- [ ] Pin/Unpin dùng CAS.
- [ ] Stale version không overwrite.
- [ ] Dirty editor không mất text khi Pin.
- [ ] Pin state persist qua restart.
- [ ] Pin state survive trash/restore.
- [ ] Pinned-first đúng ở mọi active sort.
- [ ] Search/filter giữ pinned-first.
- [ ] Category sort qua partition boundary đúng.
- [ ] Pagination không duplicate/missing.
- [ ] Không client-side global sort.
- [ ] UI Pin card + editor hoàn chỉnh.
- [ ] Unit PASS.
- [ ] Contract PASS.
- [ ] Integration PASS.
- [ ] Windows UI PASS.
- [ ] Desktop E2E PASS.
- [ ] CI full green.
- [ ] TC-ADV-001 PASS evidence.
- [ ] TC-ADV-002 PASS evidence.
- [ ] RTM cập nhật.
- [ ] README cập nhật.
- [ ] Screenshot/GIF demo được lưu.
- [ ] Không P0/P1 bug mở liên quan FR-12.

---

# 37. Acceptance demo

Demo ngắn dùng để nghiệm thu:

```text
1. Mở app với 6 notes.
2. Chọn sort "Cập nhật mới nhất".
3. Pin note đang ở cuối list.
4. Note chuyển lên pinned section.
5. Đổi sang Priority.
6. Note vẫn nằm trong pinned partition.
7. Đổi sang Category.
8. Note vẫn nằm trước toàn bộ unpinned.
9. Search một từ có cả pinned và unpinned matches.
10. Pinned match đứng trước.
11. Sửa content nhưng chưa Save.
12. Pin/Unpin.
13. Content đang sửa không mất.
14. Save.
15. Restart app.
16. Pin state và content vẫn đúng.
17. Trash pinned note.
18. Restore.
19. Pin state được giữ.
20. Unpin.
21. Note trở lại normal selected ordering.
```

---

# 38. Proposed commit sequence

```text
docs(r1): freeze FR-12 pin contract
test(pin): add domain and application pin contracts
feat(pin): add pinned state and CAS command
feat(pin): persist is_pinned with legacy compatibility
feat(pin): add migration and pinned indexes
feat(pin): enforce pinned-first keyset ordering
feat(pin): add category partition pagination
feat(ui): add pin actions to note card and editor
test(pin): add Mongo/UI/E2E pin coverage
docs(r1): record FR-12 RTM and release evidence
```

Không gom toàn bộ thành một commit lớn.

---

# 39. PR checklist

Suggested PR title:

```text
feat(r1): implement pinned notes with stable server-side ordering
```

PR description phải có:

```text
Requirement:
FR-12 / AC-12a

Related:
FR-11
BR-10
BR-14

Data change:
notes.is_pinned bool

Migration:
legacy missing -> false

Concurrency:
CAS expected_version

Ordering:
pinned-first server-side

Evidence:
TC-ADV-001
TC-ADV-002
unit
contract
integration
windows-ui
desktop E2E

Known limitations:
...
```

---

# 40. Không nằm trong task này

Không scope creep sang:

```text
FR-14 Lock/PIN encryption
FR-15 Export
FR-16 Statistics
full UI redesign
rich text
multi-attachment
cloud sync
collaboration
pin folders/categories
manual reorder/drag-drop
pinned_at custom ordering
```

Full UI refresh có thể triển khai song song ở branch riêng nếu không thay domain contract.

---

# 41. Thứ tự thực hiện đề xuất

```text
R1-01.0 Contract freeze
        ↓
R1-01.1 Domain + DTO
        ↓
R1-01.2 Application + CAS
        ↓
R1-01.3 Persistence + migration
        ↓
R1-01.4 Ordering + cursor + index
        ↓
R1-01.5 UI
        ↓
R1-01.6 Full E2E + RTM + docs
        ↓
MERGE R1-01
```

Không làm UI trước ordering contract.

Nếu UI Pin chạy nhưng repository chưa pinned-first thì feature vẫn **chưa đạt FR-12**.

---

# 42. Gate để bắt đầu task tiếp theo

Chỉ chuyển sang FR-14 Lock khi R1-01 có:

```text
CI green
RTM PASS
migration verified
pagination verified
no open P0/P1 bug
```

Lý do:

FR-14 sẽ mở rộng `Note` và search/index semantics thêm lần nữa. Chốt Pin sạch trước giúp tránh trộn hai thay đổi data model/concurrency vào cùng một PR.

---

## Kết luận

FR-12 nhìn nhỏ ở UI nhưng thực tế là một **cross-layer feature**:

```text
SRS
 ↓
Domain state
 ↓
CAS mutation
 ↓
Mongo schema
 ↓
Migration
 ↓
Indexes
 ↓
Keyset cursor
 ↓
All sort modes
 ↓
Search/filter
 ↓
Presenter
 ↓
Tk UI
 ↓
E2E/RTM
```

Điểm rủi ro chính không phải nút Pin, mà là:

1. pinned-first trên mọi sort;
2. category ordering;
3. keyset pagination qua pinned/unpinned boundary;
4. stale editor version sau Pin;
5. legacy data thiếu `is_pinned`;
6. giữ CI verifier đồng bộ khi thêm E2E scenario.

Task chỉ được coi là hoàn tất khi sáu nhóm rủi ro này có automated evidence.
