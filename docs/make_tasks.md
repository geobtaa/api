# Make Tasks

Run these targets from the repository root. The Makefile loads `.env` when it
exists and loads Kamal secrets from `.kamal/secrets-common` plus
`.kamal/secrets.<KAMAL_DEST>` when those files exist.

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

The public `/feedback` page posts to `/api/v1/feedback` and sends mail with the
same sendmail/SMTP conventions as other app mail. Configure
`FEEDBACK_EMAIL_ENABLED`, `FEEDBACK_RECIPIENTS`, `FEEDBACK_FROM`, and
`FEEDBACK_DELIVERY`; production typically uses `FEEDBACK_DELIVERY=sendmail`.

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
| `make visual-assets-import` | Import generated visual asset data to `KAMAL_DEST`. |
| `make visual-assets-stream-import` | Stream generated visual asset data directly to `KAMAL_DEST`. |
| `make visual-assets-sync-all` | Export once, then import generated visual assets to `VISUAL_ASSETS_DESTS`. |

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

For remote reconciliation, run `make kamal-bridge-sync-batched KAMAL_DEST=dev1`
and then monitor with `make kamal-bridge-status-watch KAMAL_DEST=dev1`. Run
`make kamal-reindex` after the batched sync completes so Elasticsearch reflects
the corrected database rows. The batched target reconciles existing local IDs;
keep the normal bridge crawl/delta sync for discovering newly added Bridge
records. Batched resource fetches retry transient Kithe Bridge `5xx` responses
as a group before counting a record error; tune with
`KITHE_BRIDGE_BATCH_FETCH_5XX_MAX_ATTEMPTS` and
`KITHE_BRIDGE_BATCH_FETCH_5XX_RETRY_BACKOFF_SECONDS` when an upstream outage
requires slower or faster retry pacing. A batched run that completes with
record errors now finishes with `bridge_status=failed`, so do not reindex from
that run until the failed records have been retried.

June 2026 bridge cutover note: the Kithe Bridge server moved to
`https://geomg.lib.umn.edu/`, and Kamal points `KITHE_BRIDGE_URL` at the
collection endpoint `https://geomg.lib.umn.edu/api/kithe_bridge` with
`KITHE_BRIDGE_VERIFY_SSL=true`. Set verification to `false` only for a
temporary hostname/certificate mismatch during an infrastructure change.

## Analytics

| Target | Purpose |
| --- | --- |
| `make analytics-maintenance` | Run analytics partitioning, rollups, and retention maintenance. |
| `make analytics-size-report` | Show analytics table and partition sizes. |

## Database Sync And Legacy GBL Admin Import

These targets can be destructive on the destination named by `KAMAL_DEST`.
Confirm the target environment before running remote imports.

| Target | Purpose |
| --- | --- |
| `make db-export` | Export local ParadeDB to `tmp/btaa_geospatial_api_export.sql.gz` and build the db-sync archive. |
| `make db-import` | Import the db-sync archive to a Kamal destination. Preserves local API/analytics tables by default. |
| `make db-sync` | Run `db-export` then `db-import`. |
| `make gbl-admin-db-download` | Download the latest GBL Admin production dump. |
| `make gbl-admin-db-unzip` | Decompress the downloaded GBL Admin dump. |
| `make gbl-admin-db-restore` | Restore GBL Admin dump to local ParadeDB. |
| `make gbl-admin-db-sync` | Download and restore the GBL Admin dump. |
| `make gbl-admin-db-add-latest-btaa-fields` | Add latest BTAA schema fields to resources. |
| `make gbl-admin-db-import-resources` | Import resources from the GBL Admin bridge. |
| `make gbl-admin-db-import-all` | Run the full GBL Admin import pipeline. |

By default, `db-import` preserves destination-local API key and analytics tables:
`api_service_tiers`, `api_keys`, `analytics_api_usage_logs`,
`analytics_searches`, `analytics_search_impressions`, and `analytics_events`,
plus their owned sequences.

## Kamal Remote Operations

Set `KAMAL_DEST=dev1`, `dev2`, or `prd`. The default is `dev1`.

| Target | Purpose |
| --- | --- |
| `make kamal-reindex` | Run atomic Elasticsearch reindex on a Kamal destination. |
| `make kamal-verify-h3-index` | Verify H3 index fields on a Kamal destination. |
| `make kamal-clear-cache` | Clear remote cache. `KAMAL_CACHE_TYPE=search|resource|suggest|map|all`. |
| `make kamal-blog-sync` | Trigger remote home page blog sync. Use `RUN_NOW=1` for inline execution. |
| `make kamal-purge-home-blog-cache` | Purge home blog/home endpoint cache remotely. |
| `make kamal-backup-postgres` | Run the production-gated Postgres S3 backup in the cron container. |
| `make kamal-backup-elasticsearch` | Run the production-gated Elasticsearch S3 snapshot in the cron container. |
| `make kamal-backup-list-elasticsearch` | List Elasticsearch snapshots for the target destination. |
| `make kamal-bridge-status` | Show bridge status remotely. |
| `make kamal-bridge-status-watch` | Poll remote bridge status. |
| `make kamal-cron-debug` | Inspect cron container crontab, timezone, and env. |
| `make kamal-cron-test-bridge` | Run the bridge sync cron trigger inside the cron container. |
| `make kamal-worker-logs` | Tail Celery worker logs. |
| `make kamal-network-sanity` | Check outbound and self-FQDN networking on a Kamal host/container. |
| `make kamal-prime-thumbnail-cache` | Prime thumbnail cache remotely. |
| `make kamal-prime-static-map-cache` | Prime static-map cache remotely. |
| `make kamal-prime-visual-caches` | Prime remote thumbnail and static-map caches. |
| `make kamal-prime-resource-cache` | Prime remote shared API resource representation cache. |
| `make kamal-thumbnail-completeness-report` | Report remote thumbnail completeness. |
| `make kamal-api-response-cache-init` | Ensure durable API response cache tables remotely. |
| `make kamal-api-response-cache-prune` | Prune expired durable API response rows remotely. |
| `make kamal-refresh-resource-caches` | Purge and rehydrate selected remote resource/API caches. |

Kamal reindex knobs mirror local reindexing with the `KAMAL_REINDEX_*` prefix.
`make kamal-backup-elasticsearch` uses `KAMAL_BACKUP_RETAIN_COUNT` as a manual
fallback when the destination environment does not set `BACKUP_RETENTION_COUNT`.

## Performance Tests

| Target | Purpose |
| --- | --- |
| `make k6-smoke` | Run a one-iteration smoke test against frontend and API. |
| `make k6-stress` | Run concurrent frontend and API stress traffic. |
| `make k6-endpoint-capacity` | Run a fixed-request-rate capacity test for one endpoint. |

Useful variables include `K6_BASE_URL`, `K6_QUERY`, `K6_RESOURCE_ID`,
`K6_API_KEY`, `K6_ENABLE_FRONTEND`, `K6_ENABLE_API`, endpoint target and request
rate variables, and p95/p99 threshold variables. See
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

If a remote bridge task is queued but does not run:

```bash
make kamal-worker-logs KAMAL_DEST=dev1
make kamal-cron-debug KAMAL_DEST=dev1
make kamal-bridge-status KAMAL_DEST=dev1
```

If this file drifts, regenerate the target list with:

```bash
rg -n "^[a-zA-Z0-9_-]+:.*##" Makefile
```
