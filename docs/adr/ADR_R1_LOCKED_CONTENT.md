# ADR R1-04 — Authenticated locked note content

**Status: Proposed.** The desktop app already has an authenticated cipher boundary
and a separate OS-keyring-backed draft store. Reuse these adapters and keep
locked note credentials separate from the draft key.

- An active or trashed locked record uses schema v3, `is_locked=true`, the generic
  title and `content_encrypted`. The encrypted field contains the format version,
  algorithm, nonce, ciphertext plus tag, and an allowlisted KDF profile and salt.
  `content_plain` is removed in the same atomic operation. Removal uses v3 with
  `is_locked=false` and removes `content_encrypted` atomically.
- The payload is a UTF-8 JSON pair of title and content with a 1 MiB UTF-8 content
  bound. AAD binds the envelope to the note ID and locked-note format namespace.
  Note CAS versions are outside AAD so pin, attachment, reminder and trash mutations
  can advance the version without touching the encrypted bytes.
- A masked summary exposes metadata and no body. Ciphertext is only returned to
  the authenticated command path. Writes use an active-note CAS predicate and
  validate the representation before parsing. Old plaintext records are read in
  place. The existing text index continues to index plaintext fields and the
  generic title label, and application text queries exclude locked rows.
- PBKDF2 is built into Python and follows the R1 proposal. Argon2id would require
  a new dependency and versioned migration profile. A short PIN is vulnerable to
  offline guessing against a dump. Title masking avoids keeping an indexed copy
  of the original title. A generic desktop reminder avoids a race between a
  claimed title and a subsequent lock transition.
- Unlock applies to one editor in RAM. Tk only handles the prompt and rendering.
  KDF, AEAD, and Mongo calls run on bounded workers. Encrypted draft recovery
  requires the current note passphrase and the persisted draft base version before
  showing an existing locked draft. Failed authentication or a remote conflict
  leaves the encrypted draft in place.

## Preflight and rollback

Run `python scripts/create_indexes.py --dry-run` against an isolated copy. Review
`schema_v3`, `invalid_note_representation`, and the index plan. The script does
not convert documents or rebuild indexes. Before enabling locked writes in a
shared environment, back up Mongo and GridFS and verify restore.

After a v3 write, retain a v3-capable app on rollback. Pause writes and preserve
the database, draft files and OS keys while forward-fixing. A deliberate
return to plaintext requires the user's passphrase. An older v1/v2 reader
cannot handle a locked record. Prior backups, journals, oplogs or exports may
retain historical plaintext. Attachment binaries and other metadata are
outside the encryption boundary. Python session cleanup drops references on
a best-effort basis. There is no password recovery.
