# OpenGeoMetadata (OGM) harvesting (admin suite)

This document describes how to ingest OpenGeoMetadata GitHub repos (e.g. `OpenGeoMetadata/edu.stanford.purl`) into the BTAA API, keep them refreshed, and expose them via `ogm_repo[]` filtering and faceting.

During harvest, imported records now update three local DB surfaces automatically:

- `resources`
- `resource_distributions` (from `dct_references_s`)
- `resource_relationships` (from fields like `dct_isPartOf_sm`, `pcdm_memberOf_sm`, etc.)

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

## Local Setup

### 1) Database migration

Run the idempotent migration that ensures the `ogm_*` tables exist:

```bash
docker compose exec api bash -lc "cd /app/backend && python db/migrations/create_ogm_harvest_tables.py"
```

### 2) Elasticsearch reindex (required for `ogm_repo` facet/filter)

The ES mapping includes `ogm_repo`, so rebuild the local index after applying
the migration:

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
  -X POST "http://localhost:8000/api/v1/admin/reindex"
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

## Configure Local Env Vars

Deployed webhook configuration and shared-secret setup are restricted operations
material.

- **Optional paths**:
  - `OGM_CHECKOUT_PATH`: where repos are cloned/pulled (default: `data/opengeometadata`)
  - `OGM_DUMP_BASE_DIR`: where dumps are written (default: `data/harvest_dumps/ogm`)

## Using the system

### 1) Add/watch repos

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" -X PATCH \
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
- This script checks whether each repo has a `metadata-aardvark/` directory.
- If the directory is missing, it disables the repo and records that state.
- If the directory is present, it enables the repo with the default watch mode.
- For better GitHub rate limits, pass a local GitHub token.

### 2) Trigger a harvest

Single repo:

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" -X POST \
  "http://localhost:8000/api/v1/admin/ogm/harvest" \
  -H "Content-Type: application/json" \
  -d '{"ogm_repo_name":"edu.stanford.purl","ogm_trigger":"manual"}'
```

This updates Postgres immediately, including distributions and relationship rows for the touched records.
If you need local Elasticsearch/search results to reflect the new or changed records right away, run `make reindex` after the harvest completes.

All enabled weekly repos:

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" -X POST \
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

Deployed GitHub webhook payload URLs, shared secrets, and validation procedures
are restricted operations material.

Only repos with a webhook-enabled watch mode enqueue harvest jobs on push.
