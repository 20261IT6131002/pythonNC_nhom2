# ADR — Revision-aware encrypted local recovery

Status: **Proposed**, 2026-11-04. Base: `925fbdf` (R1-02 merged).
Contract: [FR-17 recovery](../srs/r1/03_R1_DRAFT_RECOVERY_CONTRACT_FREEZE.md).

Use the existing ContentCipher, SecretStore and envelope. The application defines
LocalDraft, DraftStore, key provisioning, autosave and recovery classification; local
infrastructure owns strict transport, native profile leases and atomic encrypted I/O.
Presentation owns debounce, session/request IDs, status and explicit recovery actions.

Key provisioning must be serialized before any encrypt/write. Missing native key with
existing ciphertext is a recovery failure, not permission to generate a replacement.
Profiles/key names are isolated by database/directory so test/development profiles
cannot accidentally recover each other's notes. Raw secrets never enter config/env.

The file store serializes revision comparison with replacement. Revision-conditional
ACK deletion and in-process fences prevent an old save from deleting a newer draft,
or an old queued autosave from resurrecting an acknowledged/discarded session. The
native profile lease rejects a second writer process and is released after a crash.
This is single-writer desktop recovery, not multi-device synchronization.

Use a separate draft revision to include acknowledged metadata rebases while keeping
existing content-revision behavior. New-note ACK loss continues through the existing
operation-ID unique index. A returned remote payload differing from the draft is kept
DIRTY for a user-confirmed subsequent update; it is not treated as acknowledgement of
that different content. Existing-note recovery always keeps expected_version.

Recovery discovery does not require Mongo or decryption. Selecting a draft authenticates
it and compares remote version when reachable. Missing/trash/conflict retains both
versions; source_locked is blocked until FR-14 supplies a safe save strategy. This task
does not claim protection/recovery for image bytes or reminder state.

Atomic replacement follows Python's [os.replace](https://docs.python.org/3/library/os.html#os.replace)
API. Windows profile ownership uses nonblocking
[msvcrt.locking](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking);
Unix uses flock. File fsync errors other than unsupported-operation errors fail the
write and retain the prior file. Full power-loss guarantees vary by filesystem;
recovery acceptance is based on successfully acknowledged atomic writes.

The 1 MiB serialized payload bound is an explicit implementation proposal. It does
not lower remote note limits; escaping/metadata can make a large note ineligible for
secure draft transport, which is surfaced clearly. No plaintext fallback or silent
truncation is permitted. Native OS support/CI and independent security review must be
reported separately from tests using fake keyrings.

Rollback retains ciphertext and native keys. Old code ignores these files; restore
R1-03 to recover them. No Mongo migration, TTL or automatic cleanup is needed.
