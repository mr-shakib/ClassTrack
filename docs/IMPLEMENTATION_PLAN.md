# ClassTrack — Implementation Plan (2 days)

Track progress in [PROGRESS.md](PROGRESS.md). Contract is frozen in [API.md](API.md).

---

## 0. Reality check

A production build of this SRS is roughly **106 engineer-days**. Two days buys a
**demo-grade vertical slice**: every module reachable end-to-end, shallow depth, seams left
for v2. This plan is written to that scope and nothing more.

Three things make 2 days feasible at all:

1. **PDF ingestion is already solved** — `open-routine` vendors in as five stable files.
   This was the single biggest risk item; it is now a copy.
2. **The lattice kills the hard logic** — no interval arithmetic, no overlap detection,
   no scheduling solver. Conflicts are three indexed lookups.
3. **No infrastructure** — SQLite file, in-process asyncio loop, two containers.

Assumes ~10 focused hours per day, AI-assisted, single developer.

## 1. Schedule

| Block | Hours | Focus |
|---|---|---|
| **Day 1 AM** | 0–5 | Skeleton, vendor, models, migrations, auth, ingest |
| **Day 1 PM** | 5–10 | Instances, checking, sweep, makeup, approvals, reports |
| **Day 2 AM** | 10–15 | Next.js scaffold, login, staff checking, dashboard |
| **Day 2 PM** | 15–20 | Teacher, makeup, approvals, reports, admin, deploy |

Backend is finished before frontend starts. With two people, split at hour 5 — one continues
backend, one starts the frontend against the frozen [API.md](API.md) contract with a mock.

---

## Day 1 — Backend

### Block 1 · Skeleton + vendor (hours 0–1.5)

- [ ] `git init`; create `backend/` and `web/`
- [ ] `pyproject.toml` — copy from open-routine, rename to `classtrack`, add:
      `passlib[bcrypt]`, `python-jose[cryptography]`, `python-dateutil`
- [ ] Copy `db/base.py`, `db/session.py`, `core/errors.py`, `core/logging.py`
- [ ] Copy `alembic.ini`, `migrations/env.py`, `Dockerfile`, `docker-entrypoint.sh`
- [ ] **Vendor** into `src/classtrack/routine/`:
      `lattice.py` · `pdf_reader.py` · `cell_parser.py` · `normalizer.py` · `pipeline.py`
- [ ] Write `routine/VENDORED.md` — record the source commit hash
- [ ] Adapt `core/config.py` → prefix `CLASSTRACK_`, add `jwt_secret`,
      `missed_threshold_minutes=30`, `check_window_minutes=30`, `timezone="Asia/Dhaka"`
- [ ] `main.py` app factory + `/health` responding

> Fix vendored imports with one pass: `open_routine.` → `classtrack.`

**Done when:** `uvicorn classtrack.main:app` serves `/api/v1/health`.

### Block 2 · Models + migration (hours 1.5–3)

- [ ] Copy `models/routine.py`, `models/teacher.py` verbatim
- [ ] Write `user.py` `academic.py` `instance.py` `check.py` `makeup.py`
      `notification.py` `audit.py` `setting.py` — per [DATA_MODEL.md](DATA_MODEL.md)
- [ ] Declare **every index** listed there now — retrofitting them later means a second migration
- [ ] `alembic revision --autogenerate -m "initial"` → inspect → `upgrade head`
- [ ] `cli.py seed` — users, settings, a semester

> `class_instance.status` is **nullable**. Null = unresolved. Getting this wrong forces a
> rewrite of the sweep and both dashboards.

**Done when:** `classtrack seed` populates a fresh DB and the schema matches DATA_MODEL.md.

### Block 3 · Auth + RBAC (hours 3–4)

- [ ] `core/security.py` — bcrypt hash/verify, JWT encode/decode
- [ ] `auth_service.py` — authenticate, issue token
- [ ] `api/deps.py` — `get_session`, `get_current_user`, `require_role(*roles)`
- [ ] Routes: `POST /auth/login` · `POST /auth/logout` · `GET /auth/me`
- [ ] httpOnly cookie, SameSite=Lax, 12h expiry

**Done when:** each seeded role logs in and `require_role` returns 403 correctly.

### Block 4 · Routine ingest + activation (hours 4–5)

- [ ] `POST /admin/routine/ingest` — multipart → `pipeline.ingest_pdf(activate=False)`
- [ ] `GET /admin/routine/{id}/review` — sessions + skipped cells + conflicts
- [ ] Conflict scan over parsed sessions: duplicate `(day, slot, room)`,
      teacher double-booked, missing teacher/room
- [ ] `POST /admin/routine/{id}/activate` — activate + trigger generation
- [ ] Semester + holiday CRUD

**Done when:** a real DIU routine PDF ingests and the review endpoint lists parsed sessions.

### Block 5 · Instance generation (hours 5–6)

- [ ] `instance_service.generate(semester_id)` — per [ARCHITECTURE.md §8](ARCHITECTURE.md)
- [ ] Skip Fridays and blocking holidays
- [ ] Denormalise room/teacher/course/section/slot/start_min/end_min onto each row
- [ ] Upsert on `(session_id, date)` — verify a second run creates zero rows
- [ ] `POST /admin/instances/generate`
- [ ] `GET /instances` with filters + teacher scoping

**Done when:** activation produces ~7–8k instances, and re-running changes nothing.

### Block 6 · Checking + status engine + sweep (hours 6–8) ⭐

The correctness core. Budget the most care here.

- [ ] `status_engine.derive(instance, now)` → `UPCOMING` / `ONGOING` / stored status
- [ ] `GET /checking/rooms` — group by room for a date+slot, default now
      - exclude `ONLINE_APPROVED` (BR-12) · include `is_makeup` physical (BR-10)
- [ ] `check_service.submit()` — upsert on `instance_id`, compute `late_minutes` server-side
- [ ] `POST /checking/{instance_id}`
- [ ] `sweep.sweep_once(session, now)`:
      - `TEACHER_NOT_FOUND` + threshold elapsed → `MISSED` + notify teacher (BR-05)
      - no check + window closed → `NOT_CHECKED` (BR-06)
      - selects only `status IS NULL` → idempotent
- [ ] Start the asyncio loop on app startup, 60s interval
- [ ] `GET /dashboard/live` — summary + rows + attention counts

**Tests to actually write (the only ones worth the time):**
- [ ] `TEACHER_NOT_FOUND` before threshold → still unresolved; after → `MISSED`
- [ ] No check + window closed → `NOT_CHECKED`, **never** `MISSED`
- [ ] `RUNNING` / `LATE` untouched by the sweep
- [ ] Double submit → one `check_record`
- [ ] Late calc: 10:00 slot + 10:08 arrival → 8

**Done when:** the four sweep tests pass. Do not proceed until they do.

### Block 7 · Makeup + approvals + reports (hours 8–10)

- [ ] `conflict_service.check()` — teacher/room/section/holiday on `(date, time_slot)`
- [ ] `POST /makeup/check-conflict`
- [ ] `makeup_service.create()`:
      - `PHYSICAL` → `SCHEDULED` + create instance `is_makeup=1`; original → `MAKEUP_SCHEDULED`
      - `ONLINE` → `PENDING`, notify HoD; original → `ONLINE_PENDING`
- [ ] `POST /instances/{id}/respond` — confirm / dispute (BR-08)
- [ ] `GET /approvals/pending` · `POST /approvals/{id}/decide`
      - approve → instance created, excluded from checking (AC-08)
- [ ] `GET /reports/daily` · `/reports/teacher` · `/reports/staff`
- [ ] `notification_service` — `NotificationChannel` protocol + `InAppChannel`
- [ ] `audit_service.record()` wired into every status change (BR-15)
- [ ] `GET /notifications`, `/admin/audit`

**Done when:** the full missed → confirm → makeup → approve → appears-in-checking loop works via
`curl`/Swagger. **Verify AC-08 explicitly.**

---

## Day 2 — Frontend + deployment

### Block 8 · Scaffold + auth (hours 10–11.5)

- [ ] `npx create-next-app@latest web --ts --tailwind --app --eslint`
- [ ] `lib/types.ts` — mirror API.md exactly
- [ ] `lib/api.ts` — typed fetch, `credentials: "include"`, error unwrapping
- [ ] `lib/auth.ts` — session context from `/auth/me`
- [ ] `/login` page
- [ ] `middleware.ts` — role-based redirect to each role's home
- [ ] `AppShell` — responsive nav, role-aware links
- [ ] `StatusBadge` — one colour map for all 12 statuses, used everywhere

**Done when:** each role logs in and lands on the right page.

### Block 9 · Staff checking (hours 11.5–13) ⭐

The interface that decides whether the system gets adopted. Build it on a 360px viewport.

- [ ] `/staff` — poll `/checking/rooms` every 30s
- [ ] `RoomCard` — room · teacher · course · section · time + three ≥44px buttons
- [ ] **Running = one tap**, no dialog
- [ ] **Late** → inline time input pre-filled with now
- [ ] **Not Found** → immediate submit, card shows "awaiting threshold"
- [ ] Optimistic update; revert + toast on failure
- [ ] Collapsed remark field
- [ ] Submitted card collapses to a badge, re-tappable to amend
- [ ] Slot switcher (prev / current / next)

**Done when:** a full slot is checked on a phone-sized viewport without zooming, one tap per
normal class.

### Block 10 · Dashboard + teacher (hours 13–15)

- [ ] `/dashboard` — summary cards, live table, 30s poll, attention panel
- [ ] Highlight `MISSED` / `NOT_CHECKED` rows distinctly — they mean different things
- [ ] `/teacher` — today, upcoming, missed-needing-action, makeups, stats
- [ ] Missed-class action: **Confirm** / **Dispute** (note) / **Schedule makeup**
- [ ] Notification bell + dropdown, unread count

**Done when:** a missed class raises a teacher notification and the teacher can respond.

### Block 11 · Makeup + approvals + reports (hours 15–17)

- [ ] `/teacher/makeup` — original class, mode toggle, date, slot dropdown (lattice only), room
- [ ] Live conflict check on change → `ConflictNotice`; block submit while conflicted
- [ ] `/approvals` — HoD queue, approve/reject with note
- [ ] `/reports` — daily + teacher-wise, date range, CSV export via client-side blob
- [ ] Teacher report view scoped to self

**Done when:** AC-06, AC-07, AC-08, AC-09 demonstrate end-to-end in the UI.

### Block 12 · Admin (hours 17–18)

- [ ] `/admin/routine` — upload → ingestion report → review table → activate
- [ ] Surface `skipped_sample` prominently — those cells need a human
- [ ] `/admin/calendar` — holiday add/remove
- [ ] `/admin/settings` — threshold + window
- [ ] `/admin/audit` — paginated log

**Done when:** AC-01 completes in the UI, upload through activation.

### Block 13 · Deploy (hours 18–20)

- [ ] `web/Dockerfile` — Next.js standalone output
- [ ] `deploy/compose.prod.yaml` — `api` + `web` + `caddy`, adapted from open-routine
- [ ] `deploy/Caddyfile` — `/api/*` → api:8000, `/*` → web:3000
- [ ] `.env.example` — `CLASSTRACK_JWT_SECRET`, `CLASSTRACK_ADMIN_TOKEN`, `DOMAIN`, `ACME_EMAIL`
- [ ] `docker compose up` locally end-to-end
- [ ] Seed + ingest a real routine PDF against the running stack
- [ ] Backup note in README: `docker compose cp api:/data/classtrack.db ./backup-$(date +%F).db`
- [ ] Walk all ten acceptance criteria; record results in PROGRESS.md
- [ ] Deploy to the target host

**Done when:** AC-01…AC-10 pass against the deployed stack.

---

## 2. Cut list — when running behind

Cut in this order. Everything here is deferrable without breaking an acceptance criterion.

| Order | Cut | Saves | Cost |
|---|---|---|---|
| 1 | CSV export | 30m | Manual copy from table |
| 2 | `/admin/audit` viewer (keep the writes) | 45m | Query the DB directly |
| 3 | `/reports/staff` | 45m | AC-09 unaffected |
| 4 | Notification bell (keep the records) | 45m | Teacher still sees missed classes on `/teacher` |
| 5 | `/admin/calendar` UI (seed holidays via CLI) | 45m | Holidays still excluded |
| 6 | `/admin/settings` UI (env var instead) | 30m | Threshold still configurable |
| 7 | Dispute flow (keep confirm) | 45m | AC-05 satisfied by confirm alone |
| 8 | Slot switcher on `/staff` (current only) | 30m | AC-02 unaffected |

**Never cut:** the sweep tests (Block 6), AC-08 verification, or the one-tap staff flow.
Those are the system's correctness and its adoption.

## 3. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Routine PDF differs from open-routine's expected layout | Medium | `skipped_cells` reports it; fall back to a seeded fixture for the demo — do not debug the parser inside the 2 days |
| Sweep timezone bug (UTC vs Asia/Dhaka) | **High** | Pin tz in settings; pass `now` explicitly into `sweep_once` so tests control the clock |
| Instance generation slow on SQLite | Low | `bulk_insert_mappings`, one transaction |
| Scope creep into the editable verification grid | **High** | Explicitly deferred in SRS §2.2 — review is read-only |
| Frontend/backend contract drift | Medium | API.md frozen before Block 8; types mirror it |
| Auth cookie blocked cross-origin in dev | Medium | Next.js rewrite proxies `/api` → `:8000` so it stays same-origin |

## 4. Definition of done

- [ ] All ten acceptance criteria pass on the deployed stack
- [ ] The five Block 6 tests pass
- [ ] A real routine PDF ingests, activates, and generates instances
- [ ] Staff checking is usable one-handed on a phone
- [ ] `MISSED` and `NOT_CHECKED` are visibly distinct in the UI
- [ ] Approved online makeup is provably absent from staff checking
- [ ] Audit log holds a complete missed → makeup → completed chain
- [ ] README documents setup, seed, ingest, deploy, and backup
