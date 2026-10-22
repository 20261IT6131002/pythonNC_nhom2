# PHASE 3 — PLAN 02
## Reminder Configuration → Reminder Delivery → Phase 3 Acceptance

**Project:** NoteApp / `20261IT6131002/pythonNC_nhom2`  
**Depends on:** `PHASE3_PLAN_01_CATEGORY_IMAGE.md` hoàn tất hoặc contracts ổn định  
**Requirements:** FR-09, FR-10  
**Perspective:** Senior Developer + Tech Lead  
**Target:** đóng toàn bộ MVP P0 còn lại của Phase 3  
**Merge target cuối:** `feature/phase-3` → `develop`

---

# 1. Mục tiêu

Plan 02 hoàn thiện reminder subsystem theo hai vertical slices:

1. **FR-09 — Configure Reminder**
2. **FR-10 — Deliver Reminder**

Sau đó thực hiện:

- regression Phase 1–3.
- acceptance Phase 3.
- cập nhật RTM.
- chốt baseline trước Phase 4.

Không mở rộng thành cloud scheduler, Windows Service, background daemon hoặc multi-device notification.

---

# 2. Điểm xuất phát

Repo đã có skeleton:

```text
src/noteapp/domain/entities/reminder.py

src/noteapp/application/commands/set_reminder.py
src/noteapp/application/services/reminder_service.py
src/noteapp/application/ports/notification_gateway.py

src/noteapp/infrastructure/notifications/
└── plyer_gateway.py

src/noteapp/infrastructure/scheduler/
└── reminder_poller.py
```

Các file trên hiện chưa thể được coi là implementation đầy đủ.

---

# 3. Scope Phase 3 Reminder

## In scope

```text
set reminder
reschedule reminder
cancel reminder
persist reminder
show reminder state
poll due reminders
claim due reminder
OS notification
missed reminder on restart
mark delivered
avoid obvious duplicates
clean shutdown
```

## Out of scope

```text
background OS service
push notification
email notification
cloud scheduler
cross-device sync
recurring reminder
cron expression
snooze
FR-14 encryption
```

---

# 4. Architecture

```text
Presentation
    ↓
Reminder Presenter
    ↓
Application Use Cases
    ↓
Reminder Repository Port
    ↓
Mongo Adapter

Reminder Poller
    ↓
Application Reminder Delivery Service
    ↓
NotificationGateway
    ↓
PlyerGateway
```

`ReminderPoller` không được chứa business policy.

`PlyerGateway` không được query database.

UI không gọi scheduler internals.

---

# 5. Trình tự phát triển

```text
P3B-00 Reminder Contract Freeze
       ↓
P3B-01 Reminder Domain State Machine
       ↓
P3B-02 Reminder Repository Contract
       ↓
P3B-03 Set / Reschedule / Cancel Use Cases
       ↓
P3B-04 Reminder UI
       ↓
P3B-05 Due Query + Atomic Claim
       ↓
P3B-06 Notification Gateway
       ↓
P3B-07 Poller Runtime Integration
       ↓
P3B-08 Restart / Missed Reminder
       ↓
P3B-09 Fault Handling + Shutdown
       ↓
P3B-10 Phase 3 Regression / Acceptance
```

---

# 6. P3B-00 — Contract Freeze

Chốt trước code.

## 6.1 Time semantics

Persistence:

```text
UTC only
```

Presentation:

```text
Local timezone
```

Không lưu naive datetime.

## 6.2 Reminder lifecycle

Khuyến nghị state tối thiểu:

```text
ACTIVE
DELIVERED
CANCELLED
```

Không thêm `SNOOZED`, `FAILED`, `RECURRING` ở Phase 3 nếu chưa có requirement.

## 6.3 Missed reminder policy

Chọn rule:

> Khi app khởi động, reminder ACTIVE có `due_at <= now` sẽ được xử lý một lần theo cùng delivery flow.

Không silently drop.

## 6.4 Delivery guarantee

Desktop-only MVP không cần claim "exactly once".

Mục tiêu thực tế:

> best-effort delivery với atomic claim/idempotency để giảm duplicate.

Documentation phải dùng wording đúng.

## 6.5 Poll interval

Không hard-code policy rải rác.

Config qua infrastructure/runtime config.

---

# 7. P3B-01 — Reminder Domain State Machine

## 7.1 Entity

Conceptual model:

```text
Reminder
├── due_at_utc
├── status
├── delivered_at
└── updated_at
```

Có thể embedded trong Note hoặc persistence model riêng tùy contract đã chốt, nhưng Domain API phải rõ.

## 7.2 Invariants

```text
ACTIVE:
    due_at > set_time tại thời điểm tạo/reschedule

DELIVERED:
    không được poll lại như ACTIVE

CANCELLED:
    không được deliver

reschedule:
    status quay về ACTIVE
```

## 7.3 Clock

Mọi logic thời gian cần inject `Clock`.

Không:

```python
datetime.now()
```

trực tiếp trong core use case.

---

# 8. P3B-02 — Reminder Repository Contract

Capability tối thiểu:

```text
set/remap reminder
cancel reminder
find due reminders
claim reminder
mark delivered
```

Nếu reminder embedded trong Note repository thì vẫn cần API ở Application thể hiện đúng capability.

Không expose Mongo query ra Application.

---

# 9. P3B-03 — Configure Reminder Use Cases

Tách rõ:

```text
SetReminder
RescheduleReminder
CancelReminder
```

Hoặc equivalent command design.

## 9.1 Set

Flow:

```text
UI local datetime
      ↓
timezone conversion
      ↓
validate
      ↓
UTC
      ↓
persist ACTIVE
```

## 9.2 Reschedule

```text
ACTIVE/DELIVERED/CANCELLED
          ↓
new future due_at
          ↓
ACTIVE
```

Nếu product owner muốn cấm reschedule DELIVERED thì phải chốt trong contract, không để dev tự suy đoán.

## 9.3 Cancel

Phải persist trạng thái cancel, không chỉ remove button state ở UI.

---

# 10. Timezone Handling

## 10.1 Conversion

UI giữ local datetime.

Application nhận timezone-aware timestamp hoặc DTO đủ timezone context.

Persistence giữ UTC.

## 10.2 Edge cases

Test:

- future normal.
- past.
- DST nonexistent local time.
- DST ambiguous time.
- timezone invalid.
- timezone override qua config.

Không "guess" ambiguous local time.

---

# 11. P3B-04 — Reminder UI

## 11.1 UI controls

```text
Set reminder
Change reminder
Cancel reminder
```

Hiển thị:

```text
Reminder: 21:00 25/10/2026
```

theo local timezone.

## 11.2 UI states

```text
NO_REMINDER
ACTIVE
SAVING
ERROR
```

Delivery state không nên làm editor save state bị lẫn.

## 11.3 Async

Persistence chạy worker.

Không block main thread.

Stale response phải bỏ nếu user đã switch note.

---

# 12. P3B-05 — Due Query + Atomic Claim

Đây là phần quan trọng nhất của FR-10.

## 12.1 Query

Chỉ lấy:

```text
status == ACTIVE
due_at <= now
note not permanently deleted
```

Trash policy phải chốt:

Khuyến nghị:

> soft-deleted note không phát reminder.

Khi restore, nếu reminder quá hạn, xử lý theo missed-reminder policy.

## 12.2 Claim

Không dùng:

```text
find due
→ notify
→ update delivered
```

một cách naïve nếu có khả năng poll overlap.

Cần atomic transition / claim equivalent:

```text
ACTIVE
  ↓ atomic claim
CLAIMED internally
  ↓ notify
DELIVERED
```

Nếu không muốn expose `CLAIMED` thành domain state public, có thể implement bằng atomic repository operation/internal lease metadata.

Tech Lead review bắt buộc với phần này.

---

# 13. P3B-06 — Notification Gateway

Application port:

```text
NotificationGateway
```

Infrastructure:

```text
PlyerGateway
```

Application truyền:

```text
title
message
```

Không truyền domain object lớn hoặc Mongo document vào gateway.

## 13.1 Failure policy

Notification OS fail:

- không crash app.
- log sanitized error.
- delivery state xử lý theo policy đã freeze.
- không infinite retry loop.

Phase 3 có thể chọn bounded retry hoặc để reminder trở lại eligible theo safe rule, nhưng phải document.

---

# 14. P3B-07 — Reminder Poller

Poller là infrastructure runtime.

Trách nhiệm:

```text
wake up
↓
invoke application delivery use case
↓
sleep
```

Không chứa:

- query BSON.
- state business transitions.
- notification string policy.
- Tk widget access.

## 14.1 Threading

Poller không được gọi Tk trực tiếp.

Nếu cần refresh UI badge:

```text
poller
  ↓
application result/event
  ↓
queue
  ↓
UI main thread
```

## 14.2 Shutdown

App close:

```text
signal stop
↓
poll loop exits
↓
worker executor shutdown
↓
Mongo client close
↓
Tk destroy
```

Không daemon thread bỏ mặc.

---

# 15. P3B-08 — Startup / Missed Reminder

Startup order khuyến nghị:

```text
load config
↓
create repositories/gateways
↓
build application services
↓
start UI event bridge
↓
perform missed reminder scan
↓
start poller
```

Không start poller trước khi dependencies sẵn sàng.

Missed reminder case:

```text
app closed at 10:00
due at 10:05
app reopened at 10:30
      ↓
due ACTIVE reminder detected
      ↓
claim
      ↓
notify
      ↓
DELIVERED
```

---

# 16. P3B-09 — Failure Scenarios

Bắt buộc review và test:

## DB unavailable

```text
poller → repository failure
```

Expected:

- log.
- no crash.
- retry ở vòng poll sau.
- không busy loop.

## Notification provider fail

Expected:

- app sống.
- state transition theo delivery policy.
- lỗi không lộ stack trace ra UI.

## Cancel vs poll race

```text
T1 poll sees ACTIVE
T2 user cancel
T1 tries claim
```

Atomic claim/cancel phải quyết định winner rõ.

## Reschedule vs poll race

Không deliver reminder theo due time cũ sau khi reschedule đã commit.

## Shutdown while poll running

Không corrupt state, không treo process.

---

# 17. P3B-10 — Tests

## Unit

```text
test_reminder_entity.py
test_set_reminder.py
test_reschedule_reminder.py
test_cancel_reminder.py
test_reminder_delivery.py
```

FakeClock bắt buộc.

## Contract

```text
test_reminder_repository_contract.py
test_notification_gateway_contract.py
```

## Integration

```text
test_reminder_mongo.py
test_reminder_due_claim.py
test_reminder_races.py
```

## UI

```text
test_reminder_dialog.py
test_reminder_state_ui.py
```

## Runtime

```text
test_reminder_poller.py
test_reminder_shutdown.py
```

---

# 18. Acceptance Cases

| Requirement | Scenario | Expected |
|---|---|---|
| FR-09 | set future | ACTIVE |
| FR-09 | set past | reject |
| FR-09 | reschedule | new due time |
| FR-09 | cancel | no delivery |
| FR-10 | due reminder | notify |
| FR-10 | delivered | no duplicate |
| FR-10 | cancelled | no notify |
| FR-10 | restart after due | missed policy |
| FR-10 | overlapping poll | max one successful claim |
| FR-10 | OS notify fail | app remains healthy |

---

# 19. Phase 3 Regression

Sau khi FR-09/10 xong phải chạy lại Phase 1–3.

Critical user journey:

```text
Create
→ Edit
→ Category
→ Priority
→ Search
→ Filter
→ Sort
→ Attach image
→ Set reminder
→ Trash
→ Restore
→ Reminder delivery
→ Permanent delete
```

Kiểm tra:

- optimistic conflict.
- search excludes trash.
- attachment preserved through restore.
- trashed note không phát reminder.
- permanent delete cleanup.
- category filter vẫn đúng.
- UI responsiveness.

---

# 20. NFR Gates

## Performance

- poller không busy loop.
- DB polling query có index phù hợp.
- image operations không làm Tk freeze.
- search benchmark Phase 2 không regress đáng kể.

## Reliability

- no duplicate obvious delivery.
- no attachment orphan.
- app restart safe.
- shutdown clean.

## Security

- no secret in logs.
- no raw database exception in UI.
- image validation vẫn giữ.
- notification content không leak stack/config.

## Maintainability

- dependency direction pass.
- no circular import.
- public contract documented.
- tests map về FR.

---

# 21. Branch Strategy

Task branches:

```text
feature/p3-reminder-contract
feature/p3-reminder-core
feature/p3-reminder-data
feature/p3-reminder-ui
feature/p3-reminder-delivery
test/p3-reminder-acceptance
chore/p3-release-gate
```

Merge lần lượt vào:

```text
feature/phase-3
```

Sau full acceptance:

```text
feature/phase-3 → develop
```

Không merge partial reminder subsystem vào develop nếu state machine/persistence chưa coherent.

---

# 22. Commit Sequence Gợi Ý

```text
docs(p3): freeze reminder semantics and missed delivery policy
feat(core): implement reminder state and commands
feat(data): persist reminder state and due query
feat(ui): add reminder configuration workflow
feat(data): add atomic due reminder claim
feat(notify): implement notification gateway adapter
feat(runtime): implement bounded reminder poller
fix(runtime): handle restart and missed reminders
test(p3): cover reminder races and delivery failures
test(p3): run phase 1 to phase 3 regression
docs(p3): record phase 3 acceptance evidence
```

---

# 23. Tech Lead Review Gates

## Gate A — Contract

Review trước implementation:

- [ ] state machine.
- [ ] timezone.
- [ ] missed reminder.
- [ ] trash interaction.
- [ ] atomic claim semantics.

## Gate B — Core/Data

- [ ] repository port không leak Mongo.
- [ ] FakeClock test đầy đủ.
- [ ] due query indexed.
- [ ] cancel/reschedule race covered.

## Gate C — Runtime

- [ ] no Tk access từ worker.
- [ ] poller bounded.
- [ ] shutdown clean.
- [ ] notification error safe.

## Gate D — Phase Acceptance

- [ ] FR-04 Done.
- [ ] FR-08 Done.
- [ ] FR-09 Done.
- [ ] FR-10 Done.
- [ ] regression green.
- [ ] CI green.
- [ ] RTM updated.

---

# 24. Phase 3 Definition of Done

Phase 3 chỉ đóng khi:

```text
FR-04 Category      DONE
FR-08 Image         DONE
FR-09 Set reminder  DONE
FR-10 Deliver       DONE
```

Và:

- [ ] CI xanh trên head Phase 3.
- [ ] unit/contract/integration/UI pass.
- [ ] architecture dependency gate pass.
- [ ] no open blocker defect.
- [ ] no known data-loss bug.
- [ ] no attachment orphan.
- [ ] reminder duplicate/race risk đã được test.
- [ ] README cập nhật.
- [ ] Phase 3 test report có evidence.
- [ ] RTM cập nhật.
- [ ] rollback notes được viết.
- [ ] Tech Lead + QA review hoàn tất.

---

# 25. Handover Sang Phase 4

Không kéo các feature sau vào Phase 3:

```text
FR-12 Pin
FR-14 Locked Note
FR-15 Export
FR-16 Statistics
```

Thứ tự khuyến nghị sau Phase 3:

```text
Phase 4
├── FR-12 Pin
└── FR-14 Locked Note

Phase 5
├── FR-15 Export
└── FR-16 Statistics
```

FR-14 cần security design riêng, không ghép ngầm vào reminder/image code.

---

# 26. Stop Conditions

Dừng và yêu cầu Tech Lead/PO review khi:

- muốn recurring reminder.
- muốn background notification khi app đóng.
- cần OS-specific daemon.
- muốn cloud notification.
- muốn đổi storage schema lớn.
- cần encrypt reminder content.
- cần transaction nhiều collection.
- atomic claim không thể đảm bảo bằng adapter hiện tại.
- behavior trash/reminder chưa chốt.

---

# 27. Kết quả mong đợi

Kết thúc Plan 02:

```text
Phase 2 complete
      ↓
Plan 01
FR-04 + FR-08
      ↓
Plan 02
FR-09 + FR-10
      ↓
12/16 FR functional
      ↓
Phase 3 accepted
      ↓
Ready for Phase 4
```

Phase 3 lúc này là một milestone có ý nghĩa kỹ thuật rõ ràng:

> **NoteApp chuyển từ text-note CRUD/search sang rich note có media + reminder, trong khi vẫn giữ strict architecture, data safety và async desktop behavior.**
