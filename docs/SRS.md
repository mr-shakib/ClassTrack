# ClassTrack — System Requirements Specification (v1, lean)

Department of Computer Science & Engineering, Daffodil International University

| | |
|---|---|
| **Version** | 1.0-lean |
| **Date** | 2026-09-12 |
| **Source** | `ClassTrack_System_Requirements.docx` (SRS v1.0) |
| **Scope** | Demo-grade vertical slice — every listed module reachable end-to-end |
| **Build window** | 2 days |
| **Stack** | FastAPI + SQLite/SQLAlchemy (backend), Next.js 15 + TypeScript + Tailwind (frontend) |
| **Reuses** | `open-routine` ingestion pipeline + routine data model |

---

## 1. Purpose and framing

ClassTrack monitors whether scheduled classes are actually conducted according to the
approved departmental routine, and manages the follow-up when they are not.

The system is **not** a faculty attendance tracker. It separately answers six questions:

1. Did the teacher conduct the class?
2. Was the teacher late, and by how many minutes?
3. Did office staff actually check the class?
4. Was a missed class later recovered?
5. Was the makeup physical or online?
6. Did an online class have proper administrative approval?

Keeping these six independent is the core design principle. Collapsing any two of them
(especially #1 and #3) produces unfair reporting and is the primary failure mode to avoid.

## 2. Scope of this version

This SRS describes a **lean v1**: the full module list from the source SRS, each implemented
to a working-but-shallow depth. It satisfies all ten acceptance criteria (AC-01…AC-10).

### 2.1 In scope

| # | Module | Depth in v1 |
|---|---|---|
| 1 | Authentication & RBAC | Full — JWT, 4 roles, enforced server-side |
| 2 | User management | Seed + minimal CRUD |
| 3 | Routine PDF import | **Full** — reused from `open-routine` |
| 4 | Routine verification | Review + conflict report + activate. Read-only review; corrections via re-ingest |
| 5 | Semester management | Single active semester, start/end dates |
| 6 | Academic calendar | Holiday list; instances skip holidays |
| 7 | Class instance generation | Full — idempotent materialisation |
| 8 | Room-wise staff checking | **Full** — mobile, one-tap |
| 9 | Status engine (12 states) | Full lifecycle, lazy + swept |
| 10 | Late / Missed / Not-Checked rules | **Full** — the correctness core |
| 11 | Live monitoring dashboard | Full, 30s poll |
| 12 | Teacher confirm / clarify | Full |
| 13 | Makeup management | Full — physical + online |
| 14 | Online approval workflow | Full — approve / reject |
| 15 | Conflict detection | Full — trivial on the lattice |
| 16 | Notifications | In-app only |
| 17 | Reporting | Daily + teacher-wise |
| 18 | Audit trail | Append-only writes + list view |
| 19 | System settings | Threshold config |

### 2.2 Explicitly deferred (extension points named in ARCHITECTURE.md)

- Email / SMS notification delivery — `NotificationChannel` interface exists, only `InAppChannel` implemented
- Editable routine verification grid — v1 reviews and re-ingests instead of cell-editing
- Monthly / semester / yearly comparison reports — daily + teacher-wise only
- Room-wise and staff-wise analytics reports
- Staff area/room assignment (`assigned_rooms`) — all staff see all rooms in v1
- Override-with-reason flow for conflicts — v1 blocks conflicts outright
- Multi-department support — schema carries `department`, UI assumes CSE
- PWA / offline checking, QR/NFC, geolocation — §24 of source SRS

## 3. User roles

| Role | Responsibilities |
|---|---|
| `SUPER_ADMIN` | Users, semesters, routine import, settings, all admin functions |
| `HOD` | Live dashboard, review missed/unchecked, approve online makeup, all reports |
| `STAFF` | Room-wise physical checking, record running/late/not-found |
| `TEACHER` | Own schedule, missed-class response, makeup scheduling, own reports |

### 3.1 Permission matrix (enforced in the API layer)

| Function | STAFF | TEACHER | HOD | SUPER_ADMIN |
|---|---|---|---|---|
| Check classroom | ✅ | ❌ | ✅ | ✅ |
| View own teacher report | ❌ | ✅ | ✅ | ✅ |
| View all teacher reports | ❌ | ❌ | ✅ | ✅ |
| Schedule makeup class | ❌ | ✅ | ✅ | ✅ |
| Approve online makeup | ❌ | ❌ | ✅ | ✅ |
| Upload / activate routine | ❌ | ❌ | ✅ | ✅ |
| Modify monitoring rule | ❌ | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ❌ | ✅ |

## 4. The lattice — foundational constraint

Inherited from `open-routine`. The DIU routine is a fixed **6 × 6 grid**, not a free-form calendar.

```
DAYS  = Saturday, Sunday, Monday, Tuesday, Wednesday, Thursday   (Friday = weekend)
SLOTS = 08:30-10:00, 10:00-11:30, 11:30-01:00,
        01:00-02:30, 02:30-04:00, 04:00-05:30
```

Every class occupies exactly one cell. Two consequences that shape the entire system:

1. **Occupancy is string equality on the slot label.** Two classes can never partially
   overlap, so no interval arithmetic is needed anywhere. Conflict detection (§9) reduces
   to a uniqueness check on `(date, time_slot, room)` / `(date, time_slot, teacher)` /
   `(date, time_slot, section)`.
2. `start_min` / `end_min` are **derived, for display and sorting only** — they answer
   "what is on right now". They must never become the occupancy test.

> ⚠️ **Do not replace slot-label equality with time-range overlap logic.** It is the single
> most tempting and most damaging refactor available in this codebase.

## 5. Class status lifecycle

| Status | Meaning | Set by |
|---|---|---|
| `UPCOMING` | Slot has not started | Derived from clock |
| `ONGOING` | Slot is currently active, no check yet | Derived from clock |
| `RUNNING` | Staff verified the class is running | Staff check |
| `LATE` | Teacher arrived after scheduled start | Staff check + arrival time |
| `MISSED` | Teacher absent past threshold, confirmed by check | Sweep job (from `TEACHER_NOT_FOUND`) |
| `NOT_CHECKED` | No staff input within the checking window | Sweep job |
| `MAKEUP_SCHEDULED` | Makeup created for this missed class | Teacher |
| `MAKEUP_COMPLETED` | Makeup class conducted | Staff check on makeup instance |
| `ONLINE_PENDING` | Online makeup requested, awaiting approval | Teacher |
| `ONLINE_APPROVED` | HoD approved online delivery | HoD |
| `ONLINE_REJECTED` | HoD rejected online delivery | HoD |
| `CANCELLED` | Officially cancelled | Admin |

### 5.1 Transition rules

```
UPCOMING ──clock──> ONGOING ──staff:RUNNING──────> RUNNING
                            ──staff:LATE─────────> LATE
                            ──staff:NOT_FOUND────> (pending) ──threshold──> MISSED
                            ──no input────────────────window close──────> NOT_CHECKED

MISSED ──teacher confirms──> MISSED (confirmed)
       ──teacher disputes──> MISSED (disputed, flagged for HoD)
       ──teacher schedules physical──> MAKEUP_SCHEDULED ──staff check──> MAKEUP_COMPLETED
       ──teacher requests online────> ONLINE_PENDING ──HoD──> ONLINE_APPROVED | ONLINE_REJECTED
```

Terminal statuses are never recomputed by the sweep. Status changes are always written to
the audit log with the previous value.

## 6. Late, Missed, and Not-Checked rules

### BR-03 / BR-04 — Late arrival
Staff records actual arrival time. The system computes:

```
late_minutes = actual_arrival_time − scheduled_start_time
```

Example: class starts 10:00, teacher arrives 10:08 → `LATE`, 8 minutes.

### BR-05 — Missed threshold
Default **30 minutes** after scheduled start, configurable via `settings.missed_threshold_minutes`.
A class becomes `MISSED` only when a staff member has recorded `TEACHER_NOT_FOUND` **and** the
threshold has elapsed. Absence of a check never produces `MISSED`.

### BR-06 — Not Checked
If **no** monitoring input is submitted within the checking window (default 30 min), the class
becomes `NOT_CHECKED` — a **staff** failure, never a teacher absence.

> This separation is the single most important correctness requirement in the system.
> `MISSED` requires positive evidence of teacher absence. `NOT_CHECKED` is the absence of evidence.

## 7. Room-wise checking (AC-02)

Staff UI is organised **by room**, mobile-first, current slot first.

Each room card shows: room · teacher · course · section · scheduled time, and three primary
actions — **Running** · **Late** · **Teacher Not Found**. Remark is secondary and optional.

- Normal class check = **one tap**.
- `LATE` requires an arrival time (defaults to now — still one extra tap).
- Approved online makeup classes are **excluded** from this list (BR-12).
- Physical makeup classes **appear** in this list automatically (BR-10).
- Check submission is **idempotent** per `(instance_id)` — re-submitting updates, never duplicates.

## 8. Makeup workflow

```
MISSED ─> teacher confirms ─> chooses mode
                               ├─ PHYSICAL ─> conflict check ─> MAKEUP_SCHEDULED
                               │                                 └─> enters room-wise checking
                               └─ ONLINE  ─> ONLINE_PENDING ─> HoD decision
                                                                ├─ approve ─> ONLINE_APPROVED
                                                                │             (excluded from checking)
                                                                └─ reject  ─> ONLINE_REJECTED
```

Every makeup permanently references its original missed instance (BR-13). The final record
shows the sequence `Missed → Makeup Scheduled → Makeup Completed`.

## 9. Conflict detection

On the lattice this is three indexed lookups against `class_instance` for the proposed
`(date, time_slot)`:

| Conflict | Check |
|---|---|
| Teacher | Teacher already has an instance at that date + slot |
| Room | Room already occupied at that date + slot |
| Section | Section already has a class at that date + slot |
| Holiday | Proposed date is in `holiday` |

v1 **blocks** on any conflict. The override-with-mandatory-reason path (source SRS §11) is
deferred; `ConflictReport` already carries an `overridable` flag for it.

## 10. Reporting

**Daily report** — scheduled / checked / running / late / missed / not-checked / makeup / online.

**Teacher-wise report** — total scheduled, conducted, late, missed, makeup scheduled,
makeup completed, makeup pending, online approved.

```
Monitoring Completion Rate = checked_classes / assigned_classes × 100
```

Filters in v1: date range, teacher, semester. Deferred: course, section, room, day, month, status.

## 11. Audit trail (AC-10)

Append-only. No update, no delete — enforced at the service layer. Every record captures
actor · entity · action · before → after · reason · timestamp.

Logged actions: class check submitted, status changed, teacher confirmed/disputed,
makeup scheduled, online approved/rejected, routine activated, setting modified.

## 12. Non-functional requirements

| Category | v1 target |
|---|---|
| Performance | Checking action < 300 ms; dashboard < 1 s |
| Scale | 200+ faculty, ~8,000 instances/semester — comfortable for SQLite |
| Usability | Staff performs a check with no training; one tap normal case |
| Reliability | Idempotent checks; no duplicate monitoring records under concurrency |
| Security | JWT auth, bcrypt hashes, role checks server-side on every endpoint |
| Backup | SQLite file on a Docker named volume; `.db` copy is a complete backup |
| Auditability | Every monitoring and approval action traceable to user + timestamp |

## 13. Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| AC-01 | Admin uploads, verifies, activates a routine for a semester | `POST /admin/routine/ingest` → `/admin/routine/activate` |
| AC-02 | Staff sees and checks ongoing physical classes room-wise on mobile | `/staff` at 360px viewport |
| AC-03 | Late arrival recorded, minutes calculated automatically | Check with `outcome=LATE` |
| AC-04 | Missed and Not Checked handled separately | Sweep job unit test |
| AC-05 | Teacher notified of missed class and can respond | Notification + `/teacher` |
| AC-06 | Teacher schedules physical makeup; it appears in checking | Makeup → `/staff` |
| AC-07 | Teacher requests online makeup; HoD approves/rejects | `/teacher/makeup` → `/approvals` |
| AC-08 | Approved online makeup absent from physical checking | `/staff` excludes it |
| AC-09 | Teacher-wise reports for day/month/semester/year | `/reports` (day + semester in v1) |
| AC-10 | Audit logs preserve monitoring and approval history | `/admin/audit` |

## 14. Traceability — source SRS business rules

| Rule | Where implemented |
|---|---|
| BR-01 | `instance_service.generate()` |
| BR-02 | `/staff` room-grouped UI |
| BR-03, BR-04 | `check_service.submit()` late calculation |
| BR-05 | `sweep.finalise()` threshold |
| BR-06 | `sweep.finalise()` NOT_CHECKED branch |
| BR-07 | `notification_service.notify_missed()` |
| BR-08 | `POST /instances/{id}/respond` |
| BR-09 | `POST /makeup` gated on confirmed missed |
| BR-10 | Makeup creates a `ClassInstance` with `is_makeup=True` |
| BR-11 | `mode=ONLINE` → `ONLINE_PENDING` |
| BR-12 | Staff query filters `status != ONLINE_APPROVED` |
| BR-13 | `MakeupClass.original_instance_id` FK, non-null |
| BR-14 | `conflict_service.check()` |
| BR-15 | `audit_service.record()` on every status change |
