# ClassTrack

Department Class Monitoring & Makeup Management System — CSE, Daffodil International University.

Monitors whether scheduled classes are actually conducted according to the approved routine,
and manages the follow-up when they are not: late arrivals, missed classes, staff checking
failures, makeup scheduling, and online-class approval.

**Stack:** FastAPI + SQLite · Next.js 16 + TypeScript + Tailwind · Docker + Caddy
**Reuses:** [`open-routine`](../../Personal/projects/open-routine) routine PDF ingestion (vendored, see [VENDORED.md](backend/src/classtrack/routine/VENDORED.md))

Status: **v1 complete** — all ten acceptance criteria verified, 25 tests passing.

---

## The one thing to get right

The system separates **six independent questions**, and collapsing any two produces
unfair reporting:

1. Did the teacher conduct the class?
2. Was the teacher late, and by how much?
3. **Did office staff actually check the class?**
4. Was a missed class later recovered?
5. Was the makeup physical or online?
6. Did an online class have proper approval?

Most critically: **`MISSED` requires positive evidence** of teacher absence — a staff
member recorded `TEACHER_NOT_FOUND` and the threshold elapsed. **`NOT_CHECKED` is the
absence of evidence** — a monitoring gap on the staff side, never a teacher's fault.

That distinction lives in [`services/sweep.py`](backend/src/classtrack/services/sweep.py)
and is pinned by [`tests/unit/test_monitoring_rules.py`](backend/tests/unit/test_monitoring_rules.py).

## The lattice

The DIU routine is a fixed **6 × 6 grid** — six working days × six 90-minute slots
(Friday is the weekend). Every class occupies exactly one cell, so occupancy is
**string equality on the slot label**, and conflict detection is three indexed lookups
rather than interval arithmetic.

> ⚠️ Do not replace slot-label equality with time-range overlap logic.

## Quick start

```bash
# Backend  → localhost:8000/docs
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
classtrack seed        # settings, 219 faculty, 5 accounts, a semester
classtrack demo        # synthetic routine + instances + a back-dated history
uvicorn classtrack.main:app --reload

# Frontend → localhost:3000
cd web
npm install
npm run dev
```

Sign in with any of these — password `classtrack`:

| Account | Role | Lands on |
|---|---|---|
| `admin@diu.edu` | Super admin (fallback) | `/dashboard` |
| `hod@diu.edu` | Head of department — full admin | `/dashboard` |
| `associate@diu.edu` | Associate head — full admin | `/dashboard` |
| `coordinator@diu.edu` | Coordination officer — no reports, no approvals | `/dashboard` |
| `committee@diu.edu` | Committee — checks and corrects classes | `/staff` |
| `staff1@diu.edu` | Office staff | `/staff` |
| `teacher@diu.edu` | Teacher | `/teacher` |

## Load a real routine

```bash
classtrack ingest routine.pdf --department cse --semester "Fall 2026"
classtrack generate
```

Or upload it at `/admin`. **Ingest never auto-activates** — review the extraction, then
activate. That review step is AC-01, and it is the only thing between a misparsed
document and a semester of wrong monitoring records.

## Commands

| Command | Does |
|---|---|
| `classtrack seed` | Settings, faculty directory, demo accounts, a semester |
| `classtrack demo` | Synthetic routine + instances + back-dated monitoring history |
| `classtrack demo-routine` | Synthetic routine only (no PDF needed) |
| `classtrack ingest <pdf>` | Parse a real routine PDF |
| `classtrack generate` | Materialise class instances (idempotent) |

## Tests

```bash
cd backend && pytest          # 25 tests
cd web && npx tsc --noEmit && npx eslint src
```

## Deploy

```bash
cp .env.example .env          # set CLASSTRACK_DOMAIN and CLASSTRACK_JWT_SECRET
docker compose -f deploy/compose.prod.yaml up -d --build
```

Caddy handles TLS. See [deploy/README.md](deploy/README.md) for backup and scaling notes.

**Backup** — the SQLite file is the whole database:

```bash
docker compose -f deploy/compose.prod.yaml cp api:/data/classtrack.db ./backup-$(date +%F).db
```

## Documentation

| Document | Purpose |
|---|---|
| [docs/SRS.md](docs/SRS.md) | Requirements, scope, roles, business rules, acceptance criteria |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Structure, reuse map, status engine, decisions |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Tables, indexes, invariants |
| [docs/API.md](docs/API.md) | Endpoint contract (35 endpoints) |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Build plan and cut list |
| [docs/PROGRESS.md](docs/PROGRESS.md) | What was built, what was deferred, what went wrong |

## Scope

This is a **lean v1**: every module from the SRS reachable end-to-end, shallow depth,
extension points named for v2. [SRS §2](docs/SRS.md) lists what is in and what is
deferred; [ARCHITECTURE §14](docs/ARCHITECTURE.md) says where each deferred feature plugs in.

Known gap: the PDF parser is vendored and unchanged from `open-routine`, but has not been
run against a real DIU routine here — no such document was available. Everything
downstream is exercised against a synthetic routine of the same shape.
