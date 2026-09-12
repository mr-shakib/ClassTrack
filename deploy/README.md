# Deploying ClassTrack

One host, three containers, no external services.

```
        :443  ┌───────┐   /api/*   ┌─────┐
  internet ──▶│ caddy │───────────▶│ api │──▶ SQLite (named volume)
              │  TLS  │            └─────┘
              └───┬───┘   /*       ┌─────┐
                  └───────────────▶│ web │
                                   └─────┘
```

## First deploy

```bash
cp .env.example .env
openssl rand -hex 32          # paste into CLASSTRACK_JWT_SECRET
# set CLASSTRACK_DOMAIN to a hostname whose DNS A record points here

docker compose -f deploy/compose.prod.yaml up -d --build
```

Caddy obtains and renews the TLS certificate itself. Ports 80 and 443 must be
reachable from the internet for the ACME challenge to succeed.

Migrations run automatically on container start (`docker-entrypoint.sh`), so the
schema is always current before the server accepts traffic.

## Create the first accounts

```bash
docker compose -f deploy/compose.prod.yaml exec api classtrack seed
```

This loads the faculty directory, creates the four demo accounts, and opens a
semester. **Change every password before going live** — they are all
`classtrack`.

## Load the routine

Upload the PDF at `/admin`, review what was extracted, then activate. Activation
generates the class instances for the semester.

From the CLI instead:

```bash
docker compose -f deploy/compose.prod.yaml exec api \
  classtrack ingest /path/to/routine.pdf --department cse --semester "Fall 2026"
docker compose -f deploy/compose.prod.yaml exec api classtrack generate
```

## Backup

The SQLite file is the entire database.

```bash
docker compose -f deploy/compose.prod.yaml cp \
  api:/data/classtrack.db ./backup-$(date +%F).db
```

A nightly crontab entry satisfies the SRS backup requirement:

```cron
0 2 * * * cd /srv/classtrack && docker compose -f deploy/compose.prod.yaml cp api:/data/classtrack.db /srv/backups/classtrack-$(date +\%F).db
```

Restore by stopping the stack, copying a backup back to the volume, and starting
again.

## Scaling note

The status sweep runs inside the `api` process. Keep exactly **one** replica —
two would both try to finalise the same rows. To scale out, move
`sweep_once()` to an external scheduler and set
`CLASSTRACK_SWEEP_INTERVAL_SECONDS=0` on the web replicas; the function already
takes `now` as a parameter and holds no loop state.

Moving to Postgres is one variable: set `CLASSTRACK_DATABASE_URL` to a
`postgresql+asyncpg://…` URL and install the `postgres` extra.

## Logs

```bash
docker compose -f deploy/compose.prod.yaml logs -f api
docker compose -f deploy/compose.prod.yaml logs -f caddy
```
