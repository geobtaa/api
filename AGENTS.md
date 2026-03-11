# AGENTS.md — Context for AI agents

This file gives agents a single reference for how to lint, format, test, run Docker, use the Makefile, and perform ingest/index and OpenGeoMetadata operations. For deeper detail, see the `docs/` tree.

---

## Lint, format, and test

### Backend (Python)

- **Lint** (check only): `make lint` — runs `ruff check` on `backend/app/`, `backend/tests/`, `backend/scripts/`.
- **Format** (fix in-place): `make format` — runs `ruff format` and `ruff check --fix` on the same paths.
- **Lint check** (CI-style, no edits): `make lint-check` — use before committing or in CI.
- **Tests**: From project root, with Docker services up (so the test DB exists):
  - `make test` — full suite with coverage (threshold 50% by default; override with `COVERAGE_THRESHOLD=25 make test`).
  - `make test-no-coverage` — tests without coverage threshold (debugging).
  - `make test-fast` — parallel, no coverage (fastest).
  - `make test-fresh-db` — drop and recreate `btaa_geospatial_api_test` from `btaa_geospatial_api`, then run tests separately.
  - `make lint-test` — `lint-check` then `test`.
  - `make test-pmtiles-network` — PMTiles raster thumbnail integration test (proves harvest works; requires network). The fixture `b1g_PJxxfKgpqpUT` uses MVT PMTiles which may fail; this test uses a known-good raster URL.

Test env vars (optional): `PARALLEL_WORKERS` (default 4), `WALLCLOCK_TIMEOUT_SECONDS` (default 60), `TIMEOUT_GRACE_SECONDS`, `TIMEOUT_DUMP_STACKS`. See `Makefile` for details.

### Frontend (TypeScript/React)

Commands are run from `frontend/` (or via `npm run` in that directory):

- **Lint**: `npm run lint` (check), `npm run lint:fix` (auto-fix).
- **Format**: `npm run format` (write), `npm run format:check` (check only).
- **Test**: `npm test` (Vitest once), `npm run test:watch`, `npm run test:coverage`. Config: `frontend/vitest.config.ts`, `frontend/setupTests.ts`.

Frontend lint/format config: `frontend/eslint.config.js`, Prettier defaults. See `docs/frontend/linting-and-formatting.md` and `docs/frontend/testing.md` for full details.

---

## Docker

### Services (from `docker-compose.yml`)

| Service         | Container name                    | Purpose                          |
|----------------|------------------------------------|----------------------------------|
| `api`          | btaa-geospatial-api-app           | FastAPI app (port 8000)          |
| `frontend-dev` | btaa-geospatial-api-frontend-dev  | Vite dev server (port 3000)      |
| `elasticsearch`| btaa-geospatial-api-elasticsearch | Elasticsearch 9 (port 9200)      |
| `paradedb`     | btaa-geospatial-api-paradedb      | PostgreSQL (ParadeDB)             |
| `redis`        | btaa-geospatial-api-redis         | Redis (cache + Celery broker)    |
| `celery_worker`| btaa-geospatial-api-celery        | Celery worker                    |
| `flower`       | btaa-geospatial-api-flower        | Flower UI (port 5555)             |

Require `.env` (e.g. `POSTGRES_PASSWORD`, `REDIS_PASSWORD`). Copy from `.env.example` if needed.

### Start / stop

- Start all: `docker compose up -d`
- Stop all: `docker compose down`
- Logs: `docker compose logs -f [service]`

### Rebuild a single service

Rebuild and recreate one service (e.g. after Dockerfile or dependency changes):

```bash
docker compose build api
docker compose up -d api
```

Or rebuild and start in one step:

```bash
docker compose up -d --build api
```

Examples: `api`, `frontend-dev`, `celery_worker`, `flower` (all use the project Dockerfile where applicable). `elasticsearch`, `paradedb`, `redis` are image-based and usually don’t need a local rebuild.

### Restart a single service

Restart without rebuilding (e.g. after code or env changes that are mounted):

```bash
docker compose restart api
docker compose restart celery_worker
docker compose restart frontend-dev
```

After changing frontend deps or Vite config, use `make frontend-reset` to clear the Vite cache and restart `frontend-dev`; then hard-refresh the browser.

---

## Makefile

Run from the **project root**. Key targets:

| Target                 | Description |
|------------------------|-------------|
| `make lint`            | Backend: ruff check only. |
| `make format`          | Backend: ruff format + fix. |
| `make lint-check`      | Backend: CI-style lint/format check (no edits). |
| `make test`            | Backend tests with coverage (needs Docker DB). |
| `make test-no-coverage`| Backend tests, no coverage threshold. |
| `make test-fast`       | Backend tests, parallel, no coverage. |
| `make test-fresh-db`   | Recreate test DB from main DB. |
| `make lint-test`       | `lint-check` then `test`. |
| `make reindex`         | Atomic local reindex using versioned index + alias swap, then clear local search cache. |
| `make reindex-benchmark` | Run atomic local reindex with benchmark timing output enabled. |
| `make kamal-reindex`   | Atomic reindex on Kamal with versioned index + alias swap; auto-runs `kamal-clear-cache`. |
| `make verify-h3-index` | Verify H3 pyramid fields in Elasticsearch. |
| `make kamal-clear-cache` | Clear remote API cache on Kamal (`KAMAL_CACHE_TYPE`, default `search`). |
| `make clear_cache`     | Flush Redis cache (needs `REDIS_PASSWORD` in `.env`). |
| `make frontend-reset`  | Clear Vite cache and restart frontend-dev. |
| `make db-export`       | Export ParadeDB to `tmp/btaa_geospatial_api_export.sql.gz`. |
| `make db-import`       | Import that dump to remote (Kamal); destructive. |
| `make db-sync`         | `db-export` then `db-import`. |

See `docs/make_tasks.md` for overrides (e.g. `COVERAGE_THRESHOLD`, `PARALLEL_WORKERS`).

---

## Ingest and index

### Ingesting new items

- **BTAA fixture JSONs** (e.g. from `backend/data/fixtures/btaa_featured_resources/`):  
  Uses the same OGM importer as harvest. From project root with API env (or inside API container):
  ```bash
  cd backend && python scripts/ingest_btaa_fixtures.py
  ```
  Script reads from a fixtures directory (see `ingest_btaa_fixtures.py` for path/repo name).

- **GBL fixtures**:  
  `backend/scripts/ingest_gbl_fixtures.py` — run from `backend/` with same env as API.

- **OpenGeoMetadata (OGM)**:  
  Repos are harvested via Celery (clone/pull GitHub, then import). See “OpenGeoMetadata reharvest” below. One-time bulk seed of repo list:  
  `docker compose exec api bash -lc "cd /app/backend && python scripts/populate_ogm_repos.py"`  
  (optional: `GITHUB_TOKEN` for rate limits).

### Indexing (Elasticsearch)

- **Reindex all resources locally** (safe atomic cutover):  
  `make reindex`  
  or  
  `docker compose exec api bash -lc "cd /app/backend && python scripts/reindex_atomic.py"`

- **Atomic reindex on Kamal** (safe cutover):  
  `make kamal-reindex`  
  Builds a versioned index, atomically swaps alias `ELASTICSEARCH_INDEX`, keeps one previous versioned index by default, then clears remote API cache.

- **Verify H3 pyramid fields** after reindex:  
  `make verify-h3-index`  
  or  
  `docker compose exec api bash -lc "cd /app/backend && python scripts/verify_h3_index.py"`

Backend scripts for one-off or debug indexing: `backend/scripts/reindex.py`, `backend/scripts/reindex_atomic.py`, `simple_bulk_index.py`, `run_index.py`. See `docs/backend/scripts.md` and `docs/backend/ogm_harvesting.md`.

---

## OpenGeoMetadata reharvest

- **Add or enable a repo** (e.g. weekly):  
  `PATCH /api/v1/admin/ogm/repos/{repo_name}` with `{"ogm_enabled":true,"ogm_watch_mode":"weekly"}` (Basic Auth: admin/changeme by default).

- **Trigger harvest**  
  - Single repo:  
    `POST /api/v1/admin/ogm/harvest` with `{"ogm_repo_name":"edu.stanford.purl","ogm_trigger":"manual"}`  
  - All enabled weekly repos:  
    `POST /api/v1/admin/ogm/harvest` with `{"ogm_all":true,"ogm_trigger":"weekly"}`  

- **After code/config changes** that affect OGM: restart `api` and `celery_worker` (and optionally `flower`):  
  `docker compose restart api celery_worker`

Full flow (migrations, reindex, webhook, dumps): `docs/backend/ogm_harvesting.md`.

---

## Best practices for agents

- **Run backend tests and Makefile targets from the project root**; ensure Docker is up so the test DB exists (`make test` clones from `btaa_geospatial_api` if needed).
- **Run frontend lint/format/test from `frontend/`** (or via npm there).
- **Prefer the Makefile** for backend lint, format, test, reindex, cache, and DB export/import so behavior and env are consistent.
- **Don’t duplicate long docs here** — link to `docs/` (e.g. `docs/backend/ogm_harvesting.md`, `docs/frontend/testing.md`, `docs/make_tasks.md`) for procedures and rationale.
- **Secrets and env**: `.env` is not committed; use `.env.example` as a template. Kamal secrets live in `.kamal/secrets` (not committed).
- **When changing frontend deps or Vite config**: run `make frontend-reset` and have the user hard-refresh (or use an incognito window) to avoid 504s on old chunk URLs.
