# Phase 2 10k search benchmark — 2026-10-10

Command:

```powershell
$env:NOTEAPP_TEST_MONGO_URI = "mongodb://127.0.0.1:27017"
.\.venv\Scripts\python.exe -m scripts.benchmark_phase2 --output docs/testing/PHASE2_BENCHMARK.json

```

The script creates its own UUID-named noteapp_test_benchmark_* database and drops
only that database after closing Tk/workers/clients. It never seeds, clears or
purges developer notes. Fixed seed 20261010; IDs are 24-digit hexadecimal integers;
10,000 synthetic UTF-8 notes, 9,500 active, 20% uncategorized, four categories,
three priorities, 90 date buckets. No credentials or real note contents in output.

Environment: Windows 11 build 26100; Python 3.11.9; Tcl/Tk 8.6.12; Mongo 7.0.43
in local Docker; Intel i5-13500H / 16 logical CPUs; host RAM 16,821,141,504 bytes;
Docker memory limit shown as 7.588 GiB. Shared laptop workload, not controlled CI.

20 DB warm-ups; 100 measured queries (10 each of ten cases); 100 real Tk render
requests. DB duration includes application validation, Mongo round trip, mapping.
UI duration includes worker, 50ms event pump, 30 Canvas cards and layout in a
visible 1200x760 note-list harness. It excludes the intentional 300ms typing
debounce, full three-pane startup and OS compositor paint completion. Percentiles
use nearest rank; a per-case p95 with ten samples is that case's maximum.

| Query | DB p95 ms | UI p95 ms |
|---|---:|---:|
| Recent | 5.685 | 172.351 |
| Native text | 19.026 | 145.059 |
| Category filter | 4.619 | 154.546 |
| Priority sort | 5.284 | 193.438 |
| Category sort | 9.720 | 210.396 |
| Text + category sort | 52.684 | 169.909 |
| Text + category + priority + date | 12.110 | 109.504 |
| Rare text | 2.679 | 71.648 |
| No match | 2.326 | 74.747 |
| Text/category page two | 45.445 | 141.650 |
| **Overall 100 samples** | **46.521** | **169.909** |

Overall DB p50/p95/p99: 5.685/46.521/50.715 ms.
Overall UI p50/p95/p99: 116.671/169.909/193.438 ms.
The development overall p95 is below 200ms; a category-render outlier was
210.396ms. This is measured evidence, not a promise that all requests or platforms
meet 200ms. Input-to-result latency includes another 300ms debounce. Final NFR
acceptance follows the team's agreed DEC-09 measurement policy/hardware.

[Raw samples, executed pipelines in Extended JSON and winning/executed explain
summary](PHASE2_BENCHMARK.json) are reproducible with the tracked script.
The summary excludes rejected plans; pipeline sort/limit and lookup fields show
where bounded execution occurs. Inspect docs/keys examined rather than inferring
a fast query just from returned row count.

The [initial baseline](PHASE2_BENCHMARK_BASELINE.json) measured five cases with
a withdrawn Tk harness and widget cards. Category join p95 was 600.679ms;
overall DB/UI p95 was 464.802/1091.036ms. Its explain summary included rejected
plans. It identified two bottlenecks; it is not a strict like-for-like performance
comparison with the final visible harness and expanded ten-case distribution.

The final category query first matches typed active/text/date/category/priority
criteria, groups IDs by category, joins current category names once per group,
then retrieves at most limit+1 notes per group. A final server sort/limit merges
the candidates by name_key/_id. Page two filters category keys and note IDs in
the nested lookup before its limit. The additive idx_notes_category_seek supports
category/ID seeks. No persistent name cache, denormalization, Python global sort
or public DTO change. Static null/dangling/missing-reference and native-text
pagination is independently checked against the expected 65-note order.

Canvas rows retain native text, badges, selection, mouse/keyboard actions and
scrolling while reducing widget creation/layout. UI tests and fresh-process Mongo
desktop scenarios were rerun after this change. Startup/RAM/FPS requirements have
not been certified by these query measurements.
