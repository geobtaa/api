# Make Tasks

Run these targets from the repository root. The Makefile loads `.env` when it
exists.

Use `make help` to print the authoritative target list from the current
Makefile.

## Code Quality

| Target | Purpose |
| --- | --- |
| `make lint` | Run `ruff check` on `backend/app/`, `backend/tests/`, and `backend/scripts/`. |
| `make format` | Run `ruff format` and `ruff check --fix` on backend code, tests, and scripts. |
| `make lint-check` | CI-style backend formatting and lint checks with no edits. |
| `make lint-test` | Run `lint-check` followed by the default backend test suite. |

## Backend Tests

Backend tests expect Docker database services to be available. The default test
target creates `btaa_geospatial_api_test` from `btaa_geospatial_api` when the
test database does not already exist.

| Target | Purpose |
| --- | --- |
| `make test` | Run backend tests with coverage and `COVERAGE_THRESHOLD` enforcement. |
| `make test-no-coverage` | Run backend tests without coverage threshold. |
| `make test-fast` | Run backend tests in parallel without coverage. |
| `make test-fresh-db` | Recreate the test database from the main local database, then run tests. |
| `make test-coverage-baseline` | Create a coverage baseline for comparison. |
| `make test-coverage-compare` | Compare current coverage with `BASELINE_COVERAGE`. |
| `make test-pmtiles-network` | Run the network-backed PMTiles raster thumbnail integration test. |

Common overrides:

| Variable | Default | Notes |
| --- | --- | --- |
| `COVERAGE_THRESHOLD` | `50` | Minimum coverage percentage for `make test`. |
| `PARALLEL_WORKERS` | `4` | pytest-xdist worker count; set to `0` for sequential test execution. |
| `WALLCLOCK_TIMEOUT_SECONDS` | `180` | Hard wall-clock timeout wrapper around pytest; set `0` only while debugging. |
| `TIMEOUT_GRACE_SECONDS` | `20` | Grace period after SIGINT before escalation. |
| `TIMEOUT_DUMP_STACKS` | `0` | Set `1` to print large stack dumps on timeout. |

## Frontend And CLI

Frontend lint, format, and tests are npm scripts run from `frontend/`; see
[frontend/README.md](frontend/README.md).

The public `/feedback` page posts to `/api/v1/feedback`. Deployed mail delivery
configuration is restricted operations material.

| Target | Purpose |
| --- | --- |
| `make frontend-reset` | Remove Vite cache and restart the Docker frontend service. Use after frontend dependency or Vite config changes. |
| `make cli-test` | Run the CLI test suite. |
| `make cli-lint` | Run CLI lint and format checks. |
| `make cli-format` | Format CLI code. |
| `make cli-build` | Build the CLI package. |
| `make cli-man` | Generate CLI man pages. |

## Public Docs

| Target | Purpose |
| --- | --- |
| `make docs-serve` | Serve the public MkDocs site at `http://localhost:8001`. |
| `make docs-build` | Build the public site into `mkdocs/site/`. |

## Local Data And Indexing

| Target | Purpose |
| --- | --- |
| `make ingest` | Ingest BTAA fixture records. Supports `FIXTURES_DIR` and `REPO_NAME`. |
| `make ingest-featured` | Ingest featured BTAA fixtures and reindex. |
| `make resource-aux-init` | Ensure resource auxiliary tables exist. |
| `make resource-cache-init` | Ensure durable generated resource/API response cache tables exist. |
| `make api-response-cache-init` | Ensure durable API response cache tables exist. |
| `make populate-distributions` | Rebuild legacy references, distributions, downloads, and assets. Supports `RESOURCE_ID` / `GBL_ADMIN_RESOURCE_ID`. |
| `make populate-data-dictionaries` | Populate resource data dictionaries from legacy tables. |
| `make backfill-distributions` | Backfill `resource_distributions` for resources with references but no normalized rows. |
| `make populate-relationships` | Populate `resource_relationships` from resource relationship fields. |
| `make reindex` | Build a versioned Elasticsearch index, atomically swap the alias, then prune old indexes. |
| `make reindex-benchmark` | Run the same atomic reindex with benchmark timing enabled. |
| `make verify-h3-index` | Verify H3 pyramid fields in Elasticsearch. |
| `make es-unblock` | Clear Elasticsearch read-only blocks after disk watermark incidents. |
| `make local-clear-search-cache` | Clear local search cache. |
| `make sitemap-generate` | Generate and cache sitemap XML for `/sitemap.xml`. |

Important reindex knobs:

| Variable | Default |
| --- | --- |
| `REINDEX_CHUNK_SIZE` | `2000` |
| `REINDEX_BULK_SIZE` | `2000` |
| `REINDEX_BULK_MAX_RETRIES` | `2` |
| `REINDEX_FAST_SETTINGS` | `true` |
| `REINDEX_FORCE_REPLICAS_ZERO` | `true` |
| `REINDEX_ALLOW_PARTIAL` | `false` |
| `REINDEX_PRUNE_OLD` | `true` |
| `REINDEX_RETAIN_PREVIOUS` | `1` |
| `REINDEX_REMOVE_LEGACY_INDEX` | `true` |
| `PUBLISHED_ONLY` | `false` |

`make reindex` indexes all resource rows by default. Public
Elasticsearch-backed queries apply `publication_state=published` and
`gbl_suppressed_b=false` at query time; set `PUBLISHED_ONLY=1` only for a narrowed
maintenance index build.

## Cache And Visual Assets

| Target | Purpose |
| --- | --- |
| `make clear_cache` | Flush Redis cache using `.env` credentials. |
| `make clear-thumbnail-cache` | Clear thumbnail cache for `RESOURCE_ID`. |
| `make thumbnail-completeness-report` | Report thumbnail completeness. Supports `THUMBNAIL_REPORT_SCOPE` and `THUMBNAIL_REPORT_FORMAT`. |
| `make prime-thumbnail-cache` | Prime thumbnail cache. |
| `make prime-static-map-cache` | Prime static-map cache. |
| `make prime-resource-cache` | Prime shared API resource representation cache. |
| `make prime-visual-caches` | Prime thumbnail and static-map caches. |
| `make refresh-resource-caches` | Purge and rehydrate selected resource/API caches. Use `REFRESH_APPLY=1` to apply. |
| `make api-response-cache-prune` | Prune expired durable API response cache rows. |
| `make visual-assets-export` | Export generated visual asset table data. |
| `make visual-assets-import` | Import generated visual asset data in a configured environment. |
| `make visual-assets-stream-import` | Stream generated visual asset data in a configured environment. |
| `make visual-assets-sync-all` | Export once, then import generated visual assets in configured environments. |

Common cache/priming variables:

| Variable | Notes |
| --- | --- |
| `RESOURCE_ID`, `RESOURCE_IDS` | Scope single-resource or multi-resource cache work. |
| `PRIME_LIMIT`, `PRIME_BATCH_SIZE` | Bound cache priming runs. |
| `PRIME_THUMBNAIL_CONCURRENCY`, `PRIME_STATIC_MAP_CONCURRENCY`, `PRIME_RESOURCE_CONCURRENCY` | Tune concurrency. |
| `PRIME_FORCE`, `PRIME_RETRY_FAILURES`, `PRIME_RETRY_PLACEHELD` | Control thumbnail/static-map retry behavior. |

## OpenGeoMetadata

| Target | Purpose |
| --- | --- |
| `make ogm-refresh` | Alias for `ogm-refresh-all`. |
| `make ogm-refresh-all` | Trigger harvest for all enabled weekly OGM repos. |
| `make ogm-refresh-repo OGM_REPO_NAME=...` | Trigger harvest for one repo. |
| `make ogm-status` | Show harvest status; supports `OGM_RUN_ID` for detail. |
| `make ogm-status-watch` | Poll harvest status continuously. |
| `make ogm-failures` | Show failed OGM harvest runs. |

`OGM_API_URL` defaults to `http://localhost:8000`. `OGM_STATUS_POLL_SECONDS`
defaults to `5`.

## Kithe Bridge And Blog Sync

| Target | Purpose |
| --- | --- |
| `make bridge-init` | Ensure bridge sync tables and resource aux tables exist. |
| `make bridge-sync` | Trigger a background bridge sync. |
| `make bridge-sync-batched` | Trigger batched full-resource bridge reconciliation. |
| `make bridge-cancel` | Cancel all bridge syncs and queued bridge sync tasks. |
| `make bridge-status` | Show bridge sync status. Supports `BRIDGE_RUN_ID` or `BRIDGE_RUNS_LIMIT`. |
| `make bridge-status-watch` | Poll bridge sync status continuously. |
| `make bridge-failures` | Show failed bridge sync runs. |
| `make blog-sync` | Trigger home page GIN blog sync. Use `RUN_NOW=1` for inline execution. |

Useful bridge variables:

| Variable | Default or use |
| --- | --- |
| `BRIDGE_API_URL` | Defaults to `http://localhost:8000`. |
| `BRIDGE_TRIGGER` | Defaults to `manual`. |
| `BRIDGE_LIMIT` | Optional max records to sync. |
| `BRIDGE_CHANGED_SINCE` | Optional incremental sync cutoff. |
| `RESOURCE_ID` / `BRIDGE_RESOURCE_ID` | Single-record sync scope. |
| `BRIDGE_BATCH_TRIGGER` | Batched reconciliation trigger label. Defaults to `manual_batched`. |
| `BRIDGE_BATCH_SIZE` | Batched reconciliation resources per Celery task. Defaults to `500`, capped at `1000`. |
| `BRIDGE_RESOURCE_SCOPE` | Batched reconciliation source: `all`, `published`, or `bridge_active`. Defaults to `all`. |
| `BRIDGE_MAX_RESOURCES` | Optional cap for trial batched reconciliation runs. |
| `BRIDGE_STATUS_POLL_SECONDS` | Defaults to `5`. |
| `KITHE_BRIDGE_URL` | Upstream Kithe Bridge endpoint used by the worker. |
| `KITHE_BRIDGE_VERIFY_SSL` | Defaults to `true` in code. Set to `false` only for temporary hostname/certificate mismatches. |
| `BRIDGE_BATCH_CACHE_REFRESH_ENABLED` | Defaults to `false`; set to `true` only when a batched run should also invalidate and rewarm changed resource caches. |

Remote bridge reconciliation, monitoring, retry tuning, and cache refresh
procedures are restricted operations material. Keep public notes focused on
local targets and code behavior.

Bridge resources that disappear from Kithe Bridge are deleted locally, not
converted to suppressed or retired records. A full bridge sync can detect
missing records from a complete upstream snapshot, and
`make bridge-sync RESOURCE_ID=<id>` deletes the local bridge-managed record when
that upstream record is absent. A delta sync with `BRIDGE_CHANGED_SINCE` cannot
infer deletions because unchanged records are intentionally absent from the
delta window. The deletion guard is limited to bridge-managed rows
(`bridge_resource_state`) or legacy Kithe-origin rows with `resources.import_id`.

Environment-specific Bridge endpoints and verification overrides are restricted
operations material.

## Analytics

| Target | Purpose |
| --- | --- |
| `make analytics-maintenance` | Run analytics partitioning, rollups, and retention maintenance. |
| `make analytics-size-report` | Show analytics table and partition sizes. |

## Database Sync And Legacy GBL Admin Import

Some database import targets can be destructive outside local development.
Deployed database sync procedures are restricted operations material.

| Target | Purpose |
| --- | --- |
| `make db-export` | Export local ParadeDB to `tmp/btaa_geospatial_api_export.sql.gz` and build the db-sync archive. |
| `make db-import` | Import the db-sync archive in a configured environment. Deployed use is restricted operations material. |
| `make db-sync` | Run `db-export` then `db-import`. |
| `make gbl-admin-db-download` | Download the latest GBL Admin production dump. |
| `make gbl-admin-db-unzip` | Decompress the downloaded GBL Admin dump. |
| `make gbl-admin-db-restore` | Restore GBL Admin dump to local ParadeDB. |
| `make gbl-admin-db-sync` | Download and restore the GBL Admin dump. |
| `make gbl-admin-db-add-latest-btaa-fields` | Add latest BTAA schema fields to resources. |
| `make gbl-admin-db-import-resources` | Import resources from the GBL Admin bridge. |
| `make gbl-admin-db-import-all` | Run the full GBL Admin import pipeline. |

By default, `db-import` preserves API key and analytics tables:
`api_service_tiers`, `api_keys`, `analytics_api_usage_logs`,
`analytics_searches`, `analytics_search_impressions`, and `analytics_events`,
plus their owned sequences.

## Remote Operations

Remote deployment, cache, backup, indexing, bridge, cron, worker, and network
operations are restricted operations material. Public docs intentionally do not
list destination names, remote target examples, secret-loading behavior, or
production command sequences.

## Performance Tests

| Target | Purpose |
| --- | --- |
| `make k6-smoke` | Run a one-iteration smoke test against frontend and API. |
| `make k6-stress` | Run concurrent frontend and API stress traffic. |
| `make k6-endpoint-capacity` | Run a fixed-request-rate capacity test for one endpoint. |

Useful variables include `K6_BASE_URL`, `K6_QUERY`, `K6_RESOURCE_ID`,
`K6_ENABLE_FRONTEND`, `K6_ENABLE_API`, endpoint target and request-rate
variables, and p95/p99 threshold variables. Keep API keys and deployed target
details in restricted operations docs. See
[backend/performance_testing.md](backend/performance_testing.md).

## Troubleshooting

If `make reindex` fails with a flood-stage or read-only index error:

```bash
make es-unblock
make reindex
```

If frontend chunks 504 or stale after dependency/Vite changes:

```bash
make frontend-reset
```

Then hard-refresh the browser.

If this file drifts, regenerate the target list with:

```bash
rg -n "^[a-zA-Z0-9_-]+:.*##" Makefile
```
