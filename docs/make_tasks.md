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
- `make clear_cache`: flush Redis cache DB (`REDIS_DB`, requires `REDIS_PASSWORD`)

## Frontend (Docker)

- `make frontend-reset`: clear Vite cache in `frontend-dev` and restart the dev server. Use after changing `optimizeDeps` or when seeing "Failed to fetch dynamically imported module" or 504 "Outdated Optimize Dep". **After running it, do a hard refresh** (Ctrl+Shift+R or Cmd+Shift+R) or open the app in an incognito window—otherwise the browser may keep requesting old chunk URLs and still get 504s.
- `make db-export`: export local DB → `tmp/btaa_geospatial_api_export.sql.gz`
- `make db-import`: import dump to remote via Kamal (destructive)
- `make db-sync`: `db-export` + `db-import`

