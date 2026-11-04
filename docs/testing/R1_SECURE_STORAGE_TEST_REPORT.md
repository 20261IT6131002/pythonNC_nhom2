# R1-02 — Secure storage foundation validation

Date: 2026-11-04. Branch: `feature/r1-02-secure-storage-foundation`.
Base: `60f608524aa79839e45d1e714c88493861f48ddd` (`develop`, PR #15).
Validated implementation: `ff21453d955ec9067010f1c54d52a47412f90077`.
The final documentation/evidence commit follows this implementation revision.

Scope: R1-02.1..4 from the
[execution plan](../srs/r1/R1_NEXT_EXECUTION_PLAN_FR17_FR14.md). The
[contract](../srs/r1/02_R1_SECURE_STORAGE_CONTRACT_FREEZE.md) and
[ADR](../adr/ADR_R1_SECURE_STORAGE.md) remain **Proposed**, pending M1/M3/M4 and
independent security review. Supporting FR-17 and FR-14 does not complete either FR.

## Delivered

- Immutable `EncryptedEnvelope`, `ContentCipher` and `SecretStore` public ports.
- AES-256-GCM with fresh 12-byte random nonces and authenticated envelope/consumer
  context; wrong key, changed ciphertext/tag/nonce or AAD fail authentication.
- Strict JSON/base64 encrypted-envelope transport, rejecting malformed/extra/duplicate
  fields, unknown formats and truncated tags. It does no file I/O.
- Explicit native OS keyring selection, with no configured/global plugin selection,
  plaintext/file fallback or automatic missing-key regeneration. Writes/deletes are
  verified against the native provider. Windows persistence is local-machine.
- Sanitized typed errors/result codes. Envelope bytes and worker result values are
  excluded from repr. Adapters do not log plaintext, keys, payloads or provider errors.
- Shared fake/native secret-store contracts, real AES-GCM contracts, native Windows
  credential smoke, architecture gates and installed-wheel smoke in CI.

No autosave, local draft files, recovery dialog, KDF/passphrase handling, locked-note
UI, Mongo schema/index changes or startup key provisioning are added. The existing
draft/keystore scaffolds are not presented as implemented features.

## Actual environment and commands

Windows 10.0.26100, Python **3.11.9**, cryptography **50.0.2**, keyring **25.7.0**,
MongoDB **7.0.43** via the existing local Docker container.

Use `.venv/Scripts/python.exe` for `python` in these commands.

| Command | Actual result |
| --- | --- |
| `python -m pip install -e ".[dev]"` | PASS, bounded runtime dependencies installed |
| `python -m pip check` | No broken requirements |
| `python -m ruff check .` | PASS |
| `python -m ruff format --check .` | PASS, 209 files |
| `python -m compileall -q src scripts` | PASS |
| `python -m pytest -q tests/unit tests/contract tests/ui --tb=short --cov=noteapp.domain --cov=noteapp.application --cov=noteapp.infrastructure.security --cov-report=term-missing --junitxml=.pytest_cache/r1-secure-quality-final.xml` | **528 passed, 1 skipped**, 18.09 s |
| `python -m pytest -q tests/integration --tb=short --junitxml=.pytest_cache/r1-secure-integration.xml` | **196 passed**, no skips, 109.96 s |
| `python -m pytest -q tests/integration/test_native_secret_store.py --tb=short` | **1 passed**, real Windows Credential Manager |
| `python scripts/verify_desktop_e2e.py docs/testing/R1_SECURE_STORAGE_DESKTOP_E2E.xml` | All **7** desktop scenarios passed; skipped=0 |
| `python -m pip wheel --no-deps --wheel-dir .pytest_cache/secure-package .` | Built `noteapp-0.1.0-py3-none-any.whl` |
| `python scripts/verify_secure_storage_package.py .pytest_cache/secure-package` | Installed-wheel security smoke PASS |
| `python scripts/verify_phase2_contract.py` | 5 declaration blocks, 10 models, 2 ports, 33 links verified |
| `git diff --check` / staged diff check before commits | PASS |

Integration variables: `NOTEAPP_TEST_MONGO_URI=mongodb://127.0.0.1:27017`,
`NOTEAPP_REQUIRE_MONGO=1`, `NOTEAPP_REQUIRE_UI=1`,
`NOTEAPP_TEST_NATIVE_SECRET_STORE=1`. Native smoke uses a fresh random test credential
and deletes only that owned entry in a `finally` block; no user credential is changed.
Mongo fixtures own and drop only newly generated `noteapp_test_*` databases.

The existing POSIX FIFO test (`tests/unit/test_image_file_reader.py:43`) is the one
Windows skip. No test was deleted or disabled to hide a failure. Tests for each
adapter were written first and initially failed because that adapter did not exist;
the completed adapter tests and the final suites pass.

Combined domain/application/security statement coverage: **98%** (1281 statements,
29 missed). New envelope, ports and security error mapping are **100%**; native keyring
adapter **100%**; AES-GCM adapter **94%**; envelope serializer **97%**. Coverage of the
untouched zero-statement recovery scaffolds is not evidence of a working recovery flow.

## Security acceptance evidence

| ID / invariant | Tests |
| --- | --- |
| SEC-U01 | Real AEAD roundtrip for empty, binary and Vietnamese UTF-8 payloads |
| SEC-U02 | 32 repeated encryptions use distinct observed nonces/ciphertexts; this is not a proof that random collisions are impossible |
| SEC-U03/04/07 | Shared cipher contract rejects modified body/tag/nonce, wrong key and changed record/purpose AAD |
| SEC-U05/06 | Envelope rejects bad nonce length/type; cipher rejects non-32-byte keys, non-byte plaintext and missing/invalid context |
| Envelope integrity | Serializer roundtrip and rejection of malformed JSON/base64, duplicate/extra fields, unknown version/algorithm and incomplete tags |
| SEC-K01 | Same CRUD, replacement, binary-boundary, invalid-name and invalid-value contract against fake and native adapter API double |
| SEC-K02 | Missing provider, denied get/put/delete, corrupt stored key and unacknowledged write/delete raise a sanitized error |
| SEC-K03 | Failure/plugin-selection tests leave the temporary directory empty; no file backend or new key is used |
| Repr/log hygiene | Envelope/worker result repr hides sensitive values; exception rendering/caplog omit private provider markers |
| Native persistence | A new adapter instance reads the synthetic OS credential and decrypts the serialized envelope; cleanup verifies the entry is gone |
| Architecture | Domain/application remain library-free; presentation rejects crypto/keyring imports and infrastructure internals |

[Evidence JSON](R1_SECURE_STORAGE_EVIDENCE.json) records actual counts, dependency
versions, implementation SHA and wheel SHA-256. The
[desktop JUnit](R1_SECURE_STORAGE_DESKTOP_E2E.xml) contains the seven actual desktop
testcase elements extracted without changing outcomes from the full integration run.
Existing pin/image/category/reminder/trash/search tests remain part of the regression.

## Python, packaging and CI boundaries

Direct dependency Windows wheels were actually resolved/downloaded for CPython 3.10
and 3.12 using:

```powershell
python -m pip download --only-binary=:all: --no-deps --platform win_amd64 --implementation cp --python-version 310 --abi cp310 --dest .pytest_cache/secure-deps-cp310 "cryptography>=50.0.2,<51" "keyring>=25.7,<26"
python -m pip download --only-binary=:all: --no-deps --platform win_amd64 --implementation cp --python-version 312 --abi cp312 --dest .pytest_cache/secure-deps-cp312 "cryptography>=50.0.2,<51" "keyring>=25.7,<26"
```

Both PASS. This checks availability of these direct dependencies, not full transitive
installation or interpreter execution on those versions. The local host has Python
3.11/3.14; **Python 3.10/3.12 test execution remains unverified**. The existing remote
quality matrix now builds/installs the wheel on both versions. The Windows job also
requires the native credential lifecycle test; headless Mongo CI excludes that
opt-in native test instead of pretending a desktop credential service exists.

The package smoke inserts the isolated installed target first and asserts that it
imported the built package, not the editable checkout. It tests ports, an AEAD
serialization roundtrip and a packaged icon without opening Tk or an OS keyring.
Standalone executable/signing checks are not claimed.

Remote GitHub CI has **not run for this branch** in this session. Native macOS Keychain
and Linux Secret Service have not been exercised; selection/failure behavior uses
test doubles. No remote PASS links or platform support claims are fabricated.

## File inventory and review/rollback

- Documentation relocation: the two `PHASE3_PLAN_*.md` files are now under
  `docs/srs/phase 3`; `R1_PLAN_01_PINNED_NOTES.md` is under `docs/srs/r1`. README,
  Phase 3/R1 contracts and historical reports link to those locations. The new next
  execution plan is tracked under `docs/srs/r1`, not inside a cache.
- Core: `application/dto/{encrypted_envelope,operation_result}.py`,
  `application/ports/{content_cipher,secret_store}.py`, `domain/errors.py`.
- Infrastructure: `infrastructure/security/{__init__,aes_gcm,keyring_store,serializers}.py`.
- Tests: `tests/security_{contracts,fakes}.py`; `tests/unit/test_{encrypted_envelope,
  aes_gcm,keyring_store,secure_serializers}.py`; `tests/contract/test_{content_cipher,
  keyring_secret_store,secret_store_fake,architecture}.py`;
  `tests/integration/test_native_secret_store.py`.
- Tooling: `pyproject.toml`, `.github/workflows/ci.yml`,
  `scripts/verify_secure_storage_package.py`; README, RTM, contract/ADR and this evidence.

Review remains required for the public contract, dependency choice and secure-storage
boundary. FR-17 (R1-03), FR-14 (R1-04), KDF/privacy decisions and their acceptance cases
remain pending according to the execution plan. No merge, release, production data
change, application key provisioning or plaintext draft write occurred.

Rollback the security commits in reverse order and reinstall the prior dependency
configuration. No Mongo migration or user file/key cleanup is required. Documentation
relocation is independent and can remain. The only native credential written during
verification was synthetic and was removed by its owning test.
