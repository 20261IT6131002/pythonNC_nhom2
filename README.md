# NoteApp — Phase 1 foundation

Python >=3.10, Tkinter/ttkbootstrap, PyMongo, isolated local MongoDB.
Phase 1 implements text create/list/edit, category lookup, priority, idempotent
create and optimistic updates. Track delivered tasks and remaining artifacts in
the [Phase 1 task board](docs/srs/phase%201/PHASE1_TASK_BOARD.md) and
[current handover evidence](docs/testing/PHASE1_TASK_BOARD_FOLLOWUP_2026-10-10.md).
The earlier [foundation evidence](docs/testing/PHASE1_IMPLEMENTATION.md) is historical;
approvals already confirmed in the blocker follow-up are not requested again.

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
named volume. No production database, migration, TTL, or public Mongo service.
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
a stale version silently. Unsaved content is held only in memory in Phase 1.
Closing or switching notes prompts before discarding unsaved changes.

Images, search/filtering, deletion/trash, reminders, encryption/export and local
draft recovery are deferred scaffold modules, not implemented features.
