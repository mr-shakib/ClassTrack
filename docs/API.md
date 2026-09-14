# ClassTrack — API Contract

Base: `/api/v1` · Auth: JWT in an httpOnly cookie · All timestamps ISO-8601, `Asia/Dhaka`.

Roles: `SUPER_ADMIN` (SA) · `HOD` · `STAFF` (ST) · `TEACHER` (T)

> Freeze this contract before parallel work starts. Frontend types in `web/lib/types.ts`
> mirror it exactly.

---

## 1. Auth

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | public | Sets the session cookie |
| `POST` | `/auth/logout` | any | Clears it |
| `GET` | `/auth/me` | any | Current user + role |

```jsonc
// POST /auth/login -- username is an email, or a teacher's initial
{ "username": "staff1@diu.edu", "password": "..." }
{ "username": "SRH", "password": "..." }
// 200
{ "id": 3, "full_name": "Staff One", "role": "STAFF", "teacher_initial": null }
// 401 { "detail": "Invalid credentials" }
```

`email` is still accepted as the key for `username`.

### Teacher accounts

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/admin/teachers` | HOD, SA | Faculty list, with `has_account` per initial |
| `POST` | `/admin/teachers/{initial}/account` | HOD, SA | `{ "password": "..." }` — create the sign-in |
| `PUT` | `/admin/teachers/{initial}/password` | HOD, SA | `{ "password": "..." }` — reset it |

One account per initial. The account's email is a placeholder
(`<initial>@teacher.classtrack`); the teacher signs in with the initial.

## 2. Staff checking — the hot path

### `GET /checking/rooms`
Roles: ST, HOD, SA

Room-wise list for a date + slot. Defaults to **now**. Excludes approved-online makeups (BR-12);
includes physical makeups (BR-10).

```
?date=2026-09-13&slot=10:00-11:30     both optional
```

```jsonc
{
  "date": "2026-09-13",
  "time_slot": "10:00-11:30",
  "slot_state": "ONGOING",          // UPCOMING | ONGOING | CLOSED
  "window_closes_at": "2026-09-13T10:30:00+06:00",
  "rooms": [
    {
      "instance_id": 1042,
      "room": "KT-305", "room_type": "Theory",
      "course_code": "CSE311", "section": "70-A",
      "teacher_initial": "TCA", "teacher_name": "Teacher A",
      "scheduled_start": "10:00", "scheduled_end": "11:30",
      "is_makeup": false,
      "status": null,               // null = awaiting check
      "check": null                 // or the submitted CheckRecord
    }
  ]
}
```

### `POST /checking/{instance_id}`
Roles: ST, HOD, SA — **idempotent**, upserts on `instance_id`.

```jsonc
{ "outcome": "LATE",              // RUNNING | LATE | TEACHER_NOT_FOUND
  "arrival_time": "10:08",        // required iff LATE
  "remark": null }
// 200
{ "instance_id": 1042, "status": "LATE", "late_minutes": 8,
  "checked_by": "Staff One", "checked_at": "2026-09-13T10:08:00+06:00" }
```

- `late_minutes` is computed server-side; a submitted value is ignored (BR-04, I6).
- `TEACHER_NOT_FOUND` does **not** immediately set `MISSED` — the sweep does, once the
  threshold elapses (BR-05). Response status stays `null` until then.
- Re-submitting replaces the previous check and writes an audit row.

## 3. Class instances

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/instances` | all (scoped) | Filter by date, teacher, room, status, section |
| `GET` | `/instances/{id}` | all (scoped) | Detail + check + makeup chain + audit |
| `POST` | `/instances/{id}/respond` | T | Confirm or dispute a missed class (BR-08) |
| `POST` | `/instances/{id}/cancel` | HOD, SA | Cancel with reason |

`TEACHER` callers are force-scoped to their own `teacher_initial` — the filter is applied
server-side regardless of query parameters.

```jsonc
// POST /instances/1042/respond
{ "response": "CONFIRMED", "note": null }   // CONFIRMED | DISPUTED
```
A `DISPUTED` response notifies HoD and flags the record for review. It does **not** change
the stored status — the original monitoring record survives (source SRS §9.1).

## 4. Live dashboard

### `GET /dashboard/live`
Roles: HOD, SA. Frontend polls every 30s.

```jsonc
{
  "as_of": "2026-09-13T10:15:00+06:00",
  "current_slot": "10:00-11:30",
  "summary": { "scheduled_now": 24, "running": 18, "late": 3, "missed": 1,
               "not_checked": 2, "makeup_physical": 1, "online_approved": 1 },
  "rows": [
    { "instance_id": 1042, "room": "KT-305", "teacher_initial": "TCA",
      "course_code": "CSE311", "section": "70-A", "time_slot": "10:00-11:30",
      "status": "LATE", "late_minutes": 12,
      "checked_by": "Staff Two", "checked_at": "10:12" }
  ],
  "attention": { "missed_today": 1, "not_checked_today": 2,
                 "pending_online": 1, "pending_makeup": 3, "disputes": 0 }
}
```

## 5. Makeup

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/makeup/free-rooms` | T, HOD, SA | `?date=&time_slot=` — empty rooms of the active routine |
| `POST` | `/makeup/check-conflict` | T, HOD, SA | Validate before submitting (BR-14) |
| `POST` | `/makeup` | T, HOD, SA | Request a reschedule |
| `GET` | `/makeup` | scoped | List; teachers see their own |
| `POST` | `/makeup/{id}/complete` | HOD, SA | Mark completed |

```jsonc
// POST /makeup/check-conflict
{ "date": "2026-09-20", "time_slot": "02:30-04:00",
  "room": "KT-305", "teacher_initial": "TCA", "section": "70-A" }
// 200
{ "ok": false, "overridable": true,
  "conflicts": [ { "type": "ROOM",
                   "message": "KT-305 is occupied by CSE333 (68-B)",
                   "instance_id": 1120 } ] }
```

Conflict types: `TEACHER` · `ROOM` · `SECTION` · `HOLIDAY`.

```jsonc
// POST /makeup
{ "original_instance_id": 1042, "mode": "PHYSICAL",
  "date": "2026-09-20", "time_slot": "02:30-04:00",
  "room": "KT-305", "reason": "Was on official duty" }
```

The original must be `MISSED`, or unresolved with a `TEACHER_NOT_FOUND` check — a teacher
can ask as soon as staff report them absent, without waiting for the missed threshold.
`GET /instances?needs_reschedule=true` lists exactly those classes.

Every request starts `PENDING` with no instance, and the HoD is notified.

| Mode | Original becomes |
|---|---|
| `PHYSICAL` | `MAKEUP_REQUESTED`. The room counts as taken for `free-rooms` and conflict checks. |
| `ONLINE` | `ONLINE_PENDING` |

`409` with the conflict report if validation fails; `422` if the slot has already started.
v1 does not accept an override.

The teacher is notified when staff record `TEACHER_NOT_FOUND` or `LATE` (`CLASS_REPORTED`),
and again when the sweep marks the class `MISSED` (`MISSED_CLASS`).

## 6. Reschedule approvals

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/approvals/pending` | HOD, SA | Queue of pending requests, both modes |
| `POST` | `/approvals/{makeup_id}/decide` | HOD, SA | Approve or reject |

```jsonc
{ "decision": "APPROVE", "note": "Approved for this week only" }
```

Approval re-runs the conflict check; `409` if the cell has been taken since.

| Decision | `PHYSICAL` | `ONLINE` |
|---|---|---|
| `APPROVE` | Makeup → `SCHEDULED`, original → `MAKEUP_SCHEDULED`. An `is_makeup=1` instance is created and **appears in `/checking/rooms`** for that room and slot (BR-10). | Makeup → `APPROVED`, original → `ONLINE_APPROVED`. The instance is **excluded from `/checking/rooms`** (BR-12, AC-08). |
| `REJECT` | Makeup → `REJECTED`, original → back to `MISSED`, so the teacher requests again. | Makeup → `REJECTED`, original → `ONLINE_REJECTED`. |

The teacher is notified either way.

## 7. Reports

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/reports/daily` | HOD, SA | `?date=` |
| `GET` | `/reports/teacher` | scoped | `?teacher=&from=&to=` |
| `GET` | `/reports/staff` | HOD, SA | Monitoring completion rate |

```jsonc
// GET /reports/teacher?teacher=TCA&from=2026-09-01&to=2026-12-31
{ "teacher_initial": "TCA", "teacher_name": "Teacher A",
  "range": { "from": "2026-09-01", "to": "2026-12-31" },
  "total_scheduled": 120, "conducted": 113, "late": 4, "missed": 3,
  "makeup_scheduled": 3, "makeup_completed": 2, "makeup_pending": 1,
  "online_approved": 1, "not_checked": 0 }
```

```jsonc
// GET /reports/staff  →  Monitoring Completion Rate = checked / assigned × 100
{ "rows": [ { "user_id": 3, "name": "Staff One",
              "assigned": 60, "checked": 57, "completion_rate": 95.0 } ] }
```

`TEACHER` callers may only request their own initial (403 otherwise).

## 8. Notifications

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/notifications` | any | `?unread=true` |
| `POST` | `/notifications/{id}/read` | any | Mark read |
| `POST` | `/notifications/read-all` | any | Mark all read |

## 9. Admin

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `POST` | `/admin/routine/ingest` | HOD, SA | Upload PDF (multipart) → report |
| `GET` | `/admin/routine/{id}/review` | HOD, SA | Parsed sessions + conflicts + skipped cells |
| `POST` | `/admin/routine/{id}/activate` | HOD, SA | Activate + generate instances |
| `GET` | `/admin/routines` | HOD, SA | Revision list |
| `GET/POST` | `/admin/semesters` | SA | Semester CRUD |
| `GET/POST/DELETE` | `/admin/holidays` | HOD, SA | Calendar |
| `GET/POST` | `/admin/users` | SA | User management |
| `GET/PUT` | `/admin/settings` | HOD, SA | Threshold config |
| `GET` | `/admin/audit` | HOD, SA | `?entity_type=&entity_id=&actor=` |
| `POST` | `/admin/instances/generate` | SA | Re-run generation (idempotent) |

```jsonc
// POST /admin/routine/ingest   (multipart: file, department, semester, version?)
// 200 — IngestionReport from open-routine, unchanged
{ "department": "cse", "version": "V5", "routine_id": 7,
  "cells_read": 1240, "sessions_created": 1180,
  "days_covered": { "Saturday": 196, "Sunday": 201, "...": 0 },
  "reserved": 44, "skipped": 16,
  "skipped_sample": [ { "page": 2, "day": "Monday", "time_slot": "01:00-02:30",
                        "room": "KT-410", "text": "CSE???(70_A" } ] }
```

Ingest does **not** activate. Review, then activate — that is AC-01's verification step.

```jsonc
// POST /admin/routine/7/activate
{ "semester_id": 1 }
// 200
{ "routine_id": 7, "is_active": true, "instances_generated": 7840,
  "instances_skipped_holidays": 96 }
```

## 10. Errors

```jsonc
{ "detail": "Human-readable message",
  "code": "CONFLICT_DETECTED",
  "context": { "conflicts": [ ... ] } }
```

| Status | When |
|---|---|
| `400` | Validation failed (e.g. `LATE` without `arrival_time`) |
| `401` | Missing or expired token |
| `403` | Role not permitted, or teacher requesting another teacher's data |
| `404` | Not found |
| `409` | Conflict detected, or check window closed |
| `422` | Pydantic schema violation |

## 11. Build order dependency

```
auth ──> checking ──> dashboard ──> makeup ──> approvals ──> reports
  │                                                              │
  └──────────────> admin (ingest, activate) ─────────────────────┘
```

`/auth` and `/admin/routine/*` unblock everything else — build them first.
