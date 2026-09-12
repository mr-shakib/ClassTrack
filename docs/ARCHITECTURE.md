# ClassTrack — Architecture

Companion to [SRS.md](SRS.md). Describes structure, not schedule — see
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the build order.

---

## 1. Guiding principles

1. **Lightweight over complete.** One FastAPI process, one SQLite file, one Next.js app.
   No Redis, no Celery, no message broker, no external services.
2. **Reuse `open-routine`.** The hardest solved problem — turning a published DIU routine PDF
   into structured rows — is already solved. Vendor it, don't rewrite it.
3. **The lattice is load-bearing.** Fixed 6×6 grid, occupancy by slot-label equality.
   It makes conflict detection trivial. Protect it.
4. **Separate evidence from absence of evidence.** `MISSED` ≠ `NOT_CHECKED`, everywhere,
   at every layer.
5. **Leave seams, not implementations.** Deferred features get a named interface
   (`NotificationChannel`, `ConflictReport.overridable`) so v2 is additive, not a rewrite.

## 2. System context

```
┌──────────────┐   routine PDF    ┌──────────────────────────────────┐
│  HoD / Admin ├─────────────────>│                                  │
└──────────────┘                  │      ClassTrack Backend          │
┌──────────────┐   one-tap check  │        (FastAPI, :8000)          │
│ Office Staff ├─────────────────>│                                  │
└──────────────┘   (mobile)       │  ┌────────────────────────────┐  │
┌──────────────┐   confirm /      │  │ vendored: open_routine     │  │
│   Teacher    ├─  makeup ───────>│  │ ingestion pipeline         │  │
└──────────────┘                  │  └────────────────────────────┘  │
                                  │  ┌────────────────────────────┐  │
        ┌──────────────────┐      │  │ in-process sweep loop      │  │
        │ Next.js frontend │<─────┤  │ (asyncio, 60s)             │  │
        │      (:3000)     │ JSON │  └────────────────────────────┘  │
        └──────────────────┘      └───────────────┬──────────────────┘
                                                  │
                                         ┌────────▼────────┐
                                         │ SQLite (/data)  │
                                         └─────────────────┘
```

Caddy terminates TLS and proxies both apps in production.

## 3. Why this stack

| Choice | Reason |
|---|---|
| **FastAPI** | `open-routine` is already FastAPI + SQLAlchemy 2 async + Alembic. Vendoring is a file copy. |
| **SQLite** | ~8,000 instances/semester and a single-department read-mostly workload. The `.db` file is the backup. Swap to Postgres by changing one env var — `asyncpg` is already an optional dep upstream. |
| **In-process asyncio sweep** | The only recurring job is a 60-second status finaliser. Celery + Redis would be more infrastructure than application. |
| **Next.js 15 App Router** | Server components for dashboards, client components for the checking UI. One deployable. |
| **Tailwind** | Large tap targets and responsive room cards without a component-library dependency. |

## 4. Reuse map — what comes from `open-routine`

Source: `/home/mr-nacht/Workspace/Personal/projects/open-routine` @ commit **`bcd2b8d`** (2026-08-30)

865 lines of proven code, vendored as five files.

### 4.1 Vendored verbatim (copy into `backend/src/classtrack/routine/`)

| File | What it does | Change |
|---|---|---|
| `ingestion/lattice.py` (138 ln) | DAYS/SLOTS constants, day+slot normalisation, `slot_bounds()` | none |
| `ingestion/pdf_reader.py` (230 ln) | pdfplumber grid walk → `RawCell` | none |
| `ingestion/cell_parser.py` (168 ln) | `"CSE414(62_E1)"` → course/batch/section/lab/optional | none |
| `ingestion/normalizer.py` (94 ln) | Room + initial cleanup, `"KT-503\n(COM LAB)"` → `("KT-503","Computer Lab")` | none |
| `ingestion/pipeline.py` (235 ln) | Full ingest + atomic activation swap | none |
| `models/routine.py` | `Routine`, `ClassSession` | none |
| `models/teacher.py` | `Teacher` | + `user_id` backref |

### 4.2 Adapted

| From | To |
|---|---|
| `core/config.py` | Same shape, prefix `CLASSTRACK_`, plus `jwt_secret`, `missed_threshold_minutes` |
| `db/base.py`, `db/session.py` | As-is |
| `Dockerfile`, `docker-entrypoint.sh` | Renamed module paths |
| `deploy/compose.prod.yaml`, `deploy/Caddyfile` | + `web` service for Next.js |

### 4.3 New to ClassTrack

Auth · users · semester · calendar · class instances · checking · status engine · sweep ·
makeup · approvals · notifications · reports · audit.

> **Vendoring, not importing.** `open-routine` is a separate repo with its own release cycle.
> Copying five stable files avoids cross-repo coupling during a 2-day build. Record the source
> commit in `backend/src/classtrack/routine/VENDORED.md` so upstream fixes can be pulled in.

## 5. Backend structure

```
backend/
├── pyproject.toml
├── alembic.ini
├── migrations/
├── Dockerfile
└── src/classtrack/
    ├── main.py                  # app factory, CORS, router mount, sweep startup
    ├── cli.py                   # seed, ingest, generate-instances
    ├── core/
    │   ├── config.py            # Settings (CLASSTRACK_ env prefix)
    │   ├── security.py          # bcrypt, JWT encode/decode
    │   └── errors.py
    ├── db/
    │   ├── base.py              # Base, TimestampMixin
    │   └── session.py
    ├── routine/                 # ◄── VENDORED from open-routine
    │   ├── VENDORED.md
    │   ├── lattice.py
    │   ├── pdf_reader.py
    │   ├── cell_parser.py
    │   ├── normalizer.py
    │   └── pipeline.py
    ├── models/
    │   ├── routine.py           # Routine, ClassSession   (vendored)
    │   ├── teacher.py           # Teacher                 (vendored)
    │   ├── user.py              # User, Role
    │   ├── academic.py          # Semester, Holiday
    │   ├── instance.py          # ClassInstance, ClassStatus
    │   ├── check.py             # CheckRecord, CheckOutcome
    │   ├── makeup.py            # MakeupClass, MakeupMode, MakeupStatus
    │   ├── notification.py      # Notification
    │   ├── audit.py             # AuditLog
    │   └── setting.py           # Setting
    ├── schemas/                 # Pydantic v2 request/response models
    ├── services/
    │   ├── auth_service.py
    │   ├── instance_service.py  # generation (BR-01)
    │   ├── check_service.py     # submission + late calc (BR-03/04)
    │   ├── status_engine.py     # derived status + transitions
    │   ├── sweep.py             # MISSED / NOT_CHECKED finaliser (BR-05/06)
    │   ├── conflict_service.py  # teacher/room/section/holiday (BR-14)
    │   ├── makeup_service.py    # BR-09..BR-13
    │   ├── notification_service.py
    │   ├── report_service.py
    │   └── audit_service.py     # append-only (BR-15)
    └── api/
        ├── deps.py              # get_session, current_user, require_role
        └── v1/routes/
            ├── auth.py      instances.py   checks.py
            ├── makeup.py    approvals.py   reports.py
            ├── admin.py     notifications.py  health.py
```

### 5.1 Layering rule

```
routes  →  services  →  models
   ↑          ↑
 schemas   (never import routes)
```

Routes do auth + validation + serialisation. **All business logic lives in services.**
The sweep job and the CLI call services directly — so no rule may live in a route handler.

## 6. Data model

Full DDL and field notes in [DATA_MODEL.md](DATA_MODEL.md). Shape:

```
Routine ──1:N──> ClassSession ──1:N──> ClassInstance ──1:1──> CheckRecord
   │                (template)            (one per date)
   │                                          │
Semester ─────────────────────────────────────┤
   │                                          │
Holiday (blocks generation)                   ├──1:N──> MakeupClass
                                              │            │
User ──1:1──> Teacher                         │            └──> ClassInstance (is_makeup)
  │                                           │
  ├──> CheckRecord.checked_by                 └──> AuditLog
  ├──> Notification
  └──> AuditLog.actor
```

**`ClassSession` is the template; `ClassInstance` is the occurrence.** A session says
"CSE311 is in KT-305 every Sunday at 10:00-11:30". An instance says "on 2026-09-13, that class
had status X, checked by Y at Z". Everything monitored hangs off the instance.

## 7. The status engine

Status has two sources, deliberately kept apart.

### 7.1 Derived (never stored)
While an instance is unresolved and the check window is open, status is computed from the clock:

```python
if now < slot_start:              UPCOMING
elif now <= slot_start + window:  ONGOING
```

Nothing to persist, nothing to get stale.

### 7.2 Stored (terminal)
Written once by a check, a sweep, or a workflow action. Never recomputed.

```
RUNNING  LATE  MISSED  NOT_CHECKED  MAKEUP_SCHEDULED  MAKEUP_COMPLETED
ONLINE_PENDING  ONLINE_APPROVED  ONLINE_REJECTED  CANCELLED
```

### 7.3 The sweep loop

A single asyncio task, started on app startup, every 60 seconds:

```python
async def sweep_once(session, now):
    window = settings.missed_threshold_minutes
    for inst in unresolved_instances_past(now, window):
        if inst.check and inst.check.outcome == TEACHER_NOT_FOUND:
            inst.status = MISSED          # BR-05: positive evidence
            notify_teacher(inst)
        elif inst.check is None:
            inst.status = NOT_CHECKED     # BR-06: no evidence ≠ absence
        # RUNNING / LATE already terminal — untouched
```

Properties that matter:

- **Idempotent** — only selects instances with a non-terminal status, so a re-run is a no-op.
- **Crash-safe** — restart re-sweeps by wall-clock time; nothing depends on the loop having run.
- **Timezone-pinned** — all comparisons in `Asia/Dhaka`. Stored timestamps are UTC.

> Deferred-but-seamed: for multi-process deployment, replace the loop with the same
> `sweep_once()` called from an external scheduler. The function is already pure w.r.t. `now`.

## 8. Instance generation (BR-01)

```python
def generate(semester, routine):
    holidays = set(holiday_dates(semester))
    for date in daterange(semester.start, semester.end):
        day = weekday_name(date)
        if day == "Friday" or date in holidays:
            continue
        for sess in sessions_for_day(routine, day):
            upsert(ClassInstance, key=(sess.id, date))   # idempotent
```

Denormalised onto each instance: `room`, `teacher_initial`, `course_code`, `section`,
`time_slot`, `start_min`, `end_min`. This keeps the staff screen and dashboard **single-table
index scans** — no joins on the hot path — and preserves history if the routine is later
revised.

Re-running generation after a routine revision is safe: the unique key `(session_id, date)`
makes it an upsert, and existing instances keep their status and check records.

## 9. Conflict detection (BR-14)

Because slots are atomic, this is three indexed equality lookups — not interval math:

```python
def check(date, time_slot, room, teacher, section) -> ConflictReport:
    q = instances_at(date, time_slot)          # ix_instance_date_slot
    return ConflictReport(
        teacher = q.any(teacher_initial == teacher),
        room    = q.any(room == room),
        section = q.any(section == section),
        holiday = date in holidays,
        overridable = True,                     # v2 seam
    )
```

## 10. Authentication

- **Password** — bcrypt via `passlib`.
- **Token** — JWT (HS256), 12-hour expiry, carries `sub` (user id) and `role`.
- **Transport** — httpOnly, SameSite=Lax cookie set by the API.
- **Enforcement** — `require_role(*roles)` dependency on every protected route.
  Frontend role gating is **cosmetic only**; the API is the real boundary.

```python
CurrentUser = Annotated[User, Depends(get_current_user)]
StaffOnly   = Annotated[User, Depends(require_role(STAFF, HOD, SUPER_ADMIN))]
```

## 11. Frontend structure

```
web/
├── app/
│   ├── layout.tsx  page.tsx  login/
│   ├── staff/page.tsx           # room-wise checking (client, mobile-first)
│   ├── dashboard/page.tsx       # HoD live monitor (30s poll)
│   ├── teacher/
│   │   ├── page.tsx             # today, missed-needing-action, makeups
│   │   └── makeup/page.tsx      # request form + live conflict feedback
│   ├── approvals/page.tsx       # HoD online-makeup queue
│   ├── reports/page.tsx         # daily + teacher-wise
│   └── admin/
│       ├── routine/page.tsx     # upload → review → activate
│       ├── calendar/page.tsx    # holidays
│       ├── settings/page.tsx    # threshold
│       └── audit/page.tsx
├── components/
│   ├── RoomCard.tsx             # ◄── the most important component
│   ├── StatusBadge.tsx  SummaryCard.tsx  DataTable.tsx  ConflictNotice.tsx
├── lib/
│   ├── api.ts                   # typed fetch wrapper, credentials: include
│   ├── auth.ts                  # session context
│   └── types.ts                 # mirrors backend schemas
└── middleware.ts                # route-level role redirect
```

### 11.1 `RoomCard` — the one-tap requirement

The checking screen is the only interface used while walking between classrooms. It sets the
usability bar for the whole system (AC-02).

```
┌────────────────────────────────────┐
│ KT-305              10:00 – 11:30  │
│ CSE311 · 70-A                      │
│ Teacher A (TCA)                    │
│ ┌─────────┬─────────┬────────────┐ │
│ │ Running │  Late   │ Not Found  │ │   ← ≥44px tap targets
│ └─────────┴─────────┴────────────┘ │
│ + remark                           │   ← secondary, collapsed
└────────────────────────────────────┘
```

- Optimistic update on tap; revert + toast on failure.
- **Running** = one tap, no confirmation dialog.
- **Late** expands an inline time field pre-filled with now — still one extra tap.
- Card collapses to a status badge once submitted; re-tap to amend.

## 12. Deployment

Adapted from `open-routine/deploy/`. Caddy fetches and renews Let's Encrypt certificates
itself, so there is no certificate to manage.

```yaml
services:
  api:                        # FastAPI, expose 8000, volume /data
  web:                        # Next.js standalone, expose 3000
  caddy:                      # :80 :443 → route /api/* to api, /* to web
volumes: [classtrack-data, caddy-data, caddy-config]
```

```
classtrack.example.edu {
    handle /api/* { reverse_proxy api:8000 }
    handle       { reverse_proxy web:3000 }
}
```

**Backup** — the SQLite file on the `classtrack-data` volume is the entire database.
`docker compose cp api:/data/classtrack.db ./backup-$(date +%F).db` is a complete backup;
a nightly cron entry satisfies the source SRS backup requirement for v1.

## 13. Decision record

| # | Decision | Rationale | Reversal cost |
|---|---|---|---|
| D1 | Vendor `open-routine` rather than import | No cross-repo coupling in a 2-day build | Low — 5 files |
| D2 | SQLite over Postgres | Single department, read-mostly, file = backup | Low — one env var |
| D3 | In-process asyncio sweep | Only one recurring job; avoids Redis + Celery | Low — `sweep_once()` is pure |
| D4 | Derived status for UPCOMING/ONGOING | Nothing stale to reconcile | Low |
| D5 | Denormalise room/teacher/course onto instance | Hot paths stay single-table; preserves history | Medium |
| D6 | Slot-label equality, never interval math | Inherited lattice invariant | **High — do not reverse** |
| D7 | JWT in httpOnly cookie | Simplest correct option for same-site deploy | Low |
| D8 | Block conflicts, no override | Override needs audit + reason UI; deferred | Low — flag exists |
| D9 | Read-only routine review in v1 | Editable grid is ~2 days alone; re-ingest covers correction | Medium |

## 14. Extension points for v2

| Deferred feature | Seam already in place |
|---|---|
| Email / SMS | `NotificationChannel` protocol; add `EmailChannel` beside `InAppChannel` |
| Editable verification grid | `IngestionReport.skipped_cells` already carries page/day/slot/room/text |
| Conflict override | `ConflictReport.overridable` + `AuditLog.reason` |
| Monthly/semester/yearly reports | `report_service` aggregates already take a date range |
| Staff room assignment | Add `User.assigned_rooms`; staff query filters on it |
| Multi-department | `department` already on `Routine`; add to `User` + scope queries |
| Postgres | `CLASSTRACK_DATABASE_URL` + `asyncpg` |
| Multi-process sweep | Call `sweep_once()` from an external scheduler |
| PWA / offline checking | Queue check submissions in IndexedDB; the API is already idempotent |
