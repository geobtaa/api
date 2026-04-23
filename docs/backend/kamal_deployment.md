# Kamal Deployment Guide

This runbook documents the current Kamal setup for the three active servers:

- `dev1`
- `dev2`
- `prd`

It intentionally omits older generic Kamal guidance that does not match how these boxes are configured today.

## Current Environments

| Destination | Host | Config | Secrets file |
|-------------|------|--------|--------------|
| `dev1` | `lib-btaageoapi-dev-app-01.oit.umn.edu` | `config/deploy.dev1.yml` | `.kamal/secrets.dev1` |
| `dev2` | `lib-geoportal-dev-web-01.oit.umn.edu` | `config/deploy.dev2.yml` | `.kamal/secrets.dev2` |
| `prd` | `lib-geoportal-prd-web-01.oit.umn.edu` | `config/deploy.prd.yml` | `.kamal/secrets.prd` |

Shared secrets live in `.kamal/secrets-common`.

Kamal always requires an explicit destination in this repo:

```bash
kamal deploy -d dev1
kamal deploy -d dev2
kamal deploy -d prd
```

## Current Runtime Layout

Each destination is a single-host deployment with these app roles:

- `web`: nginx + SSR + FastAPI on the public host
- `worker`: Celery worker
- `cron`: cron container for scheduled bridge/blog/analytics-maintenance tasks
- `flower`: Celery monitoring UI

Each destination also runs these accessories on the same VM:

- `paradedb`
- `elasticsearch`
- `redis`

All three boxes now use the same persistent storage layout:

- `/var/lib/btaa-geospatial-api/postgres`
- `/var/lib/btaa-geospatial-api/elasticsearch`
- `/var/lib/btaa-geospatial-api/redis`

All routine Kamal operations should use the shared `deploy` SSH account.

### Single-host routing

The public host serves both the UI and the API:

- `https://<host>/` -> SSR frontend
- `https://<host>/api/...` -> FastAPI
- `https://<host>/assets/...` -> static client assets

Kamal's bridged asset directory is normalized by `backend/scripts/start_web_singlehost.sh` before nginx starts, so old chunk URLs keep working during deploys.

The health check path is:

```text
/api/docs
```

## Secrets

Two files are loaded for every deploy:

1. `.kamal/secrets-common`
2. `.kamal/secrets.<destination>`

Per-destination files should only need the host and the shared SSH user:

```bash
export KAMAL_HOST=lib-geoportal-prd-web-01.oit.umn.edu
export KAMAL_SSH_USER=deploy
```

The exact shared secret set is defined by `config/deploy.yml`:

- ERB `ENV[...]` references
- `env.secret`
- `registry`

Treat `config/deploy.yml` as the source of truth so the docs do not drift from the config.

Before running direct `kamal` commands in a shell, source the secrets:

```bash
set -a
source .kamal/secrets-common
source .kamal/secrets.prd
set +a
```

If a Make target exists for the task you want, prefer the Make target because it already understands `KAMAL_DEST`.

## Server Bootstrap

This is only for a brand-new box. `dev1`, `dev2`, and `prd` are already bootstrapped.

Use the helper script with an existing SSH user that already has passwordless `sudo`:

```bash
backend/scripts/bootstrap_kamal_deploy_user.sh \
  --host lib-geoportal-prd-web-01.oit.umn.edu \
  --ssh-user your_existing_admin_user
```

The script:

- creates the shared `deploy` user and group if needed
- adds `deploy` to the `docker` group
- seeds `/home/deploy/.ssh/authorized_keys`
- prepares `/var/lib/btaa-geospatial-api`
- prepares `/var/lib/btaa-geospatial-api/elasticsearch`

After bootstrapping a new host:

1. Add each teammate's public key to `/home/deploy/.ssh/authorized_keys`.
2. Verify `ssh deploy@<host>` works.
3. Create/update `.kamal/secrets.<destination>` with `KAMAL_SSH_USER=deploy`.
4. Run `kamal setup -d <destination>`.

## Routine Deploy Workflow

For the existing environments, the normal workflow is:

```bash
set -a
source .kamal/secrets-common
source .kamal/secrets.prd
set +a

kamal deploy -d prd
```

Useful variants:

```bash
kamal deploy -d dev1
kamal deploy -d dev2
kamal redeploy -d prd
kamal rollback -d prd
```

There is no separate manual Docker build/push step in the normal workflow. Kamal builds and pushes the image using the GHCR credentials from `.kamal/secrets-common`.

There is also no standing post-deploy migration step in the current runbook. If a specific change needs a one-off migration or repair script, document that exact command in the PR or issue and run it explicitly.

## Verification

After a deploy, check the running version and container health:

```bash
kamal app version -d prd
kamal app details -d prd
kamal accessory details -d prd paradedb
kamal accessory details -d prd elasticsearch
kamal accessory details -d prd redis
```

Then confirm the public app is responding:

```bash
curl -sS -o /dev/null -D - https://lib-geoportal-prd-web-01.oit.umn.edu/api/docs
```

Use the matching host for `dev1` or `dev2` when checking those destinations.

## Common Operations

### Logs

```bash
kamal app logs -d prd --roles web
kamal app logs -d prd --roles worker
kamal app logs -d prd --roles cron
kamal app logs -d prd --roles flower
kamal accessory logs -d prd paradedb
kamal accessory logs -d prd elasticsearch
kamal accessory logs -d prd redis
```

For worker logs, the Make wrapper is usually easiest:

```bash
make kamal-worker-logs KAMAL_DEST=prd
```

### App and accessory control

```bash
kamal app boot -d prd
kamal accessory reboot -d prd redis
kamal accessory reboot -d prd all
kamal app exec -d prd "bash -lc 'cd /app/backend && /opt/venv/bin/python scripts/verify_h3_index.py'"
```

### Cache, indexing, and remote ops

```bash
make kamal-reindex KAMAL_DEST=prd
make kamal-clear-cache KAMAL_DEST=prd KAMAL_CACHE_TYPE=search
make kamal-network-sanity KAMAL_DEST=prd
make db-import KAMAL_DEST=prd
make db-sync KAMAL_DEST=prd
```

### Cron and bridge diagnostics

```bash
make kamal-cron-debug KAMAL_DEST=prd
make kamal-cron-test-bridge KAMAL_DEST=prd
make kamal-bridge-status KAMAL_DEST=prd
make kamal-bridge-status-watch KAMAL_DEST=prd
```

The cron container currently runs:

- daily bridge delta sync at `2:00 AM`
- daily blog sync at `3:00 AM`
- daily sitemap generation at `4:15 AM`
- daily analytics storage maintenance at `4:45 AM`

## Destination Differences

The base config in `config/deploy.yml` is shared across all destinations. The destination files only override host-specific or environment-specific behavior.

Current differences:

- `dev1`: base resource defaults, host `lib-btaageoapi-dev-app-01.oit.umn.edu`
- `dev2`: base resource defaults, host `lib-geoportal-dev-web-01.oit.umn.edu`
- `prd`: larger `web` and `worker` limits, larger Elasticsearch heap, `RATE_LIMIT_ENABLED=true`, `CACHE_DEBUG_HEADERS=false`, `CACHE_LOG_EVENTS=false`, `WEB_UVICORN_WORKERS=3`

If a new destination needs a persistent behavior difference, put only that override in `config/deploy.<dest>.yml` and keep the shared behavior in `config/deploy.yml`.

## Troubleshooting

### `registry/username: is required`

Your current shell has not sourced the Kamal secrets. Reload:

```bash
set -a
source .kamal/secrets-common
source .kamal/secrets.prd
set +a
```

### App is unhealthy after deploy

Check:

```bash
kamal app details -d prd
kamal app logs -d prd --roles web
curl -sS -o /dev/null -D - https://lib-geoportal-prd-web-01.oit.umn.edu/api/docs
```

### Accessory problem

Check the affected accessory and restart it if needed:

```bash
kamal accessory details -d prd paradedb
kamal accessory logs -d prd paradedb
kamal accessory reboot -d prd paradedb
```

Repeat the same pattern for `elasticsearch` or `redis`.

### Cron jobs are not firing

Use the current Make wrappers rather than ad hoc container commands:

```bash
make kamal-cron-debug KAMAL_DEST=prd
make kamal-cron-test-bridge KAMAL_DEST=prd
make kamal-bridge-status KAMAL_DEST=prd
```

### Bridge task was queued but no run appears

That usually means the Celery worker never started the task. Check:

```bash
make kamal-worker-logs KAMAL_DEST=prd
kamal app details -d prd
```

If needed, open Flower through an SSH tunnel:

```bash
set -a
source .kamal/secrets-common
source .kamal/secrets.prd
set +a

ssh -L 5555:localhost:5555 $KAMAL_SSH_USER@$KAMAL_HOST
```

Then open `http://localhost:5555`.

### Storage drift

All active boxes should now mount accessory data from `/var/lib/btaa-geospatial-api/*`.

If you discover a host mounted from `/home/<user>/btaa-geospatial-api-*`, treat it as legacy drift and update the host to the shared layout rather than adding another per-host exception.

## Related Docs

- `docs/make_tasks.md`
- `docs/backend/scripts.md`
- `AGENTS.md`
