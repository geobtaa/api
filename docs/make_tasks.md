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
- `make k6-smoke`: run a one-iteration k6 smoke test against both the public frontend and the backend API. Defaults to `K6_BASE_URL=https://lib-btaageoapi-dev-app-01.oit.umn.edu`, auto-discovers a resource id from search results unless `K6_RESOURCE_ID` is provided, discovers live facet values from the same seed search, and writes `tmp/k6/smoke-summary.json`.
- `make k6-stress`: run the concurrent k6 stress suite with separate frontend-page and direct-API scenarios. Defaults target `dev1`, ramp frontend traffic to `K6_FRONTEND_TARGET_VUS=4`, ramp API traffic to `K6_API_TARGET_VUS=8`, and write `tmp/k6/stress-summary.json`. The API side now includes direct faceted searches plus `/api/v1/search/facets/<facet_name>` calls, and the frontend side includes faceted `/search` page requests plus the hydrated `/search/results` JSON request through the keyed frontend BFF route. Useful overrides include `K6_QUERY`, `K6_RESOURCE_ID`, `K6_ENABLE_FRONTEND=0`, `K6_ENABLE_API=0`, `K6_CACHE_BUST_SEARCH=1` for uncached search/facet miss-path runs, `K6_ENDPOINT_BREAKDOWN=1` for per-endpoint p95/p99 summary rows, plus `K6_FRONTEND_*` and `K6_API_*`.

Overrides:

- `COVERAGE_THRESHOLD=25 make test`
- `PARALLEL_WORKERS=0 make test` (disable xdist)

## Data + ops

- `make resource-aux-init`: ensure `resource_downloads`, `resource_licensed_accesses`, `resource_assets`, durable `generated_visual_assets` / `generated_visual_asset_links`, durable `generated_resource_representations`, and durable `generated_api_responses` tables exist before bridge/legacy sync or cache priming work.
- `make visual-assets-export`: export only local durable generated visual asset rows to `tmp/generated_visual_assets.dump`, and write a sidecar manifest to `tmp/generated_visual_assets.manifest` with the row counts and byte totals used for later verification. Use this after local visual-cache priming finishes. Override `VISUAL_ASSETS_PG_DUMP_COMPRESS=0|1|...` when you want to trade archive size for faster dump speed; the default is `1`.
- `make visual-assets-import KAMAL_DEST=dev1`: import that archive to one Kamal destination through staged tables. The target first runs the deployed visual-asset table migration, loads archive data into `generated_visual_asset_*_stage`, verifies the staged counts against the export manifest, then atomically swaps the staged tables into place. The previous live tables are preserved in schema `visual_asset_backup` by default.
- `make visual-assets-stream-import KAMAL_DEST=dev1`: stream the local visual-asset tables directly into one Kamal destination without writing `tmp/generated_visual_assets.dump`. It uses the same staged-then-swap workflow as `visual-assets-import`, so live traffic can keep using the existing visual asset tables until the staged copy verifies cleanly. This is the best fit for a single destination or a disk-constrained laptop.
- `make visual-assets-sync-all`: export once, then import the same archive plus manifest to each destination in `VISUAL_ASSETS_DESTS` (default: `dev1 dev2 prd`). Override with `VISUAL_ASSETS_DESTS="dev1 dev2"` or `VISUAL_ASSETS_ARCHIVE=tmp/my_visual_assets.dump VISUAL_ASSETS_MANIFEST=tmp/my_visual_assets.manifest` as needed.
- `make prime-visual-caches`: runs thumbnail priming first, then static-map priming. After a Redis reset, the priming scripts first try to reuse durable visual storage before regenerating remote thumbnails or maps. Static-map priming defaults to durable assets/links plus aliases without hydrating full PNG bodies into Redis; use `PRIME_STATIC_MAP_HYDRATE_ASSETS=1` only for small hotsets that should load image bodies. Full-corpus static-map hydration is refused unless `PRIME_ALLOW_FULL_HYDRATION=1` is also set. Individual broken upstream assets are logged and recorded without making the task fail, so one bad provider thumbnail or map does not stop the full warming run. Local priming waits for ParadeDB to answer `SELECT 1` before starting, which avoids startup/recovery races after Docker restarts. On Kamal, use `make kamal-prime-visual-caches KAMAL_DEST=dev1` or run the lower-level `kamal-prime-thumbnail-cache` / `kamal-prime-static-map-cache` targets.
  - The visual priming scripts wait through transient Redis `LOADING` states by default (`VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS=900`, retry every `VISUAL_ASSET_REDIS_LOADING_RETRY_SECONDS=5`) so a Redis restart/load does not become a flood of false per-resource failures.
  - For very large local warm-up runs, you can temporarily recreate Redis with `REDIS_APPENDONLY=no` and `REDIS_SAVE=""` so Redis stays an in-memory hot cache while Postgres remains the durable store for generated visual assets and links.
- `make resource-cache-init`: ensure the durable `generated_resource_representations` and `generated_api_responses` cache tables exist.
- `make api-response-cache-init`: ensure only the durable `generated_api_responses` / `generated_api_response_tags` tables exist.
- `make api-response-cache-prune`: delete expired durable `generated_api_responses` rows.
- `make prime-resource-cache`: build the shared JSON:API resource representation cache used by both `/api/v1/resources/{id}` and `/api/v1/search`. This writes Redis hot entries plus durable `generated_resource_representations` rows, so Redis can be rehydrated quickly after cache loss. The primer batch-prefetches resource enrichments and bulk-writes cache rows; defaults are `PRIME_BATCH_SIZE=500` and `PRIME_RESOURCE_CONCURRENCY=16`. Use `PRIME_LIMIT`, `PRIME_BATCH_SIZE`, `PRIME_RESOURCE_CONCURRENCY`, `PRIME_FORCE=1`, or `RESOURCE_IDS="..."` to scope/tune a run. On Kamal, use `make kamal-prime-resource-cache KAMAL_DEST=dev1`.
- `make reindex`: atomic local reindex using a versioned index + alias swap (non-destructive build + atomic cutover). Defaults favor safety: swap is blocked on indexing errors/count mismatch, and one previous versioned index is retained. After a successful swap, it automatically clears local `search` cache.
  - Useful local tuning overrides: `REINDEX_CHUNK_SIZE`, `REINDEX_BULK_SIZE`, `REINDEX_BULK_MAX_RETRIES`, `REINDEX_FAST_SETTINGS`, `REINDEX_FORCE_REPLICAS_ZERO`, `REINDEX_RETAIN_PREVIOUS`.
  - Benchmark mode: `make reindex-benchmark` (or `REINDEX_BENCHMARK=true make reindex`) prints per-chunk timings and a final phase summary.
- `make sitemap-generate`: generate and cache the crawler-facing sitemap payload served at `/sitemap.xml` (and supporting `/sitemaps/*.xml` parts when the URL count exceeds sitemap protocol limits).
  - `robots.txt` only advertises that sitemap when `SEARCH_ENGINE_INDEXING_ENABLED=true`; the default remains block-all for local/dev safety.
- `make analytics-maintenance`: ensure monthly `analytics_*` partitions exist, roll up completed daily analytics into compact summary tables, and drop expired raw partitions once they are safely summarized.
- `make analytics-size-report`: print current Postgres sizes for `analytics_*` parent tables, partitions, and rollup tables.
- `make ogm-refresh`: trigger OpenGeoMetadata harvest for all enabled weekly repos (`POST /api/v1/admin/ogm/harvest` with `{"ogm_all":true,"ogm_trigger":"weekly"}`).
- `make ogm-refresh-repo OGM_REPO_NAME=edu.stanford.purl`: trigger OpenGeoMetadata harvest for one repo (`{"ogm_repo_name":"...","ogm_trigger":"manual"}`).
- OGM harvests update local Postgres records, `resource_distributions`, and `resource_relationships` automatically. Run `make reindex` if you need local Elasticsearch/search results updated immediately after the harvest.
- `make ogm-status`: show current OGM harvest runs (`GET /api/v1/admin/ogm/harvest/runs`).
- `make ogm-status OGM_RUN_ID=<run_id>`: show detail for one run (`GET /api/v1/admin/ogm/harvest/runs/{run_id}`).
- `make ogm-status-watch [OGM_RUN_ID=<run_id>] [OGM_STATUS_POLL_SECONDS=5]`: poll OGM status until you stop it (`Ctrl+C`).
- `make ogm-failures`: show only failed OGM harvest runs with `ogm_error` details.
- These OGM make tasks run `curl` from inside the `api` container and use that container's `ADMIN_USERNAME` / `ADMIN_PASSWORD`, so they stay aligned with the live API auth config.
- `make verify-h3-index`: query Elasticsearch to verify H3 pyramid fields (`h3_res2`–`h3_res8`, `geo_or_near_global`) are present (run after reindex)
- `make bridge-sync`: trigger a background bridge crawl through the admin API.
  - Full crawl example: `make bridge-sync`
  - Single-record example: `make bridge-sync RESOURCE_ID=b1g_PJxxfKgpqpUT`
  - Optional filters: `BRIDGE_LIMIT=50`, `BRIDGE_CHANGED_SINCE=2026-04-01T00:00:00Z`, `BRIDGE_TRIGGER=manual`
  - `RESOURCE_ID` is aliased to `BRIDGE_RESOURCE_ID`, so either variable works.
- `make bridge-status`: show a readable bridge sync summary instead of raw JSON by default.
  - It now includes processed/imported counts, pages, elapsed time, throughput, and an estimated total/ETA for full crawls when a prior successful full run exists.
  - Use `make bridge-status BRIDGE_STATUS_RAW=1` if you need the raw API JSON payload.
- `make bridge-status-watch`: poll the current bridge run with the same readable summary.
  - By default it shows only the current run, with processed/imported counts, pages, throughput, and estimated remaining time for full crawls.
  - Use `make bridge-status-watch BRIDGE_STATUS_SHOW_LAST=1` if you also want the last completed run for comparison.
- `make kamal-cron-test-bridge`: run the bridge cron trigger script inside a Kamal cron container. Use `CHANGED_SINCE=2026-04-23T00:00:00Z` to replay a specific bridge delta window.
- Bridge delta syncs update changed resources in Elasticsearch, delete durable generated resource representations for changed IDs, invalidate Redis entries tagged with changed `resource:<id>` values, warm thumbnails/static maps/resource-class icon assets, then re-warm tagged search/resource GETs plus the canonical `/api/v1/resources/{id}` response for each changed resource. This keeps Redis and the durable generated-resource table hot after nightly Bridge edits. Tune with `BRIDGE_SEARCH_INDEX_REFRESH_ENABLED`, `BRIDGE_SEARCH_INDEX_MAX_RESOURCE_IDS`, `BRIDGE_CACHE_REFRESH_ENABLED`, `BRIDGE_GENERATED_ASSET_REFRESH_ENABLED`, `BRIDGE_CACHE_REFRESH_MAX_RESOURCE_IDS`, `BRIDGE_CACHE_REWARM_MAX_URLS`, `BRIDGE_CACHE_REWARM_TIMEOUT_SECONDS`, `BRIDGE_CACHE_THUMBNAIL_CONCURRENCY`, `BRIDGE_CACHE_STATIC_MAP_CONCURRENCY`, `BRIDGE_CACHE_RESOURCE_ICON_CONCURRENCY`, and `BRIDGE_CACHE_REFRESH_FORCE_GENERATED_ASSETS`.
- Nightly bridge cron syncs identify themselves with `BRIDGE_TRIGGER=nightly_cron` by default. The Kamal cron crontab now pins `CRON_TZ=America/Chicago`, and the bridge script computes `changed_since` from the previous America/Chicago day before converting to UTC for the bridge API. Cron shells also source `/app/scripts/cron_env.sh` through `BASH_ENV` so Celery, Redis, DB, and Python-path settings match the live container instead of falling back to local defaults.
- Cron bridge and blog triggers now enqueue work with `apply_async(ignore_result=True)` so they do not need a Celery result-backend subscription just to queue fire-and-forget jobs.
- Set `BRIDGE_SYNC_REPORT_ENABLED=true` and `BRIDGE_SYNC_REPORT_FROM` to email the styled nightly report after the Celery sync task concludes. Default recipients are `ewlarson@gmail.com,majew030@umn.edu`; override only with `BRIDGE_SYNC_REPORT_RECIPIENTS` if the recipient list intentionally changes. Reports are sent only from `KAMAL_DEST=prd` by default; override with `BRIDGE_SYNC_REPORT_DESTINATIONS`. prd uses `BRIDGE_SYNC_REPORT_DELIVERY=sendmail`; the Kamal image installs `msmtp-mta` to provide `/usr/sbin/sendmail` and relays through UMN `smtp.umn.edu` without app-level SMTP credentials. SMTP delivery is still available with `BRIDGE_SYNC_REPORT_DELIVERY=smtp` and `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`. Reports are sent for `nightly_cron,cron` triggers by default; override with `BRIDGE_SYNC_REPORT_ON_TRIGGERS` and use `BRIDGE_SYNC_REPORT_MIN_DELTA_PROCESSED` to flag suspiciously small delta runs.
- One-time Kamal host bootstrap: prepare each server with the shared `deploy` SSH account before routine deploys. Use `backend/scripts/bootstrap_kamal_deploy_user.sh --host <host> --ssh-user <existing_admin_user>`, then keep `KAMAL_SSH_USER=deploy` in `.kamal/secrets.<dest>`. See `docs/backend/kamal_deployment.md`.
- `make kamal-reindex`: atomic remote reindex on Kamal using a versioned index + alias swap (runs once by default with `--roles web`). Uses `KAMAL_DEST=dev1` by default and supports any configured destination such as `dev2` or `prd`; secrets come from `.kamal/secrets-common` + `.kamal/secrets.<dest>`. On success, runs `make kamal-clear-cache`.
  - Useful overrides: `KAMAL_REINDEX_RETAIN_PREVIOUS=1` (default), `KAMAL_REINDEX_PRUNE_OLD=true` (default), `KAMAL_REINDEX_ALLOW_PARTIAL=false` (default; blocks swap on indexing/count mismatch), `KAMAL_REINDEX_REMOVE_LEGACY_INDEX=true` (default; one-time migration from legacy non-alias index name).
- `make kamal-verify-h3-index`: verify H3 fields on remote Kamal app containers. Use `KAMAL_DEST=<destination>` such as `dev1`, `dev2`, or `prd`.
- `make kamal-clear-cache`: clear remote API cache on Kamal (defaults to `KAMAL_CACHE_TYPE=search`). Use `KAMAL_DEST=<destination>` such as `dev1`, `dev2`, or `prd`. Override with `KAMAL_CACHE_TYPE=all` (or `suggest`/`item`).
- `make kamal-prime-resource-cache`: build the shared resource representation cache inside a Kamal app container. This ensures the durable generated-resource table exists, writes durable rows, and fills Redis. This is useful after deploy/cache clears before collecting search/detail performance HARs.
- `make kamal-prime-visual-caches`: build the thumbnail and static-map hot Redis caches inside a Kamal app container. The lower-level Kamal priming targets ensure the durable generated-visual-asset tables exist before warming. This complements `kamal-prime-resource-cache`; use both before performance HARs when you want search JSON, thumbnail redirects, and static-map/icon redirects all warm.
- `make kamal-prime-static-map-cache`: build only the static-map/resource-class-icon visual cache on Kamal. By default, full runs write durable static-map assets/links and Redis aliases without hydrating full PNG bodies into Redis DB 1. Supports `PRIME_LIMIT`, `PRIME_BATCH_SIZE`, `PRIME_STATIC_MAP_CONCURRENCY`, `PRIME_FORCE=1`, `PRIME_STATIC_MAP_HYDRATE_ASSETS=1`, `PRIME_ALLOW_FULL_HYDRATION=1`, and `RESOURCE_IDS="..."`.
- `make kamal-api-response-cache-init`: ensure the durable Postgres L2 response cache tables exist on Kamal.
- `make kamal-api-response-cache-prune`: delete expired durable Postgres L2 response cache rows on Kamal.
- `make kamal-network-sanity`: compare host-shell and app-container connectivity on a Kamal destination. It probes a few external URLs plus the server's own public hostname and exits nonzero if the container cannot reach something the host can. Defaults to `KAMAL_DEST=dev1`, role `web`, self URL `https://$(KAMAL_HOST)`, and external URLs `https://api.github.com https://raw.githubusercontent.com https://gin.btaa.org http://example.com`. Override with `KAMAL_DEST=prd`, `KAMAL_APP_ROLE=cron`, `KAMAL_NETWORK_SELF_URL=...`, or `KAMAL_NETWORK_EXTERNAL_URLS="..."`.
- `make ingest`: ingest BTAA fixture JSON files into the DB (runs inside the `api` Docker container). Default: `data/fixtures/btaa_fixtures_data`. Override with `make ingest FIXTURES_DIR=btaa_featured_resources REPO_NAME=btaa_featured_resources`. After ingest, run `make reindex` to index into Elasticsearch.
- `make ingest-featured`: ingest `data/fixtures/btaa_featured_resources` into the DB and then reindex into Elasticsearch (one-step for featured resources).
- `make clear_cache`: flush Redis cache DB (`REDIS_DB`, requires `REDIS_PASSWORD`)

Analytics storage knobs live in `.env` / deploy env vars:

- `ANALYTICS_RETENTION_API_USAGE_DAYS` default `30`
- `ANALYTICS_RETENTION_SEARCH_DAYS` default `90`
- `ANALYTICS_RETENTION_IMPRESSION_DAYS` default `30`
- `ANALYTICS_RETENTION_EVENT_DAYS` default `90`
- `ANALYTICS_PARTITION_HISTORY_MONTHS` default `2`
- `ANALYTICS_PARTITION_FUTURE_MONTHS` default `2`
- `ANALYTICS_ROLLUP_MAX_DAYS_PER_RUN` default `31`

## Frontend (Docker)

- `make frontend-reset`: clear Vite cache in `frontend-dev` and restart the dev server. Use after changing `optimizeDeps` or when seeing "Failed to fetch dynamically imported module" or 504 "Outdated Optimize Dep". **After running it, do a hard refresh** (Ctrl+Shift+R or Cmd+Shift+R) or open the app in an incognito window—otherwise the browser may keep requesting old chunk URLs and still get 504s.
- `make db-export`: export local DB → `tmp/btaa_geospatial_api_export.sql.gz`, and also build the `db-sync` import archive used by `db-import`
- `make db-import`: import the `db-sync` archive to remote via Kamal. By default this preserves destination-local tables listed in `DB_SYNC_PRESERVE_TABLES` (`api_service_tiers`, `api_keys`, `analytics_api_usage_logs`, `analytics_searches`, `analytics_search_impressions`, `analytics_events`) and their owned sequences listed in `DB_SYNC_PRESERVE_SEQUENCES`. Use `KAMAL_DEST=<destination>` such as `dev1`, `dev2`, or `prd` to target a server. To force a full overwrite, run `make db-export DB_SYNC_PRESERVE_LOCAL_TABLES=false` and then `make db-import DB_SYNC_PRESERVE_LOCAL_TABLES=false ...`.
- `make db-sync`: `db-export` + `db-import` with destination-local table preservation enabled by default
- **GBL Admin production sync**: `make gbl-admin-db-sync` downloads the latest `pgdump-geoportal_production-*.sql.gz` from the GBL Admin server and restores the newest local matching dump into local ParadeDB, whether that file is compressed (`.sql.gz`) or already decompressed (`.sql`). It streams from the compressed file when using `.gz`, so you only need space for the `.gz`. After restore, it keeps the newly restored database plus the newest previously restored `geoportal_production_*` database, pruning older ones by default (`GBL_ADMIN_RETAIN_DBS=2`). The production role `geomg` is created locally so restore does not fail on OWNER clauses. If ParadeDB crashes during restore (e.g. OOM), increase Docker memory for the `paradedb` service and re-run; you may need to drop the partial DB first: `docker compose exec paradedb psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS geoportal_production_YYYYMMDD;"`.
- **GBL Admin add latest BTAA fields**: `make gbl-admin-db-add-latest-btaa-fields` adds latest BTAA compatibility columns to `resources`.
- **GBL Admin import resources**: `make gbl-admin-db-import-resources` imports from `kithe_to_resources_bridge` into `btaa_geospatial_api` (`OLD_DB_NAME` auto-detected unless provided). To soft-retire local resources that are missing from the current old-prod snapshot, run `make gbl-admin-db-import-resources GBL_ADMIN_RETIRE_MISSING=true`.
- **GBL Admin populate distributions**: `make populate-distributions` rebuilds `resources.dct_references_s`, `resource_distributions`, `resource_downloads`, and `resource_assets` from legacy old-production data (`OLD_DB_NAME` auto-detected unless provided).
  - This now includes child Kithe asset rows, so PMTiles/download URLs that never lived on the parent record are preserved.
  - Single-record example: `make populate-distributions RESOURCE_ID=b1g_PJxxfKgpqpUT`
  - `RESOURCE_ID` is aliased to `GBL_ADMIN_RESOURCE_ID`, so either variable works.
- **GBL Admin populate data dictionaries**: `make populate-data-dictionaries` migrates legacy `document_data_dictionaries` and `document_data_dictionary_entries` into `resource_data_dictionaries` and `resource_data_dictionary_entries`.
- **GBL Admin full import pipeline**: `make gbl-admin-db-import-all` runs latest-field migration, resource import, soft-retires local resources missing from the current old-prod snapshot, migrates distributions and data dictionaries, repopulates relationships, and reindexes published resources.
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
make gbl-admin-db-import-resources GBL_ADMIN_RETIRE_MISSING=true
make populate-distributions
make populate-data-dictionaries
make populate-relationships
make reindex
```

Targeted recovery examples:

```bash
make bridge-sync RESOURCE_ID=b1g_PJxxfKgpqpUT
make populate-distributions RESOURCE_ID=b1g_PJxxfKgpqpUT
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
