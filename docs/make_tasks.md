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

- `make reindex`: reindex resources into Elasticsearch
- `make clear_cache`: flush Redis cache DB (`REDIS_DB`, requires `REDIS_PASSWORD`)
- `make db-export`: export local DB → `tmp/btaa_geospatial_api_export.sql.gz`
- `make db-import`: import dump to remote via Kamal (destructive)
- `make db-sync`: `db-export` + `db-import`

