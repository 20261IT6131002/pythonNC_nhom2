# ADR — R1 authenticated encryption and native secret storage

Status: **Proposed**, pending M1 and M3/M4 review. Date: 2026-11-04.
Base: `develop@60f608524aa79839e45d1e714c88493861f48ddd`.
Contract: [R1-02 secure storage](../srs/r1/02_R1_SECURE_STORAGE_CONTRACT_FREEZE.md).

FR-17 needs a device-local secret source; FR-14 needs passphrase-derived keys. Both
need authenticated encryption. Use small application ports and an immutable envelope
while keeping crypto, serialization and OS APIs in infrastructure. Do not merge the
two key lifecycles or introduce a shared production key, KDF, draft file or lock UI.

## Dependency review

On 2026-11-04, official PyPI metadata reported cryptography 50.0.2 (Python >=3.9,
excluding 3.9.0/3.9.1) and keyring 25.7.0 (Python >=3.9). Bound runtime dependencies to
`cryptography>=50.0.2,<51` and `keyring>=25.7,<26`, including maintenance updates within
the reviewed major line. Installed versions and resolver/wheel checks are recorded in
the test report; this does not claim every allowed version has been tested.

- [cryptography release metadata](https://pypi.org/project/cryptography/50.0.2/)
  and [installation/wheels](https://cryptography.io/en/latest/installation/).
- [AEAD API](https://cryptography.io/en/latest/hazmat/primitives/aead/): use AESGCM,
  restrict keys to 256 bits, use the full tag and authenticate caller context before
  returning plaintext. Avoid a custom primitive, truncated tags and streaming
  unauthenticated plaintext.
- [keyring release metadata](https://pypi.org/project/keyring/25.7.0/) and
  [OS/backend documentation](https://keyring.readthedocs.io/en/stable/): use explicit
  Windows/macOS/SecretService providers; the package also allows third-party backends,
  so default plugin selection alone is insufficient for a fail-closed policy.

Both projects publish Python 3.10/3.12 compatibility metadata. A wheel download check
is not an interpreter test. Windows native smoke and local/CI packaging evidence must
be reported separately from Ubuntu/macOS and remote matrix results.

## Decisions and consequences

Fresh 96-bit random nonces come from the OS CSPRNG; no public API accepts an encryption
nonce. This is standard probabilistic uniqueness, not a mathematical no-collision
guarantee across arbitrary use. R1-03/04 must define key lifecycle/usage bounds before
large-scale use. KDF choice and 16-byte salt generation remain in FR-14's scope.

Envelope v1 authenticates fixed algorithm/version context plus required caller AAD.
Strict serialization rejects duplicate/extra fields and malformed encodings. A
generic failure hides wrong-key versus tamper details. Input errors contain no input
values. Byte fields are absent from repr; no adapter logs operation payloads.

Native secrets live under `noteapp.secure-storage.v1`; reads/writes/deletes use opaque
names, never note content. Only native providers are selected; environment-configured
keyring plugins and a file fallback are not used. Put/delete verify the native result.
There is no automatic key creation, overwrite retry, in-memory fallback or key cache.

OS credential stores can be unavailable or require user permission. Same-user malware
or a compromised process is outside at-rest encryption's protection. Native calls may
block and belong in workers. Linux Secret Service requires a running user-session
service; lack of that service fails closed. KWallet-only systems are not silently
redirected to a different provider.

Packaging validation targets a normal wheel and its installed imports/resources.
Standalone executable/PyInstaller signing and native OS acceptance remain later
release work; no packaging framework is added here. Revert these commits to roll
back; no persisted user format or Mongo document changes occur in R1-02.
