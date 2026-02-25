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

- `make reindex`: atomic local reindex using a versioned index + alias swap (non-destructive build + atomic cutover). Defaults favor safety: swap is blocked on indexing errors/count mismatch, and one previous versioned index is retained. After a successful swap, it automatically clears local `search` cache.
  - Useful local tuning overrides: `REINDEX_CHUNK_SIZE`, `REINDEX_BULK_SIZE`, `REINDEX_BULK_MAX_RETRIES`, `REINDEX_FAST_SETTINGS`, `REINDEX_FORCE_REPLICAS_ZERO`, `REINDEX_RETAIN_PREVIOUS`.
  - Benchmark mode: `make reindex-benchmark` (or `REINDEX_BENCHMARK=true make reindex`) prints per-chunk timings and a final phase summary.
- `make ogm-refresh`: trigger OpenGeoMetadata harvest for all enabled weekly repos (`POST /api/v1/admin/ogm/harvest` with `{"ogm_all":true,"ogm_trigger":"weekly"}`).
- `make ogm-refresh-repo OGM_REPO_NAME=edu.stanford.purl`: trigger OpenGeoMetadata harvest for one repo (`{"ogm_repo_name":"...","ogm_trigger":"manual"}`).
- `make ogm-status`: show current OGM harvest runs (`GET /api/v1/admin/ogm/harvest/runs`).
- `make ogm-status OGM_RUN_ID=<run_id>`: show detail for one run (`GET /api/v1/admin/ogm/harvest/runs/{run_id}`).
- `make ogm-status-watch [OGM_RUN_ID=<run_id>] [OGM_STATUS_POLL_SECONDS=5]`: poll OGM status until you stop it (`Ctrl+C`).
- `make ogm-failures`: show only failed OGM harvest runs with `ogm_error` details.
- These OGM make tasks run `curl` from inside the `api` container and use that container's `ADMIN_USERNAME` / `ADMIN_PASSWORD`, so they stay aligned with the live API auth config.
- `make verify-h3-index`: query Elasticsearch to verify H3 pyramid fields (`h3_res2`–`h3_res8`, `geo_or_near_global`) are present (run after reindex)
- `make kamal-reindex`: atomic remote reindex on Kamal using a versioned index + alias swap (runs once by default with `--roles web`; source `.kamal/secrets` first). On success, this now also runs `make kamal-clear-cache`.
  - Useful overrides: `KAMAL_REINDEX_RETAIN_PREVIOUS=1` (default), `KAMAL_REINDEX_PRUNE_OLD=true` (default), `KAMAL_REINDEX_ALLOW_PARTIAL=false` (default; blocks swap on indexing/count mismatch), `KAMAL_REINDEX_REMOVE_LEGACY_INDEX=true` (default; one-time migration from legacy non-alias index name).
- `make kamal-verify-h3-index`: verify H3 fields on remote Kamal app containers (runs once by default with `--roles web`; source `.kamal/secrets` first)
- `make kamal-clear-cache`: clear remote API cache on Kamal (defaults to `KAMAL_CACHE_TYPE=search`). Uses `KAMAL_API_URL` if set, otherwise falls back to `APPLICATION_URL` from Kamal env. Override with `make kamal-clear-cache KAMAL_CACHE_TYPE=all` (or `suggest`/`item`).
- `make ingest`: ingest BTAA fixture JSON files into the DB (runs inside the `api` Docker container). Default: `data/fixtures/btaa_fixtures_data`. Override with `make ingest FIXTURES_DIR=btaa_featured_resources REPO_NAME=btaa_featured_resources`. After ingest, run `make reindex` to index into Elasticsearch.
- `make ingest-featured`: ingest `data/fixtures/btaa_featured_resources` into the DB and then reindex into Elasticsearch (one-step for featured resources).
- `make clear_cache`: flush Redis cache DB (`REDIS_DB`, requires `REDIS_PASSWORD`)

## Frontend (Docker)

- `make frontend-reset`: clear Vite cache in `frontend-dev` and restart the dev server. Use after changing `optimizeDeps` or when seeing "Failed to fetch dynamically imported module" or 504 "Outdated Optimize Dep". **After running it, do a hard refresh** (Ctrl+Shift+R or Cmd+Shift+R) or open the app in an incognito window—otherwise the browser may keep requesting old chunk URLs and still get 504s.
- `make db-export`: export local DB → `tmp/btaa_geospatial_api_export.sql.gz`
- `make db-import`: import dump to remote via Kamal (destructive)
- `make db-sync`: `db-export` + `db-import`
- **GBL Admin production sync**: `make gbl-admin-db-sync` downloads the latest `pgdump-geoportal_production-*.sql.gz` from the GBL Admin server and restores it into local ParadeDB. It streams from the compressed file (no decompression to disk), so you only need space for the `.gz`. The production role `geomg` is created locally so restore does not fail on OWNER clauses. If ParadeDB crashes during restore (e.g. OOM), increase Docker memory for the `paradedb` service and re-run; you may need to drop the partial DB first: `docker compose exec paradedb psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS geoportal_production_YYYYMMDD;"`.
- **GBL Admin add latest BTAA fields**: `make gbl-admin-db-add-latest-btaa-fields` adds latest BTAA compatibility columns to `resources`.
- **GBL Admin import resources**: `make gbl-admin-db-import-resources` imports from `kithe_to_resources_bridge` into `btaa_geospatial_api` (`OLD_DB_NAME` auto-detected unless provided).
- **GBL Admin populate distributions**: `make populate-distributions` migrates legacy `document_distributions` into `resource_distributions` (`OLD_DB_NAME` auto-detected unless provided).
- **GBL Admin populate data dictionaries**: `make populate-data-dictionaries` migrates legacy `document_data_dictionaries` and `document_data_dictionary_entries` into `resource_data_dictionaries` and `resource_data_dictionary_entries`.
- **GBL Admin full import pipeline**: `make gbl-admin-db-import-all` runs latest-field migration, resource import, distribution migration, data-dictionary migration, relationship population, and reindex.
- `make populate-relationships`: populate `resource_relationships` from `resources` (run after ingest or when relationship columns change). See `docs/backend/relationships.md`.

## GBL Admin migration runbook (old prod -> reindex)

Use this sequence when rebuilding from the old GBL Admin production snapshot.

1. Restore latest old-prod DB snapshot and build bridge materialized view:
   ```bash
   make gbl-admin-db-sync
   ```

2. Run full import pipeline into API DB, including distributions/relationships and reindex:
   ```bash
   make gbl-admin-db-import-all
   ```

If you need to pin a specific restored old DB instead of auto-detect:

```bash
OLD_DB_NAME=geoportal_production_YYYYMMDD make gbl-admin-db-import-all
```

Equivalent explicit step-by-step (instead of the all-in-one target):

```bash
make gbl-admin-db-add-latest-btaa-fields
make gbl-admin-db-import-resources
make populate-distributions
make populate-data-dictionaries
make populate-relationships
make reindex
```

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

