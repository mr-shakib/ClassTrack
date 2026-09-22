# ClassTrack — Progress Tracker

Update as you go. One line per block; tick tasks in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

**Started:** 2026-09-12  ·  **Status:** 🟢 **v1 complete** — all 10 acceptance criteria verified, 25 tests green

Legend: 🔴 not started · 🟡 in progress · 🟢 done · ⚪ cut

---

## Day 1 — Backend

| Block | Hours | Deliverable | Status | Notes |
|---|---|---|---|---|
| 1 | 0–1.5 | Skeleton + vendored ingestion | 🟢 | 865 ln vendored @ `bcd2b8d`; imports rewritten |
| 2 | 1.5–3 | Models + migration + seed | 🟢 | 12 tables, all indexes, 219 real faculty seeded |
| 3 | 3–4 | Auth + RBAC | 🟢 | bcrypt + PyJWT (not passlib/jose — broken on 3.14) |
| 4 | 4–5 | Routine ingest + activation | 🟢 | ingest/review/activate + conflict scan; PDF path vendored, unverified (no PDF) |
| 5 | 5–6 | Instance generation | 🟢 | 2900 instances; re-run creates 0 ✅ |
| 6 | 6–8 | Checking + sweep ⭐ | 🟢 | **14 rule tests pass**; MISSED vs NOT_CHECKED provably separated |
| 7 | 8–10 | Makeup + approvals + reports | 🟢 | 11 more tests; **AC-08 asserted in CI** |

## Day 2 — Frontend + deploy

| Block | Hours | Deliverable | Status | Notes |
|---|---|---|---|---|
| 8 | 10–11.5 | Scaffold + auth | 🟢 | Next 16 + React 19 + Tailwind 4; API proxied same-origin |
| 9 | 11.5–13 | Staff checking ⭐ | 🟢 | one-tap RoomCard, optimistic, ≥44px targets |
| 10 | 13–15 | Dashboard + teacher | 🟢 | 30s poll; MISSED/NOT_CHECKED visually distinct |
| 11 | 15–17 | Makeup + approvals + reports | 🟢 | live conflict feedback; CSV export |
| 12 | 17–18 | Admin screens | 🟢 | routine review/activate, calendar, rules, audit |
| 13 | 18–20 | Deployment | 🟢 | both images built + stack verified in containers |

---

## Acceptance criteria

| ID | Criterion | Status | Verified how |
|---|---|---|---|
| AC-01 | Admin uploads, verifies, activates a routine | 🟢 | UI + API; review surfaces conflicts before activation. PDF parser vendored but unexercised — no PDF available |
| AC-02 | Staff checks classes room-wise on mobile | 🟢 | room-grouped cards, one tap for Running |
| AC-03 | Late recorded, minutes auto-calculated | 🟢 | 10:00 + 10:08 → 8 min (test + live) |
| AC-04 | Missed vs Not Checked handled separately | 🟢 | 4 dedicated sweep tests |
| AC-05 | Teacher notified and can respond | 🟢 | verified end-to-end: absent → sweep → notify → confirm |
| AC-06 | Physical makeup appears in checking | 🟢 | verified live + test |
| AC-07 | Online makeup requested and decided | 🟢 | verified live + test |
| AC-08 | Approved online absent from checking | 🟢 | **asserted in test_makeup_flow.py** |
| AC-09 | Teacher-wise reports generate | 🟢 | daily + teacher-wise + staff, with CSV |
| AC-10 | Audit log preserves history | 🟢 | 266 entries; System-attributed sweep rows distinguished |

## Critical tests (Block 6)

| Test | Status |
|---|---|
| `TEACHER_NOT_FOUND` before threshold → unresolved | 🟢 |
| `TEACHER_NOT_FOUND` after threshold → `MISSED` | 🟢 |
| No check + window closed → `NOT_CHECKED`, never `MISSED` | 🟢 |
| `RUNNING`/`LATE` untouched by sweep | 🟢 |
| Double submit → one check record | 🟢 |
| Late calc: 10:00 slot + 10:08 → 8 minutes | 🟢 |

---

## Cut log

Record anything dropped, so v2 knows where to resume.

| Item | Cut at | Reason | Resume from |
|---|---|---|---|
| Real PDF ingest verification | Block 4 | No routine PDF available (upstream does not redistribute it) | `classtrack ingest <real.pdf>` — the parser is open-routine's, unchanged |
| Editable routine verification grid | Block 12 | Planned deferral (SRS §2.2) | Review is read-only; correct by re-ingesting |
| Email / SMS notifications | Block 7 | Planned deferral (SRS §2.2) | Add an `EmailChannel` beside `InAppChannel` |
| Conflict override with reason | Block 7 | Planned deferral (SRS §2.2) | `ConflictReport.overridable` is already threaded through |
| Monthly / semester / yearly reports | Block 11 | Planned deferral (SRS §2.2) | ✅ Done 2026-09-20 — `/reports/overview` |

## Decisions changed during the build

| # | Original (ARCHITECTURE.md §13) | Changed to | Why |
|---|---|---|---|
| — | `passlib` + `python-jose` for auth | `bcrypt` + `PyJWT` directly | Both unmaintained and broken on Python 3.14 |
| — | (unplanned) | Added `services/demo_routine.py` + `demo_seed.py` | No real routine PDF available; needed to unblock Blocks 5–13 |
| — | Next.js rewrite reads `API_ORIGIN` at runtime | Passed as a Docker **build** arg | Next compiles rewrites into `routes-manifest.json` at build time; a runtime read is silently ignored |
| — | (unplanned) | ESLint `react-hooks/set-state-in-effect` disabled | Every hit is fetch-on-mount via an async continuation; SWR/React Query is the real fix if this grows |

## Blockers

| Blocker | Hit at | Resolution |
|---|---|---|
| `passlib` / `python-jose` broken on Python 3.14 | Block 1 | Used `bcrypt` + `PyJWT` directly |
| Demo teacher had no classes (219 faculty, ~40 in routine) | Block 7 | `rebind_demo_teacher()` binds the account to a teacher with a real history |
| `MissingGreenlet` after rollback in the demo seeder | Block 7 | Captured plain ids before the retry loop; a rollback expires ORM objects and lazy-loading them does sync IO in async context |
| `useSearchParams` broke the production build | Block 11 | Wrapped the makeup form in `<Suspense>` |
| Seed file path broke inside the image | Block 13 | Candidate-path lookup instead of one `__file__`-relative path |
| Next.js rewrite ignored the runtime env var | Block 13 | Build arg — found only by running the containers, not by building them |

---

## Final verification (2026-09-12)

```
backend   25 tests passing · ruff clean
frontend  tsc clean · eslint clean · production build: 13 routes
docker    api + web images build; full stack verified over a container network
```

| Area | Lines |
|---|---|
| `backend/src/classtrack` | 5,886 |
| `backend/tests` | 734 |
| `web/src` | 3,500 |
| `docs` | 1,534 |

**Demo data:** `classtrack seed && classtrack demo` → 166 routine sessions,
2,900 class instances, ~240 checks, 9 missed, 30 not-checked, 2 makeups.

### What a reviewer should check first

1. `backend/tests/unit/test_monitoring_rules.py` — the MISSED vs NOT_CHECKED split.
2. `backend/tests/unit/test_makeup_flow.py::test_approved_online_makeup_is_excluded_from_checking` — AC-08.
3. `/staff` at a 360px viewport — the one-tap requirement.

---

## 2026-09-20 — Reports, roles and reschedule visibility

| Area | What changed |
|---|---|
| Roles | `COORDINATION_OFFICER` added (dashboards, admin screens, correcting past checks; no reports or approvals). Head and Associate Head now hold every Super-admin right. Accounts tab to manage non-teacher logins. |
| Reports | Monthly / semester / custom period with filters (teacher, floor, slot, course, section) and charts; daily report floor-wise; teacher-wise report listing every class; summary and teacher PDFs (reportlab). |
| Minimum classes | Course-sections with fewer than `min_conducted_classes` (default 18) held so far are red; their teacher is flagged. |
| Counting fix | A class recovered by a makeup was counted as conducted twice (original + makeup both `MAKEUP_COMPLETED`). Now one outcome per class; the makeup carries it. Conduct rate no longer counts not-checked classes against the teacher. |
| Reschedules | Makeups carry `rescheduled_from`, missed classes `rescheduled_to`; a dashed teal "Makeup · from …" tag marks them on every list. |
| Day status | `/today`: every class on a day, filterable by teacher initials, floor, slot, outcome. |
| Checking | "Find by teacher" search for correcting past classes. |
| Approvals | 4-column card grid with teacher/course search and mode filter. |

---

## 2026-09-23 — An empty room needs no approval

| Area | What changed |
|---|---|
| Reschedule | A reschedule into an empty room is booked the moment it is made: the makeup starts `SCHEDULED`, its `is_makeup=1` instance is created at once, and the original goes straight to `MAKEUP_SCHEDULED`. This is what SRS §8 and the implementation plan always described; the code had drifted into asking the HoD first. |
| Room holding | Because the instance exists immediately, the cell is occupied: `/makeup/free-rooms` drops the room and `check-conflict` reports `ROOM` against it, so no second teacher can reschedule into that room, day and slot. |
| Approvals | Only online requests reach `/approvals/pending` now. The queue still decides in-room requests left over from the old rule, and the mode filter appears only while such a request is queued. |
| Notifications | New `MAKEUP_SCHEDULED` kind: the teacher is told the room is held, the HoD is told what happened instead of being asked. `MAKEUP_REQUEST` is no longer written. |
| Online time | An online class may now be held at **any time of any day** — the teacher picks a start off the clock and it runs 90 minutes, instead of taking one of the six routine slots. New nullable `makeup_class.start_min`/`end_min` (migration `b6d4e9f10275`) carry the period, read through `MakeupClass.bounds()`. |
| Lattice | Such a period is not a cell, so it is matched by interval **overlap** in `routine/clock.py` rather than slot equality. This is the only exception, and it is safe because an online class holds no room — room occupancy is still slot equality everywhere. Conflicts now name the clashing class at *its* own time, which is what makes an overlap legible. |
| Bug found on the way | The `time_slot not in SLOTS` guards in `sweep` and the makeup route would have silently skipped any off-lattice makeup — never reminding the teacher, never sending `ends_at`. Both now read `bounds()`; a regression test covers the sweep. |
