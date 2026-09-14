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

## Behind an existing nginx

`compose.prod.yaml` brings its own Caddy and claims ports 80 and 443. On a host
that already serves other sites through nginx, use `compose.nginx.yaml`
instead: the same two app containers, bound to loopback only (API on
`127.0.0.1:8310`, web on `127.0.0.1:3310`), with the host nginx terminating TLS.

```bash
# code in /srv/classtrack/app, secrets in /srv/classtrack/.env (outside the checkout)
docker compose --env-file /srv/classtrack/.env \
  -f deploy/compose.nginx.yaml up -d --build
```

Then add the site. Get the certificate with only the port-80 block of
`nginx/classtrack.conf` enabled, then install the whole file:

```bash
certbot certonly --webroot -w /var/www/certbot -d class.bitstreamhq.com
sudo install -m 644 deploy/nginx/classtrack.conf /etc/nginx/sites-available/class.bitstreamhq.com
sudo ln -s /etc/nginx/sites-available/class.bitstreamhq.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
certbot reconfigure --cert-name class.bitstreamhq.com --deploy-hook "systemctl reload nginx"
```

The compose project is named `classtrack`, so its containers and its
`classtrack_classtrack-data` volume never collide with other stacks on the host.
With this file, replace `compose.prod.yaml` with `compose.nginx.yaml` (and add
`--env-file`) in the commands below.

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
