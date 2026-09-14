# ClassTrack — Data Model

SQLAlchemy 2.0 declarative, async. Tables marked **(vendored)** come from `open-routine`
unchanged — see [ARCHITECTURE.md §4](ARCHITECTURE.md).

---

## 1. Entity overview

```
routine (V) ──1:N──> class_session (V) ──1:N──> class_instance ──0:1──> check_record
                                                      │
semester ─────────────────────────────────────────────┤
holiday  (blocks generation)                          ├──0:N──> makeup_class
teacher (V) <──0:1── user                             │              │
                      │                               │              └──> class_instance
                      ├──> check_record.checked_by    │                   (is_makeup=1)
                      ├──> notification               │
                      └──> audit_log.actor <──────────┘
setting (k/v)
```

## 2. Vendored tables

### `routine` (V)
`id · department · version · semester · source_filename · is_active · published_at · session_count`

One published revision. New revisions ingest into a new row and only become `is_active` once
the whole import succeeds — clients never observe a half-imported routine.

### `class_session` (V) — the template
`id · routine_id · day · time_slot · room · room_type · course_code · course_title · teacher ·
batch · section · is_lab · is_optional · start_min · end_min`

One cell of the routine grid. **`time_slot` is the occupancy key** and is compared with `==`.
`start_min`/`end_min` are derived, for display and sorting only.

### `teacher` (V)
`id · initial · name · designation · department · office_room · image_url`

Keyed on the uppercase initial as it appears in the routine (e.g. `"SRH"`).

## 3. New tables

### 3.1 `user`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `email` | str(255) | unique, not null |
| `password_hash` | str(255) | bcrypt |
| `full_name` | str(255) | |
| `role` | enum | `SUPER_ADMIN` · `HOD` · `ASSOCIATE_HEAD` · `COMMITTEE` · `STAFF` · `TEACHER` |
| `teacher_initial` | str(16) FK→`teacher.initial` | nullable; set for `TEACHER` role |
| `is_active` | bool | default true |

```
ix_user_email (unique) · ix_user_role · ix_user_teacher_initial
```

> `teacher_initial` is the join between an account and its routine rows. A `TEACHER` user
> without it sees an empty schedule — validate on user creation.

### 3.2 `semester`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | str(64) | `"Fall 2026"` |
| `department` | str(16) | default `"cse"` |
| `routine_id` | int FK→`routine.id` | active routine for this semester |
| `start_date` | date | |
| `end_date` | date | |
| `is_active` | bool | exactly one true per department |

### 3.3 `holiday`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `date` | date | unique with `semester_id` |
| `title` | str(255) | `"Victory Day"` |
| `kind` | enum | `HOLIDAY` · `EXAM` · `CLOSED` · `SPECIAL` |
| `semester_id` | int FK | |

`kind ∈ {HOLIDAY, EXAM, CLOSED}` blocks instance generation. `SPECIAL` does not.

### 3.4 `class_instance` — the occurrence ⭐

The central table. One row per class per date.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `session_id` | int FK→`class_session.id` | nullable — null for makeup instances |
| `semester_id` | int FK→`semester.id` | |
| `date` | date | not null |
| `day` | str(16) | denormalised |
| `time_slot` | str(32) | **occupancy key** |
| `start_min`, `end_min` | int | display/sort only |
| `room` | str(64) | denormalised |
| `room_type` | str(32) | |
| `course_code` | str(64) | denormalised |
| `section` | str(32) | denormalised |
| `batch` | str(32) | |
| `teacher_initial` | str(16) | denormalised |
| `status` | enum `ClassStatus` | null ⇒ unresolved, status derived from clock |
| `is_makeup` | bool | default false |
| `makeup_id` | int FK→`makeup_class.id` | set when `is_makeup` |
| `teacher_response` | enum | `CONFIRMED` · `DISPUTED`, nullable |
| `response_note` | text | nullable |
| `resolved_at` | datetime | when a terminal status was written |

```
uq_instance_session_date (session_id, date)      ← makes generation idempotent
ix_instance_date_slot     (date, time_slot)      ← conflict detection
ix_instance_date_room     (date, time_slot, room)
ix_instance_teacher_date  (teacher_initial, date)
ix_instance_status_date   (status, date)         ← sweep + dashboard
ix_instance_section_date  (section, date, time_slot)
```

**`status` is nullable by design.** Null means "not yet resolved" — the API derives
`UPCOMING`/`ONGOING` from the clock. Only terminal statuses are persisted. The sweep selects
exactly `status IS NULL AND date <= today AND end_of_day(date) <= now`, which is why it is
naturally idempotent.

```python
class ClassStatus(str, Enum):
    RUNNING = "RUNNING";                   LATE = "LATE"
    MISSED = "MISSED";                     NOT_CHECKED = "NOT_CHECKED"
    MAKEUP_SCHEDULED = "MAKEUP_SCHEDULED"; MAKEUP_COMPLETED = "MAKEUP_COMPLETED"
    ONLINE_PENDING = "ONLINE_PENDING";     ONLINE_APPROVED = "ONLINE_APPROVED"
    ONLINE_REJECTED = "ONLINE_REJECTED";   CANCELLED = "CANCELLED"
# UPCOMING and ONGOING are derived, never stored.
```

### 3.5 `check_record`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `instance_id` | int FK→`class_instance.id` | **unique** — one check per instance |
| `checked_by_id` | int FK→`user.id` | |
| `outcome` | enum | `RUNNING` · `LATE` · `TEACHER_NOT_FOUND` |
| `arrival_time` | time | required when `outcome=LATE` |
| `late_minutes` | int | computed, not submitted (BR-04) |
| `remark` | text | optional |
| `checked_at` | datetime | |

```
uq_check_instance (instance_id)   ← idempotency guarantee
ix_check_user_date (checked_by_id, checked_at)   ← staff performance report
```

The unique constraint is what makes re-submission safe under a flaky mobile connection:
the service upserts on `instance_id`, so a double-tap or a retry can never create two records.

`late_minutes` is computed server-side from `arrival_time − slot_start`; a client-supplied
value is ignored.

### 3.6 `makeup_class`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `original_instance_id` | int FK→`class_instance.id` | **not null** (BR-13) |
| `teacher_initial` | str(16) | |
| `mode` | enum | `PHYSICAL` · `ONLINE` |
| `date` | date | |
| `time_slot` | str(32) | must be a valid lattice slot |
| `room` | str(64) | null when `ONLINE` |
| `reason` | text | |
| `status` | enum | `SCHEDULED` · `PENDING` · `APPROVED` · `REJECTED` · `COMPLETED` |
| `decided_by_id` | int FK→`user.id` | nullable |
| `decision_note` | text | nullable |
| `decided_at` | datetime | nullable |
| `created_instance_id` | int FK→`class_instance.id` | the instance this makeup produced |
| `drive_link` | str(1024) | nullable; required to complete an `ONLINE` makeup |
| `completed_by_id` | int FK→`user.id` | nullable |
| `completed_at` | datetime | nullable |
| `reminder_sent_at` | datetime | nullable; the sweep's one "mark it done" reminder |

```
ix_makeup_status · ix_makeup_teacher · ix_makeup_original (original_instance_id)
```

`PHYSICAL` → status `SCHEDULED`, and a `class_instance` with `is_makeup=1` is created
immediately so it enters room-wise checking (BR-10).
`ONLINE` → status `PENDING`; the instance is created only on approval, and is excluded from
staff checking (BR-12).

### 3.7 `notification`

`id · user_id FK · kind · title · body · link · read_at (nullable) · created_at`

```
ix_notification_user_unread (user_id, read_at)
```

`kind ∈ {MISSED_CLASS, MAKEUP_REMINDER, ONLINE_DECISION, ONLINE_REQUEST, DISPUTE_RAISED}`

### 3.8 `audit_log` — append-only

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `actor_id` | int FK→`user.id` | nullable — null = system (sweep) |
| `entity_type` | str(32) | `"class_instance"`, `"makeup_class"`, … |
| `entity_id` | int | |
| `action` | str(64) | `"status_changed"`, `"check_submitted"`, … |
| `before` | JSON | nullable |
| `after` | JSON | nullable |
| `reason` | text | nullable |
| `created_at` | datetime | |

```
ix_audit_entity (entity_type, entity_id) · ix_audit_actor · ix_audit_created
```

> **No update, no delete.** `audit_service.record()` is the only writer, and it exposes no
> mutation path. The source SRS requires the original monitoring record to survive even when
> an admin later changes the final status — `before`/`after` carry that history.

### 3.9 `setting`

`key (PK, str(64)) · value (str(255)) · updated_by_id FK · updated_at`

| Key | Default | Meaning |
|---|---|---|
| `missed_threshold_minutes` | `30` | BR-05 threshold |
| `timezone` | `Asia/Dhaka` | all clock comparisons |
| `department` | `cse` | active department |

## 4. Invariants

| # | Invariant | Enforced by |
|---|---|---|
| I1 | One check per instance | `uq_check_instance` |
| I2 | Generation is idempotent | `uq_instance_session_date` |
| I3 | `MISSED` requires a `TEACHER_NOT_FOUND` check | `sweep.finalise()` branch |
| I4 | `NOT_CHECKED` requires no check record | `sweep.finalise()` branch |
| I5 | Every makeup references its original | `original_instance_id` NOT NULL |
| I6 | `late_minutes` is server-computed | `check_service.submit()` |
| I7 | Approved-online never appears in staff checking | staff query filter |
| I8 | Audit rows are never mutated | service exposes no update path |
| I9 | Terminal status is never recomputed | sweep selects `status IS NULL` |
| I10 | `time_slot` is always a canonical lattice label | `lattice.normalise_slot()` at every entry point |

## 5. Seed data

```
users:     admin@diu.edu (SUPER_ADMIN) · hod@diu.edu (HOD)
           associate@diu.edu (ASSOCIATE_HEAD) · committee@diu.edu (COMMITTEE)
           staff1@diu.edu (STAFF) · teacher initials from the faculty directory
teachers:  loaded from open-routine's teachers.json evidence file
routine:   ingested from the DIU routine PDF
semester:  "Fall 2026", start 2026-09-01, end 2026-12-31
holidays:  a handful of known dates
settings:  defaults above
```

`classtrack seed --demo` additionally back-dates a few instances with mixed statuses so the
dashboard and reports have content to show at demo time.
