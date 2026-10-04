---
name: run-classtrack
description: Start, run, drive and screenshot ClassTrack (FastAPI backend + Next.js web app) locally on a throwaway database copy, sign in as any role, click through pages, hit the API with curl, and run the backend/web tests. Use when asked to run or start ClassTrack, check a change works in the real app, take a screenshot of a page, or test it.
---

ClassTrack is a FastAPI API (`backend/`, port 8000) behind a Next.js 16 dev server
(`web/`, port 3000, proxies `/api/*` to the API). An agent brings both up with
`stack.sh` on a fresh copy of the dev database, then drives the browser with
`driver.cjs`, a small Playwright command runner that reads one command per stdin
line. All paths below are relative to the repo root.

## Prerequisites

Assumed present (the README quick start makes them): `backend/.venv` with the
package installed, and `web/node_modules`. Also used: `node`, `curl`, `ss`,
`setsid`. `stack.sh up` installs Playwright once into the run dir, outside the
repo. It used the Chromium already cached in `~/.cache/ms-playwright`.

Everything a run writes goes to `$CT_RUN_DIR` (default `$TMPDIR/classtrack-run`):
`run.db`, `api.log`, `web.log`, `shots/`, `pw/`, `pids`. Set it to your scratchpad:

```bash
export CT_RUN_DIR=<your scratchpad>/ct-run
```

## Run (agent path)

```bash
.claude/skills/run-classtrack/stack.sh up       # ~5s: fresh DB copy, migrate, API + web
.claude/skills/run-classtrack/stack.sh status
.claude/skills/run-classtrack/stack.sh down     # stops only what `up` started
```

Every `up` starts from a new copy of `backend/classtrack.db`, so anything the last
run changed (passwords, checks) is gone. The original file is never written.

Drive the browser. Each command is echoed. A failing one saves `shots/fail.png`,
prints the URL and exits 1:

```bash
node .claude/skills/run-classtrack/driver.cjs <<'EOF'
login SRH classtrack
click 'header a[aria-label="Your profile"]'
wait-text Sign in with initial
ss profile-desktop full
viewport 390 844
ss profile-phone
viewport 1280 900
fill 'form >> nth=-1 >> input[autocomplete="current-password"]' classtrack
fill 'form >> nth=-1 >> input[autocomplete="new-password"] >> nth=0' mine-only
fill 'form >> nth=-1 >> input[autocomplete="new-password"] >> nth=1' mine-only
click 'button:has-text("Change password")'
wait-text Password changed.
ss password-changed
errors
EOF
```

That run changes SRH's password to `mine-only` until the next `up`. Later
sign-ins as SRH in the same run need it.

Screenshots go to `$CT_RUN_DIR/shots/<name>.png`. Read them; a page that says
only "Loading…" was captured too early.

| command | does |
|---|---|
| `login <user> <password>` | signs in through the real form, waits to leave `/login`, prints where it landed |
| `nav <path>` | goes to `$CT_BASE` + path (default `http://localhost:3000`) |
| `wait-text <text>` / `wait-gone <text>` | waits up to 60s for text to show / to go |
| `wait-url <glob>` | e.g. `wait-url **/teacher` |
| `click <sel>` / `fill <sel> <value>` / `press <key>` | Playwright selectors; quote ones with spaces |
| `select <sel> <value>` | picks a `<select>` option, e.g. a time slot |
| `viewport <w> <h>` | `390 844` is a phone |
| `ss <name> [full]` / `ss-el <sel> <name>` | screenshot (page, full page, one element) |
| `text <sel>` / `value <sel>` / `eval <js>` | print what is on the page |
| `errors` | console errors so far |

Typical admin check, waiting past the spinner:

```bash
node .claude/skills/run-classtrack/driver.cjs <<'EOF'
login hod@diu.edu classtrack
wait-text Live monitoring
wait-gone Loading…
ss hod-dashboard
nav /admin/audit
wait-text Changed own password
text 'tbody tr'
EOF
```

### Accounts in the dev database

All take the password `classtrack`. Each role lands on its home page.

| sign in as | role | lands on |
|---|---|---|
| `SRH` (or `teacher@diu.edu`) | Teacher | `/teacher` |
| `staff1@diu.edu` | Office staff | `/staff` |
| `committee@diu.edu` | Committee | `/staff` |
| `coordinator@diu.edu` | Coordination officer | `/dashboard` |
| `hod@diu.edu`, `associate@diu.edu`, `admin@diu.edu` | Full admin | `/dashboard` |

`SH` exists too but not on `classtrack`.

### API only

```bash
curl -s -c "$CT_RUN_DIR/jar" -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'content-type: application/json' -d '{"username":"staff1@diu.edu","password":"classtrack"}'
curl -s -b "$CT_RUN_DIR/jar" http://127.0.0.1:8000/api/v1/auth/profile
```

OpenAPI docs: http://127.0.0.1:8000/docs while the stack is up.

## Run (human path)

`stack.sh up`, then open http://localhost:3000. `stack.sh down` when done.

## Test

```bash
cd backend && .venv/bin/python -m pytest                          # all pass, ~70s
cd backend && .venv/bin/python -m pytest tests/unit/test_profile.py
cd backend && .venv/bin/ruff check src tests
cd web && npx tsc --noEmit -p . && npx eslint src                  # ~10s, silent when clean
```

## Gotchas

- **`lsof` does not see next-server's `*:3000` socket here.** Killing "whatever
  listens on 3000" via lsof silently leaves the dev server running. `stack.sh`
  uses `ss -ltnp` and records the PIDs it starts.
- **Next 16 allows one `next dev` per directory.** A second one binds :3001, then
  exits with `Another next dev server is already running`; the live one is in
  `web/.next/dev/lock`. `stack.sh up` reuses it, since it serves the same source
  with hot reload, and `down` leaves it alone. Kill a stale one by the PID in the
  lock. That stops its `next dev` parent too.
- **The API must be on 127.0.0.1:8000.** `next.config.ts` bakes the `/api` rewrite
  at build time with that default, and `up` refuses if the port is taken.
- **`backend/classtrack.db` lags the migrations.** `up` runs `alembic upgrade
  head` on the copy. Alembic takes its URL only from `CLASSTRACK_DATABASE_URL`;
  `alembic.ini` leaves it empty.
- **The status sweep is off in this stack** (`CLASSTRACK_SWEEP_INTERVAL_SECONDS=0`).
  On, it rewrites class statuses every minute under whatever you are looking at.
  `CLASSTRACK_RESEND_API_KEY` is unset on purpose: the dev data mails real teachers.
- **`wait-text <nav label>` returns at once.** "Dashboard" and "Reports" are in
  the header on every page. Wait for text from the page body, then `wait-gone Loading…`.
- **Headless Chromium runs in UTC** even on a Dhaka host. The driver sets
  `Asia/Dhaka` (`CT_TZ` overrides) so screenshots show the times users see.
- **Audit timestamps show 6 hours early in any browser.** This is an app bug,
  not the driver: the API sends naive UTC (`"2026-10-04T12:41:05"`) and the page
  parses it as local time.
- **Expected console errors:** `401` from `/auth/me` before sign-in, and `422`
  from any form the server refuses. Anything else in `errors` is real.
- **The Next dev indicator** (an "N" or "Compiling" pill, bottom left) shows in
  screenshots. The first visit to a route compiles it, which takes a few seconds.
- **Do not add `-q` to pytest.** `addopts` already has it; `-qq` hides the pass count.
- **`ruff format --check` fails on 22 files nobody touched.** Format only files
  you change.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'tests'`** from `.venv/bin/pytest`: the
  tests import `tests.conftest`. Run `.venv/bin/python -m pytest` from `backend/`.
- **`web.log` says `⨯ Another next dev server is already running`**: see the
  one-dev-server gotcha; `stack.sh status` prints its PID and URL.
- **`port 8000 is taken (pid N)`**: an API from an earlier run, or something
  else. If `up` started it, `stack.sh down`; otherwise stop it yourself.
- **Screenshot shows only the header and "Loading…"**: the wait matched too
  early. Add `wait-gone Loading…`.
