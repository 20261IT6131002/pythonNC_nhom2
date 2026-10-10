# Category + full-text query prototype plan — CF-07

Status: **Design/prototype obligation for P2-05/06, not executed runtime**.
Owner: M4; reviewers M3/M5. Requirements: FR-06/11, NFR-PERF-02,
P2-AC01/02/06/08/18. Canonical DTO/cursor contract:
[public interfaces](PHASE2_PUBLIC_CONTRACTS.md); unresolved category/text/performance
values: [ADR A2-Q02/Q04/N01](../adr/0002-phase2-query-trash-contract.md).

## 1. Concrete aggregation shape to prototype

The adapter compiles typed criteria into a first `$match` combining active scope,
text/category/priority and UTC bounds. When present, `$text` must be in the first
match stage, not after category lookup.
[MongoDB 7 text aggregation rules](https://www.mongodb.com/docs/v7.0/tutorial/text-search-in-aggregation/)

Fixture-only mongosh prototype (ordinal category ordering is a proposal while
A2-Q02 is unresolved; fixture text is not an agreed DEC-07 expected match):

```javascript
const firstMatch = {
  is_deleted: false,
  $text: { $search: "học tập" },
  priority: "HIGH"
};
const pipeline = [
  { $match: firstMatch },
  { $lookup: {
      from: "categories",
      localField: "category_id",
      foreignField: "_id",
      as: "_category"
  } },
  { $set: {
      category_sort_key: {
        $ifNull: [ { $arrayElemAt: [ "$_category.name_key", 0 ] }, "" ]
      }
  } },
  { $sort: { category_sort_key: 1, _id: 1 } },
  { $limit: 31 },
  { $unset: "_category" }
];
db.notes.explain("executionStats").aggregate(pipeline);
```

For page two, insert an adapter-built seek `$match` after `$set` and before `$sort`:
category_sort_key > validated last_key OR
(category_sort_key == last_key AND _id > validated last_id).
Decode ID/keys/fingerprint before building the pipeline; never splice cursor JSON
or UI dictionaries into it. `31` illustrates limit+1 for page size 30, not a fixed
maximum. Encode the last returned row's computed key+ID, then map records to NotePage.
The internal key is not an extra field in Note/NoteView or a stored category cache.

Empty text omits only the `$text` clause. Category equality and priority/date filters
remain in the initial match. Dangling/unclassified category placement follows the
actual A2-Q02 value before production merge. Refresh is needed after category rename;
pagination does not provide a snapshot under concurrent metadata changes.

A notes.category_id index supports filtering, not sorting a key computed after
lookup. This pipeline sorts on Mongo, potentially as a blocking sort; a small
returned page does not imply few scanned/joined records. `$sort` index eligibility
depends on stage position, so record the actual explain plan rather than inferring
it from an index manifest.
[MongoDB 7 sort/index behavior](https://www.mongodb.com/docs/v7.0/reference/operator/aggregation/sort/)

## 2. Required P2-05/06/16 experiment receipt

Use a fixture-owned `noteapp_test_*` benchmark DB, never clear developer notes.
Seed **10,000 deterministic notes**, generator seed `20261010`; record the actual
generator/ID scheme, content corpus, category count/names, 20% uncategorized,
priority distribution, timestamp ties and deleted records. Include title-only,
content-only and Vietnamese composed/decomposed/phrase/accent cases with DEC-07
expected values, once those values are available.

Run category+text first/next page; category without text; text+category+priority+date;
rare/common/no-match text; null/dangling category; renamed category refresh; equal
name keys with stable ID ties; a newer item inserted before page two. Compare static
result IDs with the independently expected ordering/active intersection.

For each query, store Mongo/Python/OS/CPU/RAM/location/version, index definitions,
actual pipeline/options, executionStats winning stages, index use, keys/docs examined,
join cardinality, rows returned and blocking sort/spill information when available.
Use bounded execution time/resource options reviewed for the adapter; do not add
an unbounded pipeline or assume spilling establishes acceptable latency.

DEC-09 determines accepted measurement policy. Proposed receipt: 20 warm-up calls,
100 representative searches, DB and UI end-to-end timing separately, p50/p95/p99.
Report **UNMEASURED** until runs occur, and **FAIL/deviation** if the agreed target
is exceeded. No prototype source, EXPLAIN output or index name alone establishes
search <200ms with 10k notes. Do not use Phase 1 latency as Phase 2 evidence.

## 3. Optimization fallback and merge gate

If the direct pipeline is too slow, first measure/select early filter indexes,
minimize joined category fields and intermediate note payload, then fetch full
payload only for bounded ordered result IDs. Preserve server ordering and the
same query/cursor semantics; no scan/sort of all 10k notes in Tk.

Persisting a category sort key or changing collation/search technology requires
a separate reviewed ADR/CR/migration, including category rename updates for active
and trashed notes, repair consistency, concurrent seek behavior and rollback.
It is not authorized automatically by a benchmark failure. If no compatible
optimization meets the agreed target, record the failing measurement and accepted
carry-over/deviation explicitly; do not silently change category semantics, FR
priority or report the NFR as PASS.

P2-05/06 close only with the real prototype/results receipt; CF-07 in P2-02 is
addressed as an owned execution strategy and QA obligation, not a runtime/NFR pass.
