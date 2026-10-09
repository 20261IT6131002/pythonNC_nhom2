# 05 — TEST STRATEGY, TRACEABILITY MATRIX & RELEASE GATES

**Source baseline:** original SRS FR-01..FR-16, NFRs, UC-01..08; **new candidate requirements:** FR-17 & selected BR/NFR proposals in SRS v2.  
**Đây là kế hoạch kiểm thử, KHÔNG phải báo cáo đã thực thi.** Tất cả trạng thái hiện là `NOT RUN`.

## 1. Test pyramid & môi trường

| Layer | Scope | Automation | Gate |
|---|---|---|---|
| Static/Architecture | Ruff, typing (incremental), dependency gate, secrets | every PR | zero required failure |
| Unit | entities/value objects/use cases with fake adapters & clock | pytest, fast | all core paths and edge cases |
| Integration | Mongo indexes/CRUD, GridFS, scheduler persistence, encrypted local drafts | docker Mongo fixture + temp dir/keyring stub | all FR P0 adapters |
| UI/Component | Tk event pump, editor states, search debouncing, error/close | Tk harness + controlled event loop | no freezes/no stale update |
| System/E2E | create→edit→search→reminder→trash→restore + reboot/reconnect | release job, manual OS notify | acceptance UAT |
| Nonfunctional | latency/RAM/network, threat/security, packaging | scripts + manual matrix | record measured data or NOT VERIFIED |

**Seed:** deterministic random 5,000/10,000 notes; Vietnamese diacritics, uppercase/normalization, 3 priorities, >=20 categories, boundary dates including leap year, past/future reminders, 1-byte/1MiB/10MiB images (fixture generated), corrupt image, soft-deleted, locked (R1) and duplicate/colliding operation IDs. Never commit secrets/actual sensitive data.

## 2. RTM — FR→module→tests

| Req | Phase | Module owner | Positive TC | Negative/boundary TC | Release result |
|---|---|---|---|---|---|
| FR-01 | MVP | M3/M2 | TC-CORE-001 | TC-CORE-002, TC-REC-001 | NOT RUN |
| FR-02 | MVP | M3/M2 | TC-CORE-003 | TC-CORE-004, TC-REC-002 | NOT RUN |
| FR-03 | MVP | M3/M4 | TC-SAFE-001 | TC-SAFE-002, TC-MED-006 | NOT RUN |
| FR-04 | MVP | M3/M4 | TC-CAT-001 | TC-CAT-002 | NOT RUN |
| FR-05 | MVP | M3/M2 | TC-PRIO-001 | TC-PRIO-002 | NOT RUN |
| FR-06 | MVP | M3/M4/M2 | TC-SRCH-001 | TC-SRCH-002, TC-SRCH-003 | NOT RUN |
| FR-07 | MVP | M3/M4 | TC-SRCH-004 | TC-SRCH-005 | NOT RUN |
| FR-08 | MVP | M4/M2 | TC-MED-001, TC-MED-002 | TC-MED-003,004,005,006 | NOT RUN |
| FR-09 | MVP | M3/M2 | TC-SCHED-001 | TC-SCHED-002 | NOT RUN |
| FR-10 | MVP | M3/M4 | TC-SCHED-003 | TC-SCHED-004,005 | NOT RUN |
| FR-11 | MVP | M4/M2 | TC-SORT-001 | TC-SORT-002 | NOT RUN |
| FR-12 | R1 | M2/M3 | TC-ADV-001 | TC-ADV-002 | NOT RUN |
| FR-13 | MVP **proposed** | M3/M4 | TC-SAFE-003 | TC-SAFE-004,005 | NOT RUN |
| FR-14 | R1 | M3/M4 | TC-SEC-001 | TC-SEC-002,003,004 | NOT RUN |
| FR-15 | R2 | M3/M2 | TC-EXP-001 | TC-EXP-002 | NOT RUN |
| FR-16 | R2 | M3/M2 | TC-STAT-001 | TC-STAT-002 | NOT RUN |
| FR-17 `[new]` | MVP proposed | M3/M4 | TC-REC-001 | TC-REC-002,003 | NOT RUN |

## 3. Test cases (Given / When / Then)

| TC | Case | Expected result |
|---|---|---|
| TC-CORE-001 | Create title valid, content UTF-8, category, priority | 1 note persisted, timestamps UTC, UI list refreshed |
| TC-CORE-002 | Title `''`, spaces, 251 characters | validation fails, no DB write, input preserved |
| TC-CORE-003 | Edit note, save then reload | revision increments, updated_at changes, content persists |
| TC-CORE-004 | Two concurrent versions save stale edit | write conflict, no silent overwrite; recovery option visible |
| TC-CAT-001 | Create category, assign note, rename | canonical mapping consistent and visible |
| TC-CAT-002 | Create `Work` and ` work ` | unique normalized rule rejects duplicate |
| TC-PRIO-001 | Insert HIGH/MEDIUM/LOW and sort | HIGH then MEDIUM then LOW |
| TC-PRIO-002 | Inject unexpected priority `URGENT` | input rejected before DB access |
| TC-SRCH-001 | Full text token query title/content with 10k notes | expected matching active note IDs, paging stable |
| TC-SRCH-002 | Rapid queries A then B, A response last | only B result displayed, debounce works |
| TC-SRCH-003 | Vietnamese có dấu/không dấu, phrase, typo | actual search behavior documented vs approved semantics |
| TC-SRCH-004 | Combine category+date+text | intersection correct, excludes trash |
| TC-SRCH-005 | Start>end, midnight bounds, leap day, timezone | invalid range rejected; local day included correctly |
| TC-SORT-001 | sort by created, updated, category, priority | stable deterministic ordering, no string-priority bug |
| TC-SORT-002 | Sort 10k notes with pagination | bounded page read; no client all-data sort |
| TC-MED-001 | Image exactly 1 MiB | stored INLINE, display thumbnail <=400px |
| TC-MED-002 | Image just >1MiB and <=10MiB | GRIDFS id points to correct content hash |
| TC-MED-003 | >10MiB, bogus extension, truncated image | rejected, original note unchanged |
| TC-MED-004 | Decompression bomb / extreme pixels | reject or safely cap, no crash/memory explosion |
| TC-MED-005 | GridFS succeeds, note insert fails | eventual compensation removes orphan file |
| TC-MED-006 | Replace/hard delete image with transient error | old safe until swap; eventual no orphan after purge |
| TC-SCHED-001 | Set future local date with UTC conversion | DB stores expected UTC timestamp and active true |
| TC-SCHED-002 | Past timestamp / invalid time / cancel | reject past; cancel prevents firing |
| TC-SCHED-003 | Advance fake clock over due time | notify adapter called once per intended occurrence in stable session |
| TC-SCHED-004 | OS notifications denied | UI shows failure/warning; never claims guaranteed delivery |
| TC-SCHED-005 | Close app during due time, restart | missed reminder behavior follows DEC-05; no unexplained state |
| TC-SAFE-001 | Delete note | entry removed from main list, visible trash (if DEC approved) |
| TC-SAFE-002 | Cancel permanent-delete modal | data + GridFS bytes retained |
| TC-SAFE-003 | Restore trashed note before 30 days | note back in active list, attachment usable |
| TC-SAFE-004 | Purge after retention | note and GridFS deleted, job idempotent |
| TC-SAFE-005 | Kill process during purge, restart | reconciler resumes safely, no leaked/accidentally reused blob |
| TC-ADV-001 | Pin note with any sort order | pinned first |
| TC-ADV-002 | Unpin then change sort | note returns to normal ordering |
| TC-SEC-001 | Lock/unlock note with correct passphrase | ciphertext at rest, decrypted memory only when needed |
| TC-SEC-002 | Wrong passphrase / tampered tag | authenticated decryption fails, no plaintext/traceback leaked |
| TC-SEC-003 | Check log/search/notification/temp for locked content | no plaintext exposure outside trusted editor |
| TC-SEC-004 | Unique salt/nonce, same plaintext re-encrypt | ciphertext differs, decrypt succeeds |
| TC-EXP-001 | Export Markdown+assets and PDF UTF-8 | content/image correct, Vietnamese glyphs intact |
| TC-EXP-002 | Export readonly dir, unsafe filename | useful error, no path traversal/no data corruption |
| TC-STAT-001 | Seed categories/priority counts including trash | counts exclude trashed, exact fixture match |
| TC-STAT-002 | Empty DB/zero divisions | no crashes/NaN display |
| TC-REC-001 | Save draft offline, terminate/restart, recover | encrypted draft restored, not wrongly marked remote-saved |
| TC-REC-002 | Reconnect with stale remote version | conflict shown, neither copy erased silently |
| TC-REC-003 | Keyring unavailable or local ciphertext tampered | fail closed with error, no plaintext fallback |

## 4. NFR / CST verification matrix

| Requirement | Procedure | Sample size/target | Evidence |
|---|---|---|---|
| NFR-PERF-01 | timed cold/warm startup 5k notes | original <2.0s, p95/20 trials proposed | `bench_startup.json` + host details |
| NFR-PERF-02 | indexed Mongo full text + filters 10k notes | original <200ms, p95/100 trials proposed | `explain` plans + p95 DB/UI |
| NFR-PERF-03 | forced DB sleep + smooth scroll UI instrumentation | source >=60 FPS; alternative <=50ms p95 event delay pending approval | event loop lat histogram + video |
| NFR-PERF-04 | RSS warmup & large image memory | <=150MB normal, <=300MB large image (original) | process samples/captures |
| NFR-SEC-01 | search repo, packaged artifact, runtime config | 0 hardcoded URIs/credentials | secrets scanning report |
| NFR-SEC-02 | inspect Mongo locked payload, crypto tamper tests | AES-256-GCM auth passes/fails appropriately | crypto pytest evidence |
| NFR-SEC-03 | type invalid filter, `$where`, `$gt`, unknown sort | no raw operator executes | injection pytest + DB log |
| NFR-REL-01 | network cut/restore, 3 retries then offline | no crash, no phantom save, encrypted draft recoverable | fault injection record |
| CST-01 | CI Python 3.10 + supported current | startup/unit/integration pass | matrix logs |
| CST-02/03 | UI widgets/main-thread tests | no Tk from worker, no stale result | architecture+UI test |
| CST-04 | 1MiB & 10MiB boundary + BSON size | inline/GridFS correct; no >16MB doc | attachment integration test |
| CST-05 | Windows, Ubuntu, macOS tested individually | each OS status PASS/FAIL/NOT VERIFIED | release platform table |

**Important:** Test hardware, OS, MongoDB version and DB location (same host/private LAN), note distribution, query list, CI revision must be included in every benchmark report; no fabricated measurements.

## 5. Data integrity & security test scenarios

1. Induce exception after GridFS upload, before Mongo note pointer write; reconcile orphan.
2. Induce exception after update reference, before delete old GridFS; ensure old cleanup.
3. Kill worker at `PURGING`; restart and process idempotently.
4. Trigger concurrent save on same note version; no lost update.
5. Send `note_id` invalid ObjectId / operator payload; repo typed validation.
6. Remove OS keyring privilege; local draft encryption not silently disabled into plaintext.
7. Notify locked note; content/title per DEC privacy policy not exposed.
8. Inject massive pixel image under 10MiB; Pillow guard.
9. Simulate timezone DST ambiguity/machine timezone switch.
10. Network connection stalls while user scrolls, types and closes editor; no Tk cross-thread update.

## 6. Entry/exit criteria từng cấp

- **PR entry:** FR/AC linked, tests defined; schema changes reviewed. **PR exit:** lint/type/architecture gate + related unit tests all green, reviewer approval.
- **Integration entry:** Mongo service fixture available, indexes migrations repeatable. **Exit:** no flaky P0 E2E, retry/compensation tested.
- **UAT entry:** feature freeze, seeded DB, operator instructions. **Exit:** critical UX flows passed by stakeholder; deviations recorded.
- **Release entry:** all tests with statuses, blocked reasons, backup restored once, artifacts packaged/tested. **Exit:** 0 blocker defects, known limitations signed, traceability documented.

## 7. Template test report cuối kỳ

```text
Build/Commit:
Environment: OS / Python / Tkinter/ttkbootstrap / MongoDB / CPU / RAM / network RTT
Scope: MVP / R1 / R2
Counts: Total / Pass / Fail / Blocked / Not Run
Functional: FR-01..11 / FR-13 / FR-17 statuses
NFR: raw measurements & p95 + target + verdict
Security: findings/severity/resolution
Open defects: ID / severity / owner / workaround / date
Risks accepted by: approver, approval date
Sign-off: PM + QA + PO/giảng viên
```

> **Không đổi `NOT RUN` thành `PASS` nếu chưa có execution evidence.**
