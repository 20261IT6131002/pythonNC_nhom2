# Phase 2 public interfaces — P2-02 / D0

**Status:** Proposed / REQUEST_CHANGES, version `P2-CONTRACT-1`, review revision 2,
2026-10-10. Not Accepted/Frozen; missing value comparisons are tracked exclusively
in the ADR canonical decision trace (CF-01), including reconfirmed decision status.
Authority: [ADR-0002](../adr/0002-phase2-query-trash-contract.md),
[task board](../srs/phase%202/02_PHASE2_TASK_BOARD.md).
Requirements: FR-03/06/07/11 Shall, FR-13 Should; FR-04/05 filtering,
NFR-SEC-03, CST-03. Original requirement priorities do not change.

This document selects exact names from the plan's illustrative alternatives.
The declarations below are **planned interfaces**, not code installed in `src`.
P2-03/04 and P2-09/10 implement and validate them after review. Existing Phase 1
`ListNotesInput`, `NoteRepository`, `CategoryRepository`, `Clock`, `Note`,
`NoteView`, `NoteListView` and create/update signatures remain unchanged.

## 1. Search input and normalized repository criteria

Planned location: `application/dto/note_filter.py`, alongside `ListNotesInput`.
Enums use allowlisted values; a GUI label or raw Mongo field/operator is never
accepted as an unchecked query fragment.

```python
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from noteapp.domain.value_objects.priority import Priority


class DateField(str, Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class SortMode(str, Enum):
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"
    PRIORITY = "priority"
    CATEGORY = "category"


class SortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


@dataclass(frozen=True)
class SearchNotesCriteria:
    text: str = ""
    category_id: str | None = None
    priority: Priority | None = None
    start_date: date | None = None
    end_date: date | None = None
    date_field: DateField = DateField.UPDATED_AT
    sort: SortMode = SortMode.UPDATED_AT
    direction: SortDirection = SortDirection.DESC
    limit: int = 30
    cursor: str | None = None


@dataclass(frozen=True)
class CompiledNoteCriteria:
    text: str
    category_id: str | None
    priority: Priority | None
    utc_start: datetime | None
    utc_end_exclusive: datetime | None
    date_field: DateField
    sort: SortMode
    direction: SortDirection
    limit: int
    cursor: str | None
```

`SearchNotesCriteria` is the canonical public name (the plan's `SearchNotesInput`
is illustrative); `sort`/`limit` are canonical, without duplicate `sort_field`
or `page_size` aliases. M3 owns these declarations and validation.

Input rules to implement under P2-03/04:

- `text`: string, trim leading/trailing whitespace; empty means no text clause.
  Preserve interior spaces, punctuation, quotes and Unicode. Reject dictionaries,
  lists and BSON objects, not literal strings such as `$where` or JSON-like text.
  Mongo search-language interpretation must match DEC-07; string acceptance alone
  does not promise a particular token/phrase match.
- `category_id`: None means all categories; a nonblank opaque string means equality.
  Reject empty/non-string IDs. An unknown valid category yields an empty result;
  do not rewrite it to None and accidentally return all notes.
- Optional priority and all enums: validate allowlisted enum values; reject unknown
  values before any repository call. No raw filter/sort dictionaries.
- Local bounds are `date`, not `datetime` or unchecked strings; if both exist,
  require start <= end. One-sided ranges/default date field are A2-Q01 assumptions.
  Convert local midnight and midnight after the end date independently to aware UTC;
  never add a fixed 24h to a UTC instant on a DST transition. Overflow/nonexistent
  or ambiguous local midnight requires ValidationError, not silent correction.
- `limit`: exact integer 1..100 (bool invalid), default 30. `cursor`: None or a
  nonempty string; structural/provenance checks belong to its repository adapter.
  No search-text cap is implied by a pagination or cursor bound.
- A compiled criterion contains only normalized strings/enums/UTC bounds; it is
  never a Mongo filter. Adapters still validate the types and bounds they receive.

Use-case signature for P2-03/04:
`SearchNotes(repo: SearchRepository, local_timezone: tzinfo | None)`;
`execute(command: SearchNotesCriteria) -> NoteListView`.
Inject a real IANA ZoneInfo through bootstrap. None represents unavailable zone
resolution: queries without date bounds and Phase1 CRUD still work, while any dated
query fails ValidationError before repository access. Do not silently substitute
UTC or today's fixed local offset for a historical timezone.

### Timezone resolution and Windows data — CF-04

Planned P2-04 infrastructure resolver, owned by M4 with M3 date conversion and
M5 tests: explicit `NOTEAPP_TIMEZONE` IANA key takes precedence; otherwise resolve
an unambiguous OS IANA identity. This is a proposed configuration addition, not
a variable already supported by the current app.

On Windows, obtain the Windows timezone key in infrastructure and map it through
a versioned, territory-aware CLDR Windows-to-IANA mapping. Record the mapping
version/source; ambiguous/multiple results require an explicit IANA override,
not choosing a guessed zone or abbreviation. CLDR describes these territory-aware
mappings. [Unicode CLDR mapping](https://cldr.unicode.org/development/development-process/design-proposals/extended-windows-olson-zid-mapping)

ZoneInfo uses system IANA data or the first-party `tzdata` package; Windows often
needs that package. P2-04 must declare/package `tzdata` in pyproject with a reviewed
version range and include it in Windows installs and all required timezone tests.
The package supplies rules, not OS timezone identity. Neither mapping nor tzdata
is fetched over the network from a widget handler. Missing key/mapping/data produces
a sanitized date-filter error. [Python 3.11 ZoneInfo data sources](https://docs.python.org/3.11/library/zoneinfo.html#data-sources)

On Unix, use a valid configured TZ/IANA key or a resolvable system zone identity;
if only an unnamed TZif/fixed offset is available, require explicit configuration.
Resolve outside the core; core receives ZoneInfo/None and does no registry/file I/O.
Cache resolution for a request snapshot and invalidate when configuration changes.

For each local midnight boundary, evaluate fold=0 and fold=1, convert to UTC and
round-trip to local wall time. Deduplicate valid UTC instants: zero means nonexistent,
two means ambiguous, and one is usable. Fail ValidationError for zero/two; the
default fold alone must not silently select an ambiguous boundary. Compute the end
from the next local calendar date independently; reject date.max overflow.

P2-04/16 acceptance fixtures (future tests, not results from this D0 check):

| Zone/case | Required result |
|---|---|
| Asia/Ho_Chi_Minh, 2026-10-10 | UTC bounds 2026-10-09 17:00 to 2026-10-10 17:00 |
| America/New_York, 2026-03-08 | UTC 05:00 to next day 04:00; 23-hour interval |
| America/New_York, 2026-11-01 | UTC 04:00 to next day 05:00; 25-hour interval |
| Synthetic deterministic midnight gap/fold fixture | ValidationError for missing/ambiguous midnight, no repository call |
| Windows mapping unavailable, invalid IANA key, missing tzdata/system data | Dated query rejected; undated query/CRUD available; required tests fail instead of skip |
| Explicit valid override on Windows | Same bounds as IANA fixture; no fixed-offset fallback |

## 2. Search port, ordering and cursor

Planned location: `application/ports/note_query_repository.py`.

```python
from typing import Protocol

from noteapp.application.ports.note_repository import NotePage


class SearchRepository(Protocol):
    def search(self, criteria: CompiledNoteCriteria) -> NotePage:
        """Return a bounded active-note page or a typed core error."""
```

The port imports `CompiledNoteCriteria` from the DTO module in its actual
implementation. The declarations in this document share one namespace.
The use case maps `NotePage` into the existing `NoteListView`; infrastructure
returns domain notes, not widgets/BSON or a GUI-specific query result.

| Mode | Direction allowed | Exact ordering tuple | AC |
|---|---|---|---|
| UPDATED_AT | DESC | `(updated_at DESC, id DESC)` | P2-AC07/08 |
| CREATED_AT | ASC / DESC | `(created_at, id)` in requested direction | P2-AC07/08 |
| PRIORITY | DESC | `(priority_rank DESC, updated_at DESC, id DESC)` | P2-AC06/08 |
| CATEGORY | ASC | `(category.name_key ASC, id ASC)` | P2-AC06/08 |

Reject other mode/direction combinations as ValidationError. Priority rank is
3/2/1, not enum-string lexical order. Resolve category by canonical `category_id`
against `categories.name_key`; no category-name duplication in notes. Ordinal
casefold name order and missing-category placement are A2-Q02 assumptions, not
a claim of locale-aware Vietnamese alphabetical collation.
P2-05/06 must prototype the exact lookup/text/seek pipeline and performance
obligations in [the category query plan](PHASE2_CATEGORY_QUERY_PLAN.md) (CF-07).
Neither this tuple nor a category_id index proves the <200ms NFR target.

All search criteria intersect and all queries exclude `is_deleted:true`.
Only Mongo builds `$text`, seek predicates and category lookup. Text relevance
does not introduce a sixth sort mode. Never scan/sort the whole collection in Tk.

Cursor wire ownership: M4, decoded only inside infrastructure. Proposed version 1
payload is `{version, namespace, query_fingerprint, sort, direction,
last_sort_key, last_id}` with namespace `active_search`; use canonical JSON encoded
as URL-safe base64. Decode an encoded string of at most **2048 ASCII characters**
with checked field set, version, namespace, enum values, ID and sort-key arity/types.
This is a technical resource bound, not an SRS text-content limit.

Fingerprint: SHA-256 of canonical UTF-8 JSON with sorted keys containing trimmed
text, category, priority, date field, normalized UTC bounds, sort, direction and
limit, excluding the cursor itself. It binds query identity, not authentication.
Cursor values are untrusted; validate before constructing any seek predicate.
Use timestamp precision read back from Mongo, not a pre-write microsecond value.

Seek on the complete ordering tuple, always ending with unique ID. Reject a cursor
from another namespace/query/sort as ValidationError; never fall back to page 1.
A new higher-sorted insert between pages must not repeat an earlier row. Existing
records edited/deleted while paging are not a snapshot: Refresh starts from page 1.
Category rename can change ordering and requires Refresh, not an omission guarantee.

## 3. Trash inputs, port records and public views

Planned input location: `application/dto/note_input.py`, alongside existing inputs.

```python
@dataclass(frozen=True)
class TrashNoteInput:
    note_id: str
    expected_version: int


@dataclass(frozen=True)
class RestoreNoteInput:
    note_id: str
    expected_version: int


@dataclass(frozen=True)
class PurgeNoteInput:
    note_id: str
    expected_version: int
    confirmed: bool = False


@dataclass(frozen=True)
class ListTrashInput:
    limit: int = 30
    cursor: str | None = None
```

IDs are existing opaque note IDs, not a new UUID that creates another note.
Expected version is an exact integer >=1. The use case requires `confirmed is True`
for purge; this flag expresses explicit intent, not identity/authorization proof.
Canceling the UI modal never submits a task or calls the repository. Application
validation independently rejects False/missing/non-bool confirmation with no write.

Planned repository records/location: `application/ports/trash_repository.py`.

```python
from noteapp.domain.entities.note import Note


@dataclass(frozen=True)
class TrashedNote:
    note: Note
    deleted_at: datetime


@dataclass(frozen=True)
class TrashPage:
    items: tuple[TrashedNote, ...]
    next_cursor: str | None


class TrashRepository(Protocol):
    def move_to_trash(
        self, note_id: str, expected_version: int, now: datetime
    ) -> TrashedNote:
        """Atomically transition active -> trash or raise a typed error."""

    def restore(self, note_id: str, expected_version: int, now: datetime) -> Note:
        """Atomically restore the same note ID or raise a typed error."""

    def list_trashed(self, limit: int, cursor: str | None = None) -> TrashPage:
        """Return trash ordered by deleted_at DESC, id DESC."""

    def purge_confirmed(self, note_id: str, expected_version: int) -> None:
        """Permanently remove confirmed, verified text-only trash after CAS."""
```

Planned public output location: `application/dto/note_view.py`.

```python
from noteapp.application.dto.note_view import NoteView


@dataclass(frozen=True)
class TrashedNoteView:
    note: NoteView
    deleted_at: datetime


@dataclass(frozen=True)
class TrashListView:
    items: tuple[TrashedNoteView, ...]
    next_cursor: str | None
```

Repository `TrashedNote` is mapped to `TrashedNoteView` by the use case;
`deleted_at` and all other persistence times are aware UTC, rendered local in UI.
No deletion fields are added to the old `NoteView` positional constructor.

Use-case signatures for P2-09/10 (Clock is the existing application port):

| Constructor | execute signature |
|---|---|
| `TrashNote(repo: TrashRepository, clock: Clock)` | `(command: TrashNoteInput) -> TrashedNoteView` |
| `RestoreNote(repo: TrashRepository, clock: Clock)` | `(command: RestoreNoteInput) -> NoteView` |
| `PurgeNote(repo: TrashRepository)` | `(command: PurgeNoteInput) -> None` |
| `ListTrash(repo: TrashRepository)` | `(command: ListTrashInput) -> TrashListView` |

Each state change targets the expected state AND version in one atomic operation.
Trash increments version and sets deleted_at; restore increments version and unsets
deleted_at, preserving ID/content/category/priority/created_at. A2-T01 proposes
updating updated_at for both transitions. A2-T02 proposes restore until actual purge;
both values remain blocked on the ADR evidence trace rather than agreed by default.
Purge performs a conditional removal; no version increment on a nonexistent row.

Repeated old-version actions and wrong-state actions raise Conflict without another
write; missing/purged IDs raise NotFound. A lost ACK followed by retry may therefore
return Conflict/NotFound and needs reload/reconciliation; it cannot be called a
confirmed success or recreated implicitly. No new mutation-operation ID is added.

Trash cursors use a distinct `trash_list` namespace and `(deleted_at,id)` seek key;
never accept a Phase 1 recent-list or active-search cursor. Same size/type/version
checks apply. The fingerprint binds this view, ordering and page limit.

## 4. Error, worker and security contracts

| Situation | Core error / result envelope | Writes allowed |
|---|---|---|
| Bad input, enum, dates, limit, cursor or confirmation | ValidationError -> VALIDATION | None |
| Unknown valid category in search | Empty NoteListView | None |
| Missing/purged note for mutation | NotFound -> NOT_FOUND | None |
| Stale version, wrong state, competing CAS winner | Conflict -> CONFLICT | None for rejected action |
| DB failure/unacknowledged operation | RepositoryUnavailable -> UNAVAILABLE | Outcome may be unknown; never report success |
| Unsupported stored schema / corrupt tombstone | RepositoryUnavailable -> UNAVAILABLE | None; repair/review separately |
| Attachment/locked-record purge without verified cleanup | ValidationError -> VALIDATION | None; fail closed |
| Worker admission limit | Existing BUSY/UI busy state | None for unsubmitted request |
| Unexpected exception | Existing UNEXPECTED | Preserve editor; no raw error text |

Reuse `OperationResult` and existing ErrorCode members; no new driver messages,
exception text, note content, query text, URI or secrets enter the result envelope
or logs. New error types require contract review, not an implicit mapping change.

W3 P2-12 still owes real automatic 30-day retention for verified text-only trash,
including cutoff, bounded scans, stale-candidate/restore races and retry tests.
Enable only after that task's safety gate. Unknown attachment/locked formats remain
untouched; W4 owns their real cleanup. This is not a scope move of automatic
retention to W4 and cannot make AC14 pass from manual purge tests alone.

M2 schedules debounce/main-thread dialogs, increments generation on query/view
changes, resets list/cursor and freezes input before submit. TaskRunner workers
return DTO/error envelopes only; UIEventPump checks generation/view lifetime.
Query identity is tied to the submitted snapshot, not reread controls. No new
fingerprint field is required in `NoteListView`; presenter request state owns it.
Drop stale page responses, cancel scheduled debounce on close, preserve unsaved
editor content through filters, errors and delete/save races.

## 5. Contract acceptance cases for downstream tests

| Case | Expected | Owner/task | AC |
|---|---|---|---|
| Default/empty search, unknown category, combined valid filters | Bounded active results / empty unknown category / intersection | M3/M4/M5, P2-03/06/15 | 04/08 |
| Raw dict, invalid enum/direction, bool limit/version, blank ID/cursor | Typed ValidationError before query/write | M3/M5, P2-03/10/15/17 | 16 |
| Equal local dates, reversed bounds, date.max overflow, 23/25h day | Half-open UTC bounds or ValidationError; no fixed 24h conversion | M3/M5, P2-04/16 | 05 |
| Priority mixed/equal rank, category IDs opposite name order | Rank/name-key tuple order, stable ID tie | M4/M5, P2-06/16 | 06/07 |
| 65 rows, equal times, newer insert, reused cursor on another query | Distinct bounded static pages; no earlier duplicate; invalid old cursor | M4/M5, P2-06/16 | 08 |
| Vietnamese accents/phrase/composed Unicode | Compare real Mongo results against supplied DEC-07 cases; no invented matches | M4/M5, P2-05/15 | 01/02 |
| Delete correct version, repeat old version, save races delete | One transition/one winner; UTC deleted_at; rejected stale action | M3/M4/M5, P2-09..11/17 | 09/13 |
| Restore right/wrong state/version, restore after purge | Same ID/new version or Conflict/NotFound, no resurrection | M3/M4/M5, P2-09..11/17 | 11/13 |
| Cancel/default-false purge, active note, unsupported attachment/schema | Zero writes; typed failure | M2/M3/M4/M5, P2-10/11/14/17 | 12/16 |
| Confirmed text-only trash purge races restore | One conditional winner; no unconditional deletion after restore | M4/M5, P2-11/17 | 12/13 |
| Missing deleted_at on v1 active vs damaged deleted record | Active readable; invalid trash never guessed eligible for purge | M4/M5, P2-11/17 | 17/19 |
| DB outage, late search/page/mutation result, window close | Safe error, no false ACK or destroyed-widget callback | M2/M5, P2-08/14/18 | 03/15/16 |

AC numbers refer to P2-ACxx in the Phase 2 RTM. These cases are future obligations,
not Phase 2 test results. Independent review and approved P2-01 values precede
merging affected production behavior.
