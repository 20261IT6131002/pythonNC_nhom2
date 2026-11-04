# R1-03 — Encrypted draft recovery contract

Status: **Proposed for M1/M2/M3/M4 review**, implemented on the user's request.
Base: `develop@925fbdf` after PR #16. Foundation is reused without crypto duplication.
Scope: FR-17/AC-17a..c, TC-REC-001..003, BR-09/10/14, NFR-REL-01/02,
NFR-SEC-04 and NFR-MAIN-01. Plan: [FR-17 execution](R1_PLAN_03_FR17_DRAFT_RECOVERY.md).

| Decision | Implementation basis awaiting review |
| --- | --- |
| REC-D01 | Canonical opaque UUID per editor draft session. |
| REC-D02 | New notes persist/reuse their stable UUID client_operation_id. |
| REC-D03 | Existing notes retain opaque note_id and exact base_version for CAS. |
| REC-D04 | Draft snapshot revisions are monotonic; equal identical writes are idempotent, older writes ignored. |
| REC-D05 | 750 ms main-thread debounce; immutable snapshots go to bounded workers. |
| REC-D06 | Multiple independent `<uuid>.draft` records; no global single JSON. |
| REC-D07 | 32-byte random master key in the native OS SecretStore; provisioning serialized. |
| REC-D08 | Existing encrypted files/temps plus missing key fail closed without regeneration. |
| REC-D09 | Keyring/crypto/file failure preserves RAM/old ciphertext and reports secure autosave unavailable. |
| REC-D10 | Only a matching remote ACK with no newer editor revision authorizes revision-conditional cleanup. |
| REC-D11 | Remote failures retain the encrypted draft. |
| REC-D12 | Remote change/deletion/trash preserves local and remote; no duplicate creation for an existing note. |
| REC-D13 | Discover and recover are separate; user explicitly selects recover/keep/discard and explicitly saves remote. |
| REC-D14 | source_locked is reserved; this version rejects locked recovery/save rather than routing through normal UpdateNote. |

DraftStore adds `delete_if_revision` to the proposed port because reading then deleting
is not atomic. Cleanup fences already-acknowledged late writes; user discard fences
the entire session identity. Newer snapshots cannot be deleted by an old ACK.
Identical revision with a different payload conflicts rather than silently overwriting.

The editor content revision retains its existing semantics. A separate monotonic draft
revision tracks content plus adopted note ID/version metadata, so pin/image/reminder
acknowledgements can rebase a dirty draft without changing FR-12's content revision.
Recovery restores the persisted base version and operation ID, enters DIRTY and never
claims remote SAVED. Category options retain a missing selected category until the
user chooses a replacement; metadata not owned by the draft is not overwritten.

Only `format_version`, `draft_id`, `encrypted_envelope` are in the plain file wrapper.
All other fields (including operation ID, revision and timestamps) are encrypted.
Strict UTF-8 JSON rejects duplicate/extra fields and malformed values. Payload limit
is **1 MiB serialized UTF-8**, wrapper read bound **2 MiB**. This is a draft transport
bound, not a new remote-note business limit; oversized drafts remain in RAM with an
explicit warning and can still be saved remotely. No plaintext temp/file fallback.

Default profiles live in the user's OS application-data directory, scoped by an opaque
hash of the configured database name. An explicit absolute NOTEAPP_DRAFT_DIR can choose
another profile. Key names are profile-scoped opaque names. A native OS profile lease
prevents concurrent processes from sharing a writable profile; kernel release permits
restart after a crash. A zero-content `.profile.lock` file contains no note/key data.

Only workers discover files, access keyring, encrypt/decrypt and perform writes. Each
write uses a private same-directory encrypted temp, flush/fsync and os.replace without
deleting the prior good file first. Explicit corrupt draft discard does not need the
lost key. No retention deletion is automatic in v1.

Local discovery and Mongo initialization are independent startup jobs. Manual reconnect
is sufficient; reconnect never auto-saves or overwrites. Closing attempts a final
worker snapshot with a bounded UI grace period; process kill guarantees only recovery
of the last successfully persisted encrypted snapshot, not every keystroke. Existing
in-flight I/O may finish during runtime shutdown, with no callbacks into destroyed Tk.

No Mongo format migration, FR-14/KDF, attachment binary recovery, background daemon,
multi-device synchronization or automatic remote conflict resolution is introduced.
Remote CI and independent review remain release gates. Rollback stops the app and
reverts R1-03 code; keep encrypted files and OS keys for later recovery, never discard
them as part of rollback. See [ADR](../../adr/ADR_R1_DRAFT_RECOVERY.md).
