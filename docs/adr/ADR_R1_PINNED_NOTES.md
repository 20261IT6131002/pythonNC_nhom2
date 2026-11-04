# ADR — R1 pinned ordering and metadata CAS

Status: **Proposed**, pending M1 and affected owner review.
Contract: [R1 pin contract](../srs/r1/01_R1_PIN_CONTRACT_FREEZE.md).

FR-12 requires pinned notes before unpinned notes under every active sort. Applying
a UI sort to one fetched page cannot meet that requirement. Add a boolean domain/DTO
field, a metadata-only repository CAS operation and a leading server sort/cursor key.

Keep the existing category aggregation, grouping by `(category_id, is_pinned)` before
the bounded note lookups. Normalize missing category IDs to null before grouping to
avoid producing the same uncategorized notes twice. Retain all later pin partitions
when seeking, regardless of category key. Add separate ascending/descending created
indexes because the leading pin key always remains descending.

Require explicit normalization before startup queries: BSON missing and false sort as
different types. Startup reports a migration requirement without mutating old data.
The migration refuses existing non-boolean flags and only fills missing values; no
schema_version bump, TTL, timestamp rewrite or document deletion is introduced.

The additive field is also admitted by the existing purge whitelist, so notes remain
purgeable with the existing attachment cleanup. Other unknown fields remain rejected.

Rollback: revert the feature commits and keep the additive boolean field/indexes.
Versions remain monotonic. Old clients must be stopped during migration/rollout since
they do not write the field and do not implement pinned ordering. Cursor continuity
across ordering mutations or remote changes is not a snapshot guarantee; local pin
success always starts a fresh page. Independent review remains required before merge.
