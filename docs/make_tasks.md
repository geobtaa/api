# Make tasks (developer reference)

This project uses a `Makefile` to wrap common developer/ops tasks.

> If you’re not a developer: you can ignore this file. The main `README.md` is written for non-technical users.

## Code quality

- `make lint`: run Ruff lint on backend code
- `make format`: format + auto-fix with Ruff
- `make lint-check`: CI-style formatting + lint checks (no modifications)

## Tests

- `make test`: run tests with coverage (defaults: `COVERAGE_THRESHOLD=50`, `PARALLEL_WORKERS=4`)
- `make test-no-coverage`: run tests without coverage threshold
- `make test-fast`: fastest local tests (parallel, no coverage)
- `make test-fresh-db`: drop/recreate `btaa_geospatial_api_test` (cloned from `btaa_geospatial_api`)
- `make lint-test`: `lint-check` + `test`

Overrides:

- `COVERAGE_THRESHOLD=25 make test`
- `PARALLEL_WORKERS=0 make test` (disable xdist)

## Data + ops

- `make reindex`: reindex resources into Elasticsearch (same logic as hitting `/api/v1/admin/reindex`)
- `make verify-h3-index`: query Elasticsearch to verify H3 pyramid fields (`h3_res2`–`h3_res8`, `geo_or_near_global`) are present (run after reindex)
- `make ingest`: ingest BTAA fixture JSON files into the DB (runs inside the `api` Docker container). Default: `data/fixtures/btaa_fixtures_data`. Override with `make ingest FIXTURES_DIR=btaa_featured_resources REPO_NAME=btaa_featured_resources`. After ingest, run `make reindex` to index into Elasticsearch.
- `make ingest-featured`: ingest `data/fixtures/btaa_featured_resources` into the DB and then reindex into Elasticsearch (one-step for featured resources).
- `make clear_cache`: flush Redis cache DB (`REDIS_DB`, requires `REDIS_PASSWORD`)

## Frontend (Docker)

- `make frontend-reset`: clear Vite cache in `frontend-dev` and restart the dev server. Use after changing `optimizeDeps` or when seeing "Failed to fetch dynamically imported module" or 504 "Outdated Optimize Dep". **After running it, do a hard refresh** (Ctrl+Shift+R or Cmd+Shift+R) or open the app in an incognito window—otherwise the browser may keep requesting old chunk URLs and still get 504s.
- `make db-export`: export local DB → `tmp/btaa_geospatial_api_export.sql.gz`
- `make db-import`: import dump to remote via Kamal (destructive)
- `make db-sync`: `db-export` + `db-import`
- `make populate-relationships`: populate `resource_relationships` from `resources` (run after ingest or when relationship columns change). See `docs/backend/relationships.md`.

## Troubleshooting

### `make reindex` fails: "flood stage disk watermark exceeded" / indices read-only

Elasticsearch blocks writes when the disk passes the flood-stage watermark (e.g. 95% full) so the node doesn’t fill the disk. Reindex will fail until there is more free space or the threshold is relaxed.

**Options:**

1. **Free disk space** (recommended): Remove unneeded data, clean Docker (`docker system prune -a` if appropriate), or move the ES data volume to a disk with more space. The watermark is configured in `docker-compose.yml` for the `elasticsearch` service (`cluster.routing.allocation.disk.watermark.*`).

2. **After freeing disk space**, clear the read-only block so writes (e.g. reindex) work again:
   ```bash
   make es-unblock
   ```
   Then run `make reindex` as needed.

3. **Relax watermarks for local dev only**: In `docker-compose.yml`, under the `elasticsearch` service env, you can temporarily set e.g. `cluster.routing.allocation.disk.watermark.flood_stage=99.9%` (or disable with `cluster.routing.allocation.disk.threshold_enabled=false`). Only do this on a dev machine with enough free space; otherwise you risk filling the disk.

4. **Use a remote Elasticsearch** with more space: Point the app at another ES (e.g. via `ELASTICSEARCH_URL` and run reindex there).

