#!/usr/bin/env bash
# Bring the ClassTrack stack up on a throwaway copy of the dev database, or down.
#
#   stack.sh up      fresh DB copy -> alembic upgrade -> API :8000 + web :3000
#   stack.sh down    stop what `up` started (never a server it found running)
#   stack.sh status  what is listening on :8000 and :3000
#
# Everything it writes goes under $CT_RUN_DIR (default: $TMPDIR/classtrack-run):
#   run.db  the database copy     api.log / web.log  server output
#   pw/     a Playwright install  shots/             driver screenshots
#   pids    what `up` started, for `down`
# backend/classtrack.db itself is only ever read.
set -euo pipefail

UNIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="${CT_RUN_DIR:-${TMPDIR:-/tmp}/classtrack-run}"
DB_URL="sqlite+aiosqlite:///$RUN/run.db"
LOCK="$UNIT/web/.next/dev/lock"

# `ss`, not `lsof`: lsof does not report next-server's dual-stack *:3000 socket.
port_pids() { ss -ltnpH "sport = :$1" | { grep -o 'pid=[0-9]*' || true; } | cut -d= -f2 | sort -u; }

# Next 16 runs one dev server per directory and records it here.
lock_pid() {
  [ -f "$LOCK" ] || return 0
  local pid
  pid=$(grep -o '"pid":[0-9]*' "$LOCK" | cut -d: -f2)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; fi
}
lock_url() { grep -o '"appUrl":"[^"]*"' "$LOCK" | cut -d'"' -f4; }

wait_for() {  # url seconds
  timeout "$2" bash -c "until curl -sf -o /dev/null '$1'; do sleep 1; done"
}

up() {
  mkdir -p "$RUN/shots"
  : >"$RUN/pids"
  if [ -n "$(port_pids 8000)" ]; then
    echo "port 8000 is taken (pid $(port_pids 8000)) -- the web app proxies the API there." >&2
    echo "Stop that process, or '$0 down' if an earlier 'up' started it." >&2
    exit 1
  fi

  # The driver's browser library. Installed once, outside the repo.
  if [ ! -d "$RUN/pw/node_modules/playwright" ]; then
    echo "installing playwright into $RUN/pw ..."
    npm i --silent --prefix "$RUN/pw" playwright >/dev/null
  fi

  # A fresh copy every time, so a previous run's changed passwords are gone.
  cp "$UNIT/backend/classtrack.db" "$RUN/run.db"
  (cd "$UNIT/backend" && CLASSTRACK_DATABASE_URL="$DB_URL" .venv/bin/alembic upgrade head) \
    >"$RUN/migrate.log" 2>&1 || { cat "$RUN/migrate.log"; exit 1; }

  # Sweep off: it rewrites class statuses every minute, which makes a page
  # change under you. No Resend key: the dev data mails real teachers.
  # setsid -f: fully detached, so no shell reports the job when it is killed.
  (cd "$UNIT/backend" && env -u CLASSTRACK_RESEND_API_KEY \
      CLASSTRACK_DATABASE_URL="$DB_URL" CLASSTRACK_SWEEP_INTERVAL_SECONDS=0 \
      setsid -f .venv/bin/uvicorn classtrack.main:app --host 127.0.0.1 --port 8000 \
      >"$RUN/api.log" 2>&1)
  wait_for http://127.0.0.1:8000/api/v1/health 60 || { tail -20 "$RUN/api.log"; exit 1; }
  port_pids 8000 >>"$RUN/pids"
  echo "api  up  http://127.0.0.1:8000/docs  (database: $RUN/run.db)"

  local existing base
  existing=$(lock_pid)
  if [ -n "$existing" ]; then
    # It serves this same source tree with hot reload, and proxies /api to
    # :8000 -- the API just started. Use it rather than fight it; leave it be.
    base=$(lock_url)
    echo "web  reusing the next dev already running for web/ (pid $existing): $base"
  else
    (cd "$UNIT/web" && setsid -f npm run dev >"$RUN/web.log" 2>&1)
    wait_for http://localhost:3000/login 120 || { tail -20 "$RUN/web.log"; exit 1; }
    lock_pid >>"$RUN/pids"
    base=http://localhost:3000
    echo "web  up  $base"
  fi
  [ "$base" = http://localhost:3000 ] || echo "export CT_BASE=$base   # for the driver"
}

down() {
  [ -s "$RUN/pids" ] || { echo "nothing to stop: no server started by up is recorded"; return; }
  # Killing next-server takes its `next dev` parent with it.
  xargs -r kill <"$RUN/pids" 2>/dev/null || true
  for _ in $(seq 20); do
    alive=""
    while read -r p; do
      if kill -0 "$p" 2>/dev/null; then alive="$alive $p"; fi
    done <"$RUN/pids"
    [ -z "$alive" ] && { : >"$RUN/pids"; echo "stopped"; return; }
    sleep 0.5
  done
  echo "still running: $alive" >&2
  exit 1
}

status() {
  for p in 8000 3000; do
    pids=$(port_pids "$p" | paste -sd' ')
    if [ -n "$pids" ]; then echo ":$p up (pid $pids)"; else echo ":$p down"; fi
  done
  [ -n "$(lock_pid)" ] && echo "web/ dev server: pid $(lock_pid) at $(lock_url)" || true
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  status) status ;;
  *) echo "usage: $0 up|down|status" >&2; exit 2 ;;
esac
