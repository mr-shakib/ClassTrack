# ClassTrack — API Contract

Base: `/api/v1` · Auth: JWT in an httpOnly cookie · All timestamps ISO-8601, `Asia/Dhaka`.

Roles: `SUPER_ADMIN` (SA) · `HOD` · `ASSOCIATE_HEAD` · `COORDINATION_OFFICER` (CO) · `COMMITTEE` (C) · `STAFF` (ST) · `TEACHER` (T)

`HOD` and `ASSOCIATE_HEAD` hold every `SUPER_ADMIN` permission, so wherever SA or HOD is
listed below, all three are included; SA remains only as a fallback login.

`COORDINATION_OFFICER` runs day-to-day monitoring: everything marked **MGR** below
(the dashboards, the routine, the calendar, staff coverage, rules, audit) plus checking
and correcting past checks. They see **no reports** and **cannot decide** reschedule
requests. `COMMITTEE` may check classes and correct past ones, nothing more.

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
Roles: ST, C, HOD, SA

Room-wise list for a date + slot. Defaults to **now**. Excludes approved-online makeups (BR-12);
includes physical makeups (BR-10).

Every caller gets **every floor** — staff are not limited to their assigned floors. The response
groups rooms into `floors` (`key`, `label`, `total`, `checked`, `is_mine`), with a staff member's
assigned floors first; each room carries its `zone_key`. `zones` lists the caller's assigned
floors (empty for non-staff). Assigned floors still decide who is responsible for an unreported
class (`/reports/unreported`); they never hide a class.

```
?date=2026-09-13&slot=10:00-11:30     both optional
```

```jsonc
{
  "date": "2026-09-13",
  "time_slot": "10:00-11:30",
  "slot_state": "ONGOING",          // UPCOMING | ONGOING | CLOSED
  "window_closes_at": "2026-09-14T00:00:00+06:00", // end of the day: reports stay open until then
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
Roles: ST, C, HOD, SA — **idempotent**, upserts on `instance_id`.

Staff may submit any time from the class's start until the end of that day. After the day (or
before the class starts) only C, HOD and SA may submit; this is audited as `check_overridden`,
and `reason` is optional.

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
| `POST` | `/instances/{id}/cancel` | MGR | Cancel with reason |

`TEACHER` callers are force-scoped to their own `teacher_initial` — the filter is applied
server-side regardless of query parameters.

Every instance carries `rescheduled_from` (on a makeup: the missed class it recovers) and
`rescheduled_to` (on a missed class: the latest non-rejected request), each
`{ date, time_slot, room, instance_id, mode, status }` or `null`. Room rows on the checking
screen and dashboard rows carry `rescheduled_from` too, so a makeup can be marked apart.

```jsonc
// POST /instances/1042/respond
{ "response": "CONFIRMED", "note": null }   // CONFIRMED | DISPUTED
```
A `DISPUTED` response notifies HoD and flags the record for review. It does **not** change
the stored status — the original monitoring record survives (source SRS §9.1).

## 4. Live dashboard

### `GET /dashboard/day?date=`
Roles: MGR. Every class on one day with its `status`, its report `outcome`, floor, check,
and reschedule links. The screen filters by teacher, floor, slot and outcome client-side.

### `GET /checking/search?teacher=&from=&to=`
Roles: ST, C, MGR. A teacher's checkable classes over a range (default: the last 14 days,
at most six months), newest first, as room rows with their own `date`, `time_slot` and
`slot_state`. For finding a past class to correct.

### `GET /dashboard/live`
Roles: MGR. Frontend polls every 30s.

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
| `POST` | `/makeup` | T, HOD, SA | Reschedule a missed class |
| `GET` | `/makeup` | scoped | List; teachers see their own |
| `POST` | `/makeup/{id}/complete` | T (own), HOD, SA | Mark done after the class ends; `{ "drive_link": "https://..." }` required for `ONLINE` |

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

Conflict types: `TEACHER` · `ROOM` · `SECTION` · `HOLIDAY` · `SLOT`.

`check-conflict` takes `start_time` in place of `time_slot` too, and the form uses it to
validate an online class as the teacher picks the time. A period off the clock is matched by
**overlap** against every class on the day rather than by slot equality, because it is not a
cell and really can half-cover one; each conflict names the clashing class at *its* own time.
A class that merely touches another's edge — starting exactly as it ends — does not clash.

```jsonc
// POST /makeup
{ "original_instance_id": 1042, "mode": "PHYSICAL",
  "date": "2026-09-20", "time_slot": "02:30-04:00",
  "room": "KT-305", "reason": "Was on official duty" }

// POST /makeup — online, at a time off the clock
{ "original_instance_id": 1042, "mode": "ONLINE",
  "date": "2026-09-25", "start_time": "19:30" }
```

Send **either** `time_slot` (a routine slot) **or** `start_time`, never both; `422`
otherwise. `start_time` is a 24-hour `HH:MM` and is `ONLINE` only — a class in a room has to
sit in a cell, because a cell is what the staff screen walks. The class runs 90 minutes from
that time, on any day at any hour, and is stored with a plain `"19:30-21:00"` time slot. It
must finish before midnight, so the latest start is `22:30`.

An `ONLINE` request may include an optional `drive_link` (a full `http(s)://` address; `422`
otherwise). The HoD or Associate Head sees it in `/approvals/pending`, and it counts when the
makeup is later marked done. It is ignored for `PHYSICAL`.

The original must be `MISSED`, or unresolved with a `TEACHER_NOT_FOUND` check — a teacher
can ask as soon as staff report them absent, without waiting for the missed threshold.
`GET /instances?needs_reschedule=true` lists exactly those classes.

| Mode | When | Makeup starts | Original becomes | Decision |
|---|---|---|---|---|
| `PHYSICAL` | A routine slot | `SCHEDULED`, with its `is_makeup=1` instance already created | `MAKEUP_SCHEDULED` | None. An empty room is the whole decision, so the class is booked on the spot; the teacher and the HoD are told it happened. |
| `ONLINE` | A routine slot, or any time off the clock | `PENDING`, with no instance | `ONLINE_PENDING` | The HoD is notified and decides (BR-11). |

A booked room is taken from that moment: its instance occupies the cell, so
`free-rooms` drops it and `check-conflict` reports `ROOM` against it for everyone else.

`409` with the conflict report if validation fails; `422` if the slot has already started.
v1 does not accept an override.

The teacher is notified when staff record `TEACHER_NOT_FOUND` or `LATE` (`CLASS_REPORTED`),
and again when the sweep marks the class `MISSED` (`MISSED_CLASS`).

## 6. Reschedule approvals

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/approvals/pending` | HOD, SA | Queue of pending requests |
| `POST` | `/approvals/{makeup_id}/decide` | HOD, SA | Approve or reject |

```jsonc
{ "decision": "APPROVE", "note": "Approved for this week only" }
```

Only `ONLINE` requests reach this queue: an in-room reschedule books itself at
`POST /makeup`. Requests made before that rule can still be sitting here, so the
`PHYSICAL` column below stays valid for them.

Approval re-runs the conflict check; `409` if the cell has been taken since.

| Decision | `PHYSICAL` (legacy queue only) | `ONLINE` |
|---|---|---|
| `APPROVE` | Makeup → `SCHEDULED`, original → `MAKEUP_SCHEDULED`. An `is_makeup=1` instance is created and **appears in `/checking/rooms`** for that room and slot (BR-10). | Makeup → `APPROVED`, original → `ONLINE_APPROVED`. The instance is **excluded from `/checking/rooms`** (BR-12, AC-08). |
| `REJECT` | Makeup → `REJECTED`, original → back to `MISSED`, so the teacher reschedules again. | Makeup → `REJECTED`, original → `ONLINE_REJECTED`. |

The teacher is notified either way. The notification names the missed class (course, section,
original date, slot and room), the new date and slot, and whether it is in a room or online. It
links to `/teacher#makeup-{id}`, where the reschedule stays visible until marked done.

### Marking a makeup done

`POST /makeup/{id}/complete` moves an approved makeup (`SCHEDULED` or `APPROVED`) to `COMPLETED`.

- A teacher may complete only their own; HOD and SA may complete any.
- `422` until the rescheduled slot has **ended** (`ends_at` in `MakeupOut`).
- `ONLINE` needs a Drive link: one sent with the request is enough, or pass `drive_link` (a full
  `http(s)://` address, which replaces it). It is stored on the makeup and in the audit log.
  Ignored for `PHYSICAL`.
- `409` for a `PHYSICAL` makeup that staff reported `TEACHER_NOT_FOUND` at the new time.

Once an approved makeup's slot ends without completion, the sweep sends the teacher one
`MAKEUP_REMINDER`.

## 7. Reports

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/reports/overview` | HOD, SA | Any period (monthly, semester) — `?from=&to=&teacher=&floor=&course=&section=&slot=` |
| `GET` | `/reports/overview/pdf` | HOD, SA | The same, as a department summary PDF |
| `GET` | `/reports/daily` | HOD, SA | `?date=` — totals, floor-wise and slot-wise, makeups moved onto the day |
| `GET` | `/reports/teacher` | T (own), HOD, SA | `?teacher=&from=&to=` — per-course tallies and every class |
| `GET` | `/reports/teacher/pdf` | T (own), HOD, SA | The same, as a PDF listing every class |
| `GET` | `/reports/staff` | HOD, SA | Monitoring completion rate |

Every class falls in exactly one **outcome**: `CONDUCTED` (on time), `LATE`, `MISSED`,
`NOT_CHECKED`, `RESCHEDULED` (missed and moved), `CANCELLED` or `PENDING`. **Held** is
on time + late, including makeups. A recovered class counts once, on the day its makeup
was held. The **conduct rate** is held ÷ (held + missed): not-checked classes are a staff
gap and never lower it.

A course-section with fewer than `min_conducted_classes` held (a setting, default 18) is
`below_minimum`; a teacher with any such course is `flagged`.

`STAFF`, `COMMITTEE` and `COORDINATION_OFFICER` get 403 from every report.

```jsonc
// GET /reports/teacher?teacher=TCA&from=2026-09-01&to=2026-12-31
{ "teacher_initial": "TCA", "teacher_name": "Teacher A",
  "range": { "from": "2026-09-01", "to": "2026-12-31" }, "min_conducted": 18,
  "total_scheduled": 120, "conducted": 113, "on_time": 109, "late": 4, "missed": 3,
  "not_checked": 0, "rescheduled": 3, "conduct_rate": 97.4, "flagged": false,
  "courses": [ { "course_code": "CSE311(70_A)", "section": "70_A", "held": 24,
                 "below_minimum": false, "...": 0 } ],
  "classes": [ { "date": "2026-09-13", "time_slot": "10:00-11:30", "outcome": "RESCHEDULED",
                 "rescheduled_to": { "date": "2026-09-20", "time_slot": "04:00-05:30" } } ] }
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
| `POST` | `/admin/routine/ingest` | MGR | Upload PDF (multipart) → report |
| `GET` | `/admin/routine/{id}/review` | MGR | Parsed sessions + conflicts + skipped cells |
| `POST` | `/admin/routine/{id}/activate` | MGR | Activate + generate instances |
| `GET` | `/admin/routines` | MGR | Revision list |
| `GET` | `/admin/semesters` | MGR | Semester list |
| `POST` | `/admin/semesters` | HOD, SA | Create a semester |
| `GET/POST/DELETE` | `/admin/holidays` | MGR | Calendar |
| `GET/POST` | `/admin/users` | HOD, SA | User management |
| `PATCH` | `/admin/users/{id}` | HOD, SA | Rename, change role, (de)activate, reset password |
| `GET/PUT` | `/admin/settings` | MGR | Missed threshold, minimum classes per course |
| `GET` | `/admin/audit` | MGR | `?entity_type=&entity_id=&actor=` |
| `POST` | `/admin/instances/generate` | HOD, SA | Re-run generation (idempotent) |

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
| `409` | Conflict detected, or reporting closed for that day |
| `422` | Pydantic schema violation |

## 11. Build order dependency

```
auth ──> checking ──> dashboard ──> makeup ──> approvals ──> reports
  │                                                              │
  └──────────────> admin (ingest, activate) ─────────────────────┘
```

`/auth` and `/admin/routine/*` unblock everything else — build them first.
