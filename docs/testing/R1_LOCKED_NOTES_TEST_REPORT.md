# R1-04 Locked Notes test report

2026-11-07. Isolated Linux x86-64, CPython 3.12, MongoDB 7.0.28 and Tk under Xvfb.
Base `6757833c601bcdf3b074241742db093cb383edc5`. All database names in the
test fixture are generated under `noteapp_test_`. Desktop tests substitute
synthetic passphrase prompts and, for crash recovery, the device-key port.

| Coverage | Evidence |
| --- | --- |
| TC-SEC-001 | Real Mongo BSON has no `content_plain` after create, lock, edit or recovery. Restart unlocks with the correct phrase. |
| TC-SEC-002 | Wrong passphrase and altered GCM ciphertext fail authentication. Copying a payload to another note fails AAD binding. An unsupported KDF cost is rejected before key derivation. |
| TC-SEC-003 | Native `$text` canaries disappear after lock. Lists and trash mask the title. The notification spy receives generic text. The encrypted draft file contains neither its content marker nor the passphrase. |
| TC-SEC-004 | Edit and rekey change salt and nonce. The old phrase fails after rekey. Explicit removal returns plaintext only after confirmation. |
| FR-02, FR-09/10, FR-12, FR-13 | Direct plaintext CAS against a locked version fails. Pin, reminder, trash and restore preserve ciphertext. Confirmed purge removes the record. |
| FR-17 | Reopened encrypted draft retains its base version. Bad phrase and wrong ACK revision preserve the draft. The desktop crash/restart test exercises explicit authentication, locked save and revision-conditional draft cleanup. |

Commands used for regression, with the test-only Mongo URI, display and required
flags configured:

```bash
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src scripts
python -m pip check
python -m pytest -q tests/unit tests/contract tests/ui
python -m pytest -q tests/integration -m 'not ui and not native_secret_store'
python -m pytest -q tests/integration/test_desktop.py --junitxml=desktop.xml
python scripts/verify_desktop_e2e.py desktop.xml
python scripts/create_indexes.py --dry-run
python -m pip wheel --no-deps --wheel-dir .pytest_cache/secure-wheels .
python scripts/verify_secure_storage_package.py .pytest_cache/secure-wheels
git diff --check
```

Local result: **577 unit/contract/UI**, **211 non-UI integration** and **13
desktop Mongo** cases passed. The desktop JUnit gate requires all 13 cases.
The installed-wheel security and draft smoke checks passed, along with lint,
format, compile, dependency consistency, and isolated index preflight.

The KDF benchmark on AMD EPYC 9V74 used 20 sequential synthetic derivations.
Median was 79.7 ms and nearest-rank P95 was 84.4 ms. Demo-device cost remains
pending.

Remaining gates include independent PO/TL/security review, hosted checks,
native Windows and macOS/Linux credential-store verification, staging
backup/restore, and a dedicated log-capture scan. The regression matrix does
not establish locked GridFS backup/restore, recovery of a new-note draft
before it has a remote note ID, or fault-injection coverage of a lost ACK
during an existing-note lock transition. Such drafts are retained encrypted.
The runtime reports a failed lock write as unconfirmed. Reload the remote
record to determine whether the lock was committed before retrying.
