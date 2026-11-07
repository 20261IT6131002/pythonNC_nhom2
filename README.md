# NoteApp — R1 pinned notes, categories, images and reminders

Python >=3.10, Tkinter/ttkbootstrap, PyMongo, isolated local MongoDB.
Phase 1 implements text create/list/edit, category lookup, priority, idempotent
create and optimistic updates. Track delivered tasks and remaining artifacts in
the [Phase 1 task board](docs/srs/phase%201/PHASE1_TASK_BOARD.md) and
[current handover evidence](docs/testing/PHASE1_TASK_BOARD_FOLLOWUP_2026-10-10.md).
The earlier [foundation evidence](docs/testing/PHASE1_IMPLEMENTATION.md) is historical;
approvals already confirmed in the blocker follow-up are not requested again.

Phase 2 adds native title/content search, category/priority/local-day filters,
five sort choices, keyset pages, versioned trash/restore and confirmed permanent
deletion. Track implementation and review gates in the
[Phase 2 board](docs/srs/phase%202/02_PHASE2_TASK_BOARD.md) and
[test report](docs/testing/PHASE2_TEST_REPORT.md). The UI follows the supplied
sketch and uses packaged Google Material Icons with their Apache-2.0 license.

Phase 3A (plan: [PHASE3_PLAN_01_CATEGORY_IMAGE.md](docs/srs/phase%203/PHASE3_PLAN_01_CATEGORY_IMAGE.md),
contract: [freeze](docs/srs/phase%203/01_PHASE3_CONTRACT_FREEZE.md), ADR:
[ADR_PHASE3_CATEGORY_ATTACHMENT](docs/adr/ADR_PHASE3_CATEGORY_ATTACHMENT.md)) adds:

- **Category management** (sidebar → *Quản lý danh mục*): create, rename, recolor, delete.
  Names are unique after trim/NFC/casefold (DB unique index); a category still referenced by
  any note, including trashed ones, cannot be deleted. Rename keeps the note link.
- **One image per note** (editor → *Chọn ảnh…*): PNG/JPEG/GIF/WebP verified by decoding,
  <= 10 MiB, <= 25 megapixels; <= 1 MiB stored as BinData, larger in GridFS; 400 px wide
  thumbnail. Replace/remove keep the old image until the note update succeeds. Trash and
  restore keep the image; permanent delete and retention remove it.
- `scripts/run_retention.py --apply` also sweeps payloads no note references (older than
  15 minutes). The same job runs in the app only with `NOTEAPP_ENABLE_RETENTION=1`.

The category-delete rule and one-image-per-note are **assumptions awaiting team approval**
(SRS DEC-06 and AC-04b are still open).

Phase 3B (plan: [PHASE3_PLAN_02_REMINDER_DELIVERY.md](docs/srs/phase%203/PHASE3_PLAN_02_REMINDER_DELIVERY.md),
contract: [freeze](docs/srs/phase%203/02_PHASE3_REMINDER_CONTRACT_FREEZE.md), ADR:
[ADR_PHASE3_REMINDER_DELIVERY](docs/adr/ADR_PHASE3_REMINDER_DELIVERY.md)) adds:

- **Reminders** (editor → *Đặt nhắc…* / *Đổi nhắc…* / *Hủy nhắc*): enter local date and time
  (dd/mm/yyyy, HH:MM); stored as UTC. Past times and local times skipped or repeated by a
  DST change are rejected. States are `ACTIVE`, `DELIVERED`, `CANCELLED`.
- **Delivery while the app is open**: a startup scan delivers reminders that came due while
  the app was closed, then a background poller checks every `NOTEAPP_REMINDER_POLL_SECONDS`
  (default 30, allowed 5–3600). An atomic lease claim stops two pollers from delivering the
  same reminder. Notes in the trash stay silent; a restored overdue reminder fires next poll.
- Delivery is **best effort, not exactly-once**. `DELIVERED` means the operating system
  accepted the notification call; it does not prove the toast was shown. A failed OS
  notification is retried up to 3 times (1 then 5 minutes), after which the reminder stays
  `ACTIVE` and is shown as waiting; set a new time to retry. Nothing is delivered while the
  app is closed. On Linux, `plyer` needs a notification service (for example `notify-send`).

Reminder behaviour for rescheduling a delivered reminder and the missed-reminder rule are
**assumptions awaiting approval** (SRS DEC-05 is still open).

## R1 pinned notes (FR-12)

Use **Ghim / Bỏ ghim** in a saved note's toolbar or on its card. Press **P** on a
selected card as a keyboard alternative. Pinned notes come first for all five active
sort choices and within matching search/filter results. Trash keeps the flag but
does not offer pin actions or change its ordering. Restore brings back the pin.
Pin changes use version CAS, preserve modification time and keep unsaved editor text.

Plan: [R1-01](docs/srs/r1/R1_PLAN_01_PINNED_NOTES.md); [contract](docs/srs/r1/01_R1_PIN_CONTRACT_FREEZE.md);
[ADR](docs/adr/ADR_R1_PINNED_NOTES.md); [validation](docs/testing/R1_PIN_TEST_REPORT.md).
PIN-D01..D14 are implemented assumptions awaiting team review; this does not approve
other open SRS decisions.

Before opening an existing DB with this version, stop all old/new app instances and
back up MongoDB plus attachment data using the existing backup procedure. Set the
intended `NOTEAPP_MONGO_URI` and `NOTEAPP_DB_NAME`, then run:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_pinned.py --plan
.\.venv\Scripts\python.exe scripts/migrate_pinned.py --apply
.\.venv\Scripts\python.exe scripts/migrate_pinned.py --plan
.\.venv\Scripts\python.exe scripts/create_indexes.py
```

Plan only reports counts. Apply fills missing `is_pinned` with false, including trash,
and refuses existing values of the wrong type. Repeating apply modifies zero records.
It preserves version, timestamps, content, attachments, reminders and schema_version.
Startup refuses unnormalized data. A fresh/empty database needs no migration.
Indexes are additive; old cursors are rejected and the app starts a new page.

Rollback the feature code while leaving the added boolean/indexes in place; no field
removal is necessary. The additive field is safe to retain, but the pre-R1 purge
whitelist may refuse these notes, so pause purge/retention until an independent
rollback review updates that whitelist. Do not unset stored pin flags automatically.

## R1-02 secure storage foundation

The next [execution plan](docs/srs/r1/R1_NEXT_EXECUTION_PLAN_FR17_FR14.md) separates
secure storage (R1-02), encrypted draft recovery (R1-03) and locked notes (R1-04).
R1-02 introduced typed cipher/secret-store ports, an immutable
encrypted envelope, AES-256-GCM, strict envelope serialization and an explicit OS
keyring adapter. It adds no autosave, recovery dialog or lock UI, and changes no Mongo
schema. FR-17 and FR-14 are described separately below.

The native secret adapter selects Windows Credential Manager (local-machine
persistence), macOS Keychain or Linux Secret Service. It fails closed when access is
unavailable or denied, and never selects a plaintext/file backend or invents a missing
key. Linux needs a working user-session Secret Service; a headless server may have
none. No application encryption key is provisioned at startup by this foundation.

Dependencies: `cryptography>=50.0.2,<51`, `keyring>=25.7,<26`. Public ports do not import
either library. Call adapters from workers when integrating the later use cases.
The [contract](docs/srs/r1/02_R1_SECURE_STORAGE_CONTRACT_FREEZE.md) and
[ADR](docs/adr/ADR_R1_SECURE_STORAGE.md) remain proposed pending independent review.
See [secure-storage validation](docs/testing/R1_SECURE_STORAGE_TEST_REPORT.md) for
executed tests, packaging evidence and unverified platform/CI gates.

To run the native credential smoke explicitly on a supported desktop, it creates
and removes one randomly named synthetic entry inside the NoteApp service namespace:

```powershell
$env:NOTEAPP_TEST_NATIVE_SECRET_STORE = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_native_secret_store.py
```

For a wheel smoke (installed imports, AEAD roundtrip and packaged icon, without native
keyring access):

```powershell
.\.venv\Scripts\python.exe -m pip wheel --no-deps --wheel-dir .pytest_cache/secure-wheels .
.\.venv\Scripts\python.exe scripts/verify_secure_storage_package.py .pytest_cache/secure-wheels
```

The foundation itself has no Mongo migration. Once R1-03 has written drafts,
preserve their ciphertext and OS keys during rollback.

## R1-03 encrypted local draft recovery (FR-17)

Text, title, priority, category, operation ID and base version are snapshotted after
750 ms of inactivity. Encryption, native keyring access and file I/O run in workers.
The UI distinguishes **local draft saved** from **saved to MongoDB**; remote failures
leave the editor and the last successfully written encrypted snapshot available.

On restart, **Bản nháp** offers explicit recover, keep and confirmed delete actions,
even when Mongo is unavailable. Recover restores unsaved content; reconnect and
press **Lưu** to save remotely. New notes reuse their operation ID across restarts,
including a lost remote acknowledgement. Existing notes retain their base version;
conflicts keep both versions and require an explicit user decision. A matching
remote acknowledgement removes only the covered local revision.

Default storage is `%LOCALAPPDATA%/NoteApp/drafts/<profile>` on Windows,
`~/Library/Application Support/NoteApp/drafts/<profile>` on macOS, or
`${XDG_DATA_HOME:-~/.local/share}/NoteApp/drafts/<profile>` on Linux. The profile is
an opaque hash of the database name; its random master key lives in the native OS
credential store. Optional `NOTEAPP_DRAFT_DIR` selects an absolute profile directory.
Keep its location stable: key names are tied to the normalized directory path.
Only one running app may write a profile at a time.

The file wrapper contains an opaque ID and authenticated ciphertext. Temporary
files are encrypted too. Missing keys, denied keyring access, tampering or write
failure produce a warning and preserve existing data; there is no plaintext
fallback or replacement key for existing ciphertext. Draft payloads are bounded
to **1 MiB serialized UTF-8**, independently of remote-note validation. An oversized
draft remains in memory with a warning and may still be saved remotely.

An abrupt process exit preserves the last acknowledged snapshot; keystrokes inside
the debounce window may not have reached disk. Attachment binaries, reminder
schedules and locked-note recovery are outside this slice. Graceful close gives
workers a bounded UI grace period; an already running native I/O call may still
finish during runtime shutdown.

See the [contract](docs/srs/r1/03_R1_DRAFT_RECOVERY_CONTRACT_FREEZE.md),
[ADR](docs/adr/ADR_R1_DRAFT_RECOVERY.md) and
[validation report](docs/testing/R1_DRAFT_RECOVERY_TEST_REPORT.md). Contract decisions
remain proposed, and remote CI plus independent review remain release gates.
Rollback stops the app and reverts the grouped R1-03 commits without deleting
encrypted files or their OS credential entries. No Mongo schema migration is needed.

## R1-04 locked notes (FR-14)

Use **Bảo mật → Khóa ghi chú / Lưu với khóa** to lock a saved note or
create a new note directly with encryption. Save any changes to an existing
plaintext note before locking. Enter and confirm a passphrase of at least 12
characters. Keep it safe because forgotten passphrases cannot be recovered.

Select a locked note and use **Mở khóa trong phiên** to view or edit. Save as
usual to encrypt the new revision. Use **Khóa lại** to close the session, or
leave the editor to clear it. The editor also relocks after five minutes idle,
with a warning if its latest draft write could not be confirmed. **Đổi cụm mật
khẩu** re-encrypts with a new phrase. **Bỏ khóa vĩnh viễn** asks for confirmation
before restoring plaintext storage.

Lists and search hide the private title and content. Desktop reminders use a
generic message. Attachment bytes and metadata remain outside the locked content.
Previous database backups and exports can still contain historical plaintext.
If locked data has been written, keep a v3-capable reader when rolling back.
See the [contract](docs/srs/r1/04_R1_LOCKED_NOTE_CONTRACT_FREEZE.md) and
[verification report](docs/testing/R1_LOCKED_NOTES_TEST_REPORT.md).

## Windows setup

Python 3.12 is preferred; 3.11 also works (used for this checkout).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
docker compose -f compose.dev.yml up -d --wait
$env:NOTEAPP_MONGO_URI = "mongodb://127.0.0.1:27017"
$env:NOTEAPP_DB_NAME = "noteapp_dev"
.\.venv\Scripts\python.exe scripts/create_indexes.py
.\.venv\Scripts\python.exe scripts/seed_notes.py --count 35
.\.venv\Scripts\python.exe -m noteapp.main
```

## Linux / macOS setup

Install Python's Tk system package if your interpreter lacks Tkinter (Ubuntu:
`python3-tk`). Then:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
docker compose -f compose.dev.yml up -d --wait
export NOTEAPP_MONGO_URI=mongodb://127.0.0.1:27017
export NOTEAPP_DB_NAME=noteapp_dev
python scripts/create_indexes.py
python scripts/seed_notes.py --count 35
python -m noteapp.main
```

`.env.example` documents variables; export them explicitly. No implicit .env loader.
Only loopback Mongo and `noteapp_dev*` / `noteapp_test_*` databases are allowed in
this technical slice. The local Docker port binds 127.0.0.1 and uses a dedicated
named volume. No production database, automatic migration, TTL, or public Mongo service.
`docker compose -f compose.dev.yml stop` preserves development data.

## Checks

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q tests/unit tests/contract
$env:NOTEAPP_TEST_MONGO_URI = "mongodb://127.0.0.1:27017"
$env:NOTEAPP_REQUIRE_MONGO = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration
.\.venv\Scripts\python.exe -m pytest -q tests/ui
```

On Unix use `python` after activating the venv. Integration tests skip with an
explicit reason when Mongo is absent locally; `NOTEAPP_REQUIRE_MONGO=1` makes
missing Mongo a failure. They create a random `noteapp_test_*` DB per fixture and
only drop that generated database. UI tests require a display; unit/contract tests
never create a Tk root. CI provisions Mongo and requires integration tests.

## User flow

Use **Mới** / Ctrl+N to compose, **Lưu** / Ctrl+S to persist. Select a list entry
to edit it. **Tải thêm** fetches the next page of 30 notes; **Làm mới** reloads the
first page. Select priority/category in the editor. Saved timestamps display in
your OS timezone; persistence uses UTC. Save errors preserve the text. A conflict
requires reloading the server version or starting a new note; it never overwrites
a stale version silently. R1-03 adds the encrypted local snapshots described above.
Closing or switching notes prompts before discarding unsaved changes.

Ctrl+F focuses search. Text search uses Mongo native tokens/phrases; `học` and
`hoc` match alike under the chosen options, while substring matching and Vietnamese
stemming are not provided. Category, priority and local ISO date filters combine
by intersection. Empty dates leave that side unbounded. Choose the date field and
sort from the sidebar; **Xóa bộ lọc** resets all search criteria. **Thùng rác** opens
a read-only note view with **Khôi phục** and **Xóa vĩnh viễn**. Permanent deletion
requires a yes/no confirmation; cancel preserves the database row.

Windows timezone discovery uses tzlocal + IANA tzdata. Set `NOTEAPP_TIMEZONE` to an
IANA name such as `Asia/Ho_Chi_Minh` to override it. An unresolved timezone or an
ambiguous/missing local midnight rejects dated filters instead of guessing.

Index preflight: `python scripts/create_indexes.py --dry-run` reports schema/index
status with no writes. Applying indexes is additive; incompatible indexes or TTL
fail preflight. Old active notes stay schema v1; trash transitions lazily add v2
tombstones, preserving IDs/content/version history. Review schema/contract choices
before integration; no production migration is performed here.

Automatic text-only retention is opt-in with `NOTEAPP_ENABLE_RETENTION=1` after
safety review. While the app is open it schedules a bounded 100-row job each minute
on the existing worker pool. Only verified text records deleted at least 30 days
ago qualify; CAS protects restore races, unknown/attachment/locked fields remain
untouched and no TTL is installed. `python scripts/run_retention.py` inspects
eligibility; `--apply` explicitly performs one bounded batch. A git revert cannot
recover permanently purged data.

Phase 3 adds images, categories and reminders; R1 adds pinning and encrypted local
draft recovery. Rich text, locked notes/PIN and export remain pending.
