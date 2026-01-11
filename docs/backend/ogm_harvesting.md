# OpenGeoMetadata (OGM) harvesting (admin suite)

This document describes how to ingest OpenGeoMetadata GitHub repos (e.g. `OpenGeoMetadata/edu.stanford.purl`) into the BTAA API, keep them refreshed, and expose them via `ogm_repo[]` filtering and faceting.

## What was added

- **DB tables** (all columns prefixed `ogm_`):
  - `ogm_repos`: which repos to watch and their harvest status
  - `ogm_harvest_runs`: audit log + stats per run
  - `ogm_resource_state`: per-repo `ogm_last_seen_at` + `ogm_missing_since` tracking

- **Elasticsearch field + facet**:
  - `ogm_repo` (keyword-ish; stored as text with `.keyword`) derived from `resources.b1g_adminTags_sm` tags of the form `ogm_repo:<repo_name>`

- **Celery tasks**:
  - `ogm_harvest_repo(repo_name, trigger)`
  - `ogm_harvest_all(trigger)`

- **Admin endpoints** (Basic Auth protected under `/api/v1/admin/*`):
  - `GET /api/v1/admin/ogm/repos`
  - `PATCH /api/v1/admin/ogm/repos/{repo_name}`
  - `POST /api/v1/admin/ogm/harvest`
  - `GET /api/v1/admin/ogm/harvest/runs`
  - `GET /api/v1/admin/ogm/harvest/runs/{run_id}`
  - `GET /api/v1/admin/ogm/repos/{repo_name}/missing`
  - `GET /api/v1/admin/ogm/harvest/runs/{run_id}/dumps`
  - `GET /api/v1/admin/ogm/harvest/runs/{run_id}/dumps/{filename}`

- **Webhook endpoint** (GitHub signature verified; mounted under `/api/v1/admin/*`, but NOT Basic Auth):
  - `POST /api/v1/admin/ogm/webhook`

## One-time setup (existing deployments)

### 1) Database migration

Run the idempotent migration that ensures the `ogm_*` tables exist:

```bash
docker compose exec api bash -lc "cd /app/backend && python db/migrations/create_ogm_harvest_tables.py"
```

### 2) Elasticsearch reindex (required for `ogm_repo` facet/filter)

The ES mapping now includes a new field `ogm_repo`, so you need to rebuild the index once:

```bash
curl -u admin:changeme -X POST "http://localhost:8000/api/v1/admin/reindex"
```

This deletes and recreates the ES index (`ELASTICSEARCH_INDEX`) and re-indexes all `resources`.

## Docker restarts (recommended)

Because we added new code paths and Celery task imports, restart at least:

```bash
docker compose restart api celery_worker
```

Optional:
- `docker compose restart flower` (if you use Flower UI)

You **do not** need to restart Postgres or Elasticsearch for these changes, as long as you run the migration + reindex.

## Dependency note (git)

OGM harvesting currently uses `git clone` / `git pull` inside the API/Celery containers.
Ensure the backend image includes `git` (the project `Dockerfile` installs it).

## Configure env vars

- **Webhook verification** (required to accept GitHub webhooks):
  - `OGM_WEBHOOK_SECRET`: shared secret configured in the GitHub webhook settings

- **Optional paths**:
  - `OGM_CHECKOUT_PATH`: where repos are cloned/pulled (default: `data/opengeometadata`)
  - `OGM_DUMP_BASE_DIR`: where dumps are written (default: `data/harvest_dumps/ogm`)

## Using the system

### 1) Add/watch repos

```bash
curl -u admin:changeme -X PATCH \
  "http://localhost:8000/api/v1/admin/ogm/repos/edu.stanford.purl" \
  -H "Content-Type: application/json" \
  -d '{"ogm_enabled":true,"ogm_watch_mode":"weekly"}'
```

Supported `ogm_watch_mode` values:
- `weekly`, `webhook`, `both`, `manual`

### 1a) Populate `ogm_repos` from GitHub (bulk)

To seed the watch list from the [`OpenGeoMetadata` GitHub org](https://github.com/OpenGeoMetadata):

```bash
docker compose exec api bash -lc "cd /app/backend && python scripts/populate_ogm_repos.py"
```

Notes:
- This script checks whether each repo has a `metadata-aardvark/` directory.\n+  - If **missing**, it sets `ogm_enabled=false` and flags it via `ogm_tags.ogm_missing_aardvark=true`.\n+  - If **present**, it sets `ogm_enabled=true` and `ogm_watch_mode=weekly`.\n+- For better GitHub rate limits, pass a token:\n+  - `GITHUB_TOKEN=... python scripts/populate_ogm_repos.py`

### 2) Trigger a harvest

Single repo:

```bash
curl -u admin:changeme -X POST \
  "http://localhost:8000/api/v1/admin/ogm/harvest" \
  -H "Content-Type: application/json" \
  -d '{"ogm_repo_name":"edu.stanford.purl","ogm_trigger":"manual"}'
```

All enabled weekly repos:

```bash
curl -u admin:changeme -X POST \
  "http://localhost:8000/api/v1/admin/ogm/harvest" \
  -H "Content-Type: application/json" \
  -d '{"ogm_all":true,"ogm_trigger":"weekly"}'
```

### 3) Query by repo (multi-select)

Search across multiple repos:

```text
GET /api/v1/search?ogm_repo[]=edu.stanford.purl&ogm_repo[]=edu.umn
```

Facet values are available via:

```text
GET /api/v1/search/facets/ogm_repo
```

### 4) Dumps

For a given `run_id`:

- manifest:
  - `GET /api/v1/admin/ogm/harvest/runs/{run_id}/dumps`
- download a specific file:
  - `GET /api/v1/admin/ogm/harvest/runs/{run_id}/dumps/dataset.parquet`

## Webhook notes

Configure a GitHub webhook on the repo(s) you care about:
- Payload URL: `http://<your-api-host>/api/v1/admin/ogm/webhook`
- Content type: `application/json`
- Secret: must match `OGM_WEBHOOK_SECRET`
- Events: `push` (and `ping` for validation)

Only repos with `ogm_watch_mode` of `webhook` or `both` will enqueue harvest jobs on push.

