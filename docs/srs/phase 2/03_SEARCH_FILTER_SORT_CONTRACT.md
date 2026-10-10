# PHASE 2 — SEARCH / FILTER / SORT / PAGINATION CONTRACT

**Phạm vi:** FR-06, FR-07, FR-11 Shall + lọc FR-04/05 từ Phase 1. **Nguồn:** SRS gốc phần “Cơ chế tìm kiếm toàn văn và bộ lọc thời gian”, “Cơ chế sắp xếp”, SRS v2 §§3,5,6; `DEC-07` matching semantics đã được nhóm chốt nhưng artifact/giá trị chưa được cung cấp trong repo. Dưới đây là **đề xuất contract kỹ thuật**; team điền expected cases của quyết định đã có trước merge.

## 1. Query semantics mapping: bắt buộc phân biệt source và design

**P2-02 clarification (10/10/2026):** tên/signature cụ thể để review nằm trong
[public interfaces](../../architecture/PHASE2_PUBLIC_CONTRACTS.md) và
[ADR-0002](../../adr/0002-phase2-query-trash-contract.md).
Các code blocks `SearchNotesInput`/`SortField`/constructor dưới đây vẫn là ví dụ
của plan; canonical proposal chọn `SearchNotesCriteria`, `SortMode`, separate
`SearchRepository` và timezone injection theo contract mới. Chưa có runtime
implementation hay artifact phê duyệt được suy diễn từ clarification này.

Theo follow-up CF-01/04/07: agreed-value trace chỉ nằm tại ADR-0002;
public contract đặc tả Windows/IANA/fail-closed date resolution, và
[category query prototype plan](../../architecture/PHASE2_CATEGORY_QUERY_PLAN.md)
giao cụ thể P2-05/06/16 pipeline/EXPLAIN/10k receipt. Các ví dụ bên dưới không
tự trở thành expected values của DEC-07 hay bằng chứng NFR đã đạt.

| Vấn đề | SRS gốc | Áp dụng/đề xuất Phase 2 | Verify |
|---|---|---|---|
| Full-text fields | `title`, `content` | Code hiện lưu `title` và **`content_plain`**; text index phải đánh trên field tồn tại, không đổi data name một cách bất ngờ | Title-only/content-only fixtures |
| Query operator | `$text` với `$search` | Text index Mongo native, không client scan/regex thay thế mặc định | `explain`, index info |
| Debounce | 300 ms | Presenter/Tk `root.after(300)`; cancel pending timer | Fake clock/UI tester |
| Search behavior | Token full-text | Không hứa substring, Vietnamese stemming, không dấu khi chưa có quyết định và test thực; native text mặc định Mongo cần probe | Vietnamese corpus |
| Date range | Start_Date/End_Date + intersection text | Theo `created_at`/`updated_at` do UI chọn hoặc default đã chốt; **ngày trên máy người dùng**, inclusive bằng UTC half-open | UTC/DST cases |
| Priority sort | HIGH→MEDIUM→LOW | `priority_rank DESC` = 3,2,1 (Phase1 lưu sẵn) | Mixed priorities |
| Category sort | `category_name` A–Z | Canonical category by `category_id` + `categories.name_key`; **không** sort ObjectId/lexical category_id | Study/Cá nhân/test missing |
| Updated sort | Updated newest | `(updated_at DESC, _id DESC)` | Equal timestamp |
| Created sort | Asc / Desc | `(created_at ASC/DESC, _id ASC/DESC)` | Equal timestamp |
| Deleted | Active only | Every active query constrained `is_deleted:false`; trash uses different query use-case | Delete→search no result |
| Paging | SRS perf (no fixed page) | Reuse Phase1 30 default, max 100, bounded cursor; no `skip` over 10k in production route | 65/10k seed |

**Text matching examples to sign off:** `“học”` vs `“hoc”`, `“học tập”` as two terms or phrase, punctuation, mixed case, Vietnamese Unicode combining, literal `-`, double quotes and leading `$`. Do **not** claim all of these match; document the **actual** Mongo result and compare to approved expectation. Reject abusive query syntax if validation policy specifies, but do not arbitrarily cap user text as though SRS imposed a cap.

## 2. Recommended typed DTO (illustrative, not code committed)

```python
from dataclasses import dataclass
from datetime import date
from enum import Enum
from noteapp.domain.value_objects.priority import Priority

class DateField(str, Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class SortField(str, Enum):
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"
    PRIORITY = "priority"
    CATEGORY = "category"

class SortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"

@dataclass(frozen=True)
class SearchNotesInput:
    text: str = ""
    category_id: str | None = None
    priority: Priority | None = None
    start_date: date | None = None
    end_date: date | None = None
    date_field: DateField = DateField.UPDATED_AT
    sort_field: SortField = SortField.UPDATED_AT
    direction: SortDirection = SortDirection.DESC
    limit: int = 30
    cursor: str | None = None
```

- `start_date` and `end_date` **may be None**, single-sided range is supported if approved; invalid date order raises `ValidationError`.
- `text` is a **string**, not Mongo filter dict. Category ID opaque until validated/converted at Mongo mapper, not a raw `ObjectId` in DTO.
- If text changes, category/priority/date/sort changes, **reset cursor**. Query response includes applied query signature/snapshot identifier in presenter state, not data from UI controls inferred after worker returns.
- `ListNotesInput` and `NoteRepository.list_recent()` Phase 1 should remain backward compatible; implement a new QueryPort/`SearchNotes` use case, or extend with defaults in an approved nonbreaking contract.

## 3. Port/application shape

```python
class SearchRepository(Protocol):
    def search(self, criteria: CompiledNoteCriteria) -> NotePage: ...

class SearchNotes:
    def __init__(self, repo: SearchRepository, clock: Clock, timezone_port: LocalTimezone): ...
    def execute(self, command: SearchNotesInput) -> NoteListView: ...
```

`CompiledNoteCriteria` is **domain/application-level normalized typed filter**, not `$text`/`$gte`/Mongo dict. Alternative: port accepts validated `SearchNotesInput` minus presentation fields plus converted UTC bounds; lock the exact signature under P2-02. `LocalTimezone` can be an injected provider only if really needed to avoid OS timezone testing complexity. **No need to add a framework**.

`SearchNotes` owns: validate & normalize input → derive local start/end into UTC range → allowlisted sort/filter → repo execution → map NotePage to existing `NoteListView`. Infrastructure owns: `$text` compiler, category lookup, index/aggregation/explain, BSON object IDs, cursor encoding.

## 4. Local date semantics + DST

For inclusive local dates `2026-10-10` to `2026-10-12`, **do not** query `end <= 2026-10-12 23:59:59`. Instead:

1. Resolve user's real local timezone with DST-aware IANA zone where possible (not merely today's fixed UTC offset).
2. `lower = local_start_of_day(start_date).astimezone(UTC)`.
3. `upper = local_start_of_day(end_date + 1 day).astimezone(UTC)`.
4. Mongo `$gte: lower`, `$lt: upper`; if a bound is absent, omit only that bound.

A calendar day at DST switch may be 23/25 hours; adding a fixed 24h to UTC start is **wrong** for some zones. Unit tests should use `Asia/Ho_Chi_Minh` and `America/New_York` transition; exact date-field default (created vs updated) must match signed UX rule. Store UTC-aware, display OS timezone.

## 5. Mongo adapter SQL-like intent and pseudo filters

Query normal case:

```python
filter_ = {"is_deleted": False}
if criteria.text:
    filter_["$text"] = {"$search": criteria.text}
if criteria.category_id:
    filter_["category_id"] = object_id(criteria.category_id)
if criteria.priority:
    filter_["priority"] = criteria.priority.value
if criteria.utc_start or criteria.utc_end:
    filter_[criteria.date_field.value] = {
        **({"$gte": criteria.utc_start} if criteria.utc_start else {}),
        **({"$lt": criteria.utc_end} if criteria.utc_end else {}),
    }
```

**Không pass bất kỳ `dict` của user** vào `collection.find()`; adapter chỉ build từ DTO có type/enum allowlist. Không dùng `$where`. Việc ghép `$text` với nhiều sort keys có thể ảnh hưởng plan/index; test query actual Mongo trước khi cố tối ưu.

Recommended candidate indexes (chỉ định final sau spike):

```js
// One named text index for title + actual content_plain:
db.notes.createIndex({title:"text", content_plain:"text"}, {name:"idx_notes_text"})
// Current idx_notes_recent from Phase 1 must remain.
db.notes.createIndex({is_deleted:1, category_id:1, updated_at:-1, _id:-1}, {name:"idx_notes_category_recent"})
db.notes.createIndex({is_deleted:1, priority_rank:-1, updated_at:-1, _id:-1}, {name:"idx_notes_priority"})
db.notes.createIndex({is_deleted:1, created_at:-1, _id:-1}, {name:"idx_notes_created"})
```

These are **index candidates**, not already implemented and not all necessarily optimal. Assess `$text` index language/tokenization, index count, Mongo text/compound restrictions and `explain("executionStats")` on fixture. For `category_name A–Z`, join `categories` (e.g. `$lookup` and sort `name_key`) or controlled denormalization + migration; measure query cost. Avoid `priority` lexical sort. Exclude future locked plaintext by design when FR-14 introduces `content_encrypted`.

## 6. Sorting + keyset cursor contract

- Always append unique `_id` tie-break in same direction for deterministic pagination. A cursor captures `{version, query_fingerprint, sort_field, direction, last_sort_key, last_id}`; for category sort include normalized `name_key`. Validate cursor size/type; **never** parse it via string-to-code or trust raw JSON as pipeline.
- Seek predicate for descending `(updated_at,_id)` is `updated_at < t OR (updated_at=t AND _id<id)`. For ascending, invert. For category: seek on the computed normalized category key + stable tie. Test missing/unclassified category placement explicitly.
- If user changes sort/filter/search, old cursor must be invalidated and all existing rows cleared/reset. A stale cursor presented to different query should raise typed invalid-input error, not silently return mixed pages.
- If a note already fetched changes timestamp while paginating, cursor paging isn't snapshot isolation. Define user-facing refresh semantics and acceptance tests; **do not promise no omission under arbitrary concurrent edits** without snapshot pagination architecture.

## 7. Tkinter request lifecycle

```text
User types/query changes on main thread
  → cancel pending main-thread root.after timer
  → increment search_generation / freeze typed snapshot
  → root.after(300ms, submit snapshot)  [Search debounce]
  → TaskRunner executes use case in worker; emits OperationResult
  → UIEventPump polls Queue on Tk main thread
  → presenter checks generation/fingerprint/view-alive
  → render page OR loading/error/empty; stale result ignored
```

**Responsiveness:** No PyMongo calls, `.find()`, `aggregate()` or timezone network lookup in widget handlers. Disable `Load more` if query pending. For rapid search input, limit pending TaskRunner submissions; optionally cancellation token for unstarted tasks, never rely on forcibly killing DB calls. `request_close()` must cancel debounce `after` ID before root destroy.

## 8. Acceptance examples (test expected behavior)

| ID | Input | Expected |
|---|---|---|
| Q-01 | title-only `Kế hoạch`, content-only `họp` | both searchable as semantics allow; index used |
| Q-02 | text+category+priority+date | intersection; only active notes |
| Q-03 | future date / reversed dates | no result / ValidationError respectively |
| Q-04 | `HIGH, LOW, MEDIUM` order | `HIGH, MEDIUM, LOW` |
| Q-05 | 40 notes, limit 30 then 10 | exactly 40 distinct IDs, predictable order |
| Q-06 | Input `a` then `ab`, response `a` arrives late | only `ab` shown |
| Q-07 | Filter changes before page-2 response | old response discarded, no mixed rows |
| Q-08 | 10k seed + 100 searches | p95/time/index explain logged; **pass NFR only if measured below target** |
| Q-09 | soft-deleted note matching title | absent from active search and filters |

## 9. Compatibility + rollback

- Test all Phase1 `ListNotes` and `MongoNoteRepository` contract tests unchanged.
- Migration/index setup idempotent; apply only additive fields/indexes; no dropping existing collections/indexes without approved migration.
- Rollback Phase2 feature commits should not destroy Phase1 data; if index created but code rolled back, keep index harmless until a separate approved cleanup task.
- SQLite is **not** a second adapter deliverable of W3; do not block W3 on standalone offline design.
