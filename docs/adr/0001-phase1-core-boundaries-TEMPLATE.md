# ADR-0001 — Phase 1 Core Boundaries / Ports / Minimal Schema

**Status:** Proposed (KHÔNG tự đánh Accepted).  
**Draft date:** 2026-10-09. **Owner:** M1. **Reviewers:** M2, M3, M4.  
**Context:** repo `develop` có scaffold domain/application/infrastructure/presentation, nhưng cần hợp đồng đủ ổn định để 5 người phát triển song song và có đường mở rộng sau này.

## Decision — đề xuất

- Domain thuần Python, application orchestrate use cases định nghĩa Protocol ports, infrastructure implement Mongo adapters, presentation Tk chỉ dùng public use cases/DTO, bootstrap là composition root.
- Minimum notes schema: opaque ID (Mongo mapper dùng ObjectId), title, content_plain, category ID, priority+rank, created_at/updated_at UTC, version, client_operation_id, is_deleted default false, schema_version. Categories: name/name_key unique, color_hex, timestamps.
- Create idempotent theo operation ID; update optimistic version CAS; không trực tiếp dùng TTL hay GridFS trong Phase 1.
- Tk widgets/mainloop/root.after chỉ ở UI main thread; worker gửi `queue.Queue` result, executor bounded, shutdown safe.

## Alternatives & trade-offs

1. Tk gọi trực tiếp Mongo: reject vì coupling và nguy cơ đơ UI.
2. FastAPI/microservices ngay: reject vì overhead chưa cần cho desktop scope/team 5.
3. Only fake/in-memory note repo: chấp nhận unit tests, **không** đủ điều kiện demo persistence Phase 1.
4. Direct Mongo dev/private có kiểm soát: chấp nhận tạm cho môi trường học tập; không phải public SaaS, sau này API+identity mới hợp lý nếu phân phối rộng.

## Blocking open decisions

- [ ] DEC-01 scope và FR impacts được người có thẩm quyền xác nhận
- [ ] DEC-04 DB trust boundary / credential / TLS/private policy
- [ ] DEC-08 content limit/schema target (SRS v2 vẫn đề xuất)

## Approval

- [ ] M1 PM/Architect — reviewer name/date:
- [ ] M2 UI — reviewer name/date:
- [ ] M3 Core — reviewer name/date:
- [ ] M4 Data — reviewer name/date:
- [ ] Contract tests/architecture gate spec linked:

**Hành động:** sau khi phê duyệt, tạo `docs/adr/0001-phase1-core-boundaries.md` và đổi status thành `Accepted`. Không phát biểu template này đã accepted.
