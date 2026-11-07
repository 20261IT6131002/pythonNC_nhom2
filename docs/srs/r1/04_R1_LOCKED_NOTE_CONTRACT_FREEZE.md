# R1-04 Locked Notes contract

**Status: PENDING PO, TL, database, security and QA review.**
Implementation baseline: `develop@6757833c601bcdf3b074241742db093cb383edc5`, after PR #17.
FR-14 AC-14a–d, BR-10/12/14, NFR-SEC-02 and FR-17 recovery.
Approver and approval date are pending for every decision below.

| Decision | Implementation proposed for approval | Boundary and evidence |
| --- | --- | --- |
| LOCK-D01 | PBKDF2-HMAC-SHA256 produces a 32-byte AES-GCM key. | KDF port and adapter, real Mongo lifecycle |
| LOCK-D02 | Accept only the v1 profile at 600,000 iterations and a fresh 16-byte salt. | Codec allowlist, KDF tamper test and benchmark |
| LOCK-D03 | Require 12 characters and at most 1024 UTF-8 bytes. Preserve whitespace and Unicode, mask input and confirm new phrases. | Auth command, Tk dialogs |
| LOCK-D04 | Encrypt both title and body. Mongo title is `Ghi chú đã khóa`. | Atomic write, BSON and restart checks |
| LOCK-D05 | Text searches exclude locked records. Metadata filters and sort remain available. | Native Mongo text index test, query adapter |
| LOCK-D06 | Keep credentials in the editor session. Relock on switch, close, explicit action or five minutes idle. If the last draft write is unconfirmed, prompt before discarding unsaved content. | Editor state and desktop expiry scenario |
| LOCK-D07 | Explicit removal requires the current phrase and confirmation before a CAS plaintext write. | Auth command and negative confirmation test |
| LOCK-D08 | Trash and restore preserve locked representation. Purge validates the record and uses existing attachment compensation. | Trash integration |
| LOCK-D09 | Future export requires explicit policy review, with locked records excluded by default. | FR-15 export contract pending |
| LOCK-D10 | Use a generic OS message in the desktop runtime for all reminders, including already claimed reminders racing against lock. | Runtime wiring, phase 3 notification regression and locked Mongo reminder test |
| LOCK-D11 | Closed and listed records expose a generic title and no content preview. | View mapping and desktop restart |
| LOCK-D12 | Dedicated authenticated create, update, rekey and removal. Plaintext updates require a plaintext-state Mongo predicate. | Application guard and direct repository CAS test |
| LOCK-D13 | v1/v2 remain readable. v3 explicitly marks locked or removed-lock state. Conversion is per note and atomic. | Codec, non-mutating preflight, trash/restore |
| LOCK-D14 | Fresh salt and nonce per encrypted write. No credential or derived key stored. | Cipher reuse, rekey and tamper tests |

**Decision history.** 2026-11-07. Initial implementation proposal. DEC-10 and the
desktop-wide generic notification policy still require sign-off.

See the [ADR](../../adr/ADR_R1_LOCKED_CONTENT.md) and
[test report](../../testing/R1_LOCKED_NOTES_TEST_REPORT.md).
