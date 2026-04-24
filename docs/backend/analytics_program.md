# Analytics Program

This document describes the BTAA Geospatial API analytics program: what we collect, how the data moves through the system, the performance rules we are protecting, and how to operate and extend the analytics stack safely.

The analytics program has two complementary goals:

1. Capture every API request so we can understand real traffic, client behavior, and service-tier usage.
2. Capture product behavior in the Geoportal so we can understand searches, impressions, resource views, downloads, and outbound link clicks.

## Principles

- **Always log requests.** API request logging is independent from rate limiting. Setting `RATE_LIMIT_ENABLED=false` disables throttling, not analytics.
- **Do not slow the product down for analytics.** Request handlers and frontend interactions should not wait on Postgres writes.
- **Fail open.** If Redis or Celery is unhealthy, the application should keep serving traffic even if analytics are delayed or dropped.
- **Keep raw data for a limited time.** Raw analytics are valuable for debugging and detailed analysis, but they must not grow forever.
- **Prefer explicit source identity.** We want to know whether traffic came from the Geoportal, SSR, QGIS, docs, or a partner client when that information is available.

## Architecture

### 1. API request analytics

Every API request is serialized by `APIUsageLogService` and queued to Celery. The worker task writes the row to `analytics_api_usage_logs`, then enriches browser, OS, and device-type fields from the user agent.

Current implementation:

- Request serialization: `backend/app/services/api_usage_log_service.py`
- Async persistence and enrichment: `backend/app/tasks/api_usage_enrichment.py`
- Middleware entrypoint: `backend/app/middleware/rate_limit_middleware.py`

Important behavior:

- Request logging still runs when `RATE_LIMIT_ENABLED=false`.
- Query params are preserved in `properties.query_params`.
- UTM fields are stored in top-level columns.
- `visit_token`, `client_*`, and `source_host` are captured when available.

### 2. Product analytics

Geoportal analytics are sent as lightweight batched beacons to `/api/v1/analytics/events`. The backend accepts the payload, adds request defaults, queues it to Celery, and returns `202 Accepted`.

Current implementation:

- Frontend batching and transport: `frontend/src/services/analytics.ts`
- Ingest endpoint: `backend/app/api/v1/endpoint_modules/analytics.py`
- Batch persistence: `backend/app/tasks/analytics_events.py`

This is intentionally separate from normal search/resource API responses so search and detail pages do not block on analytics writes.

### 3. Source identity

We track source and client identity in two ways:

- **Request headers**
  - `X-BTAA-Client-Name`
  - `X-BTAA-Client-Version`
  - `X-BTAA-Client-Channel`
  - `X-BTAA-Client-Instance`
  - `X-Visit-Token`
- **Derived request context**
  - `source_host` from `Origin` / `Referer`
  - `referring_domain`
  - API key / service tier for authenticated API requests

Current first-party client identities:

- `geoportal-web` for same-origin browser API requests
- `geoportal-ssr` for server-side fetches

External or partner clients can opt into the same attribution model by sending the `X-BTAA-Client-*` headers.

## Data Model

### Raw tables

- `analytics_api_usage_logs`
  - One row per API request
  - Includes endpoint, method, status, latency, tier, API key, visit token, source, UTM fields, and request properties
- `analytics_searches`
  - One row per rendered search result page
  - Includes query, view, page, sort, search field, result counts, zero-results flag, and serialized search constraints
- `analytics_search_impressions`
  - One row per resource impression in a search result page
  - Includes `search_id`, `resource_id`, rank, page, and view
- `analytics_events`
  - One row per user interaction event
  - Includes resource views, result clicks, downloads, outbound links, citation actions, and related metadata

### Rollup tables

- `analytics_daily_api_usage_metrics`
  - Daily request counts by endpoint, method, status, tier, API key, and client/source dimensions
- `analytics_daily_search_metrics`
  - Daily counts of searches, zero-results searches, total search results, and total impressions by client/source/view/sort/search field
- `analytics_daily_resource_metrics`
  - Daily per-resource event counts by event type and client/source dimensions
- `analytics_maintenance_state`
  - Checkpoint table used by the maintenance job to track rollup progress

### Partitioning

All raw `analytics_*` tables are monthly partitioned by `partition_month`.

That gives us three benefits:

- Fast partition drops when raw data ages out
- Bounded table/index growth
- Safer long-term retention than large `DELETE` jobs

## What We Collect Today

### API request analytics

`analytics_api_usage_logs` currently captures:

- endpoint path and method
- status code and response time
- service tier and API key id
- IP address and user agent
- browser / OS / device-type enrichment
- visit token
- referrer and referring domain
- UTM fields
- source attribution fields (`client_name`, `client_version`, `client_channel`, `client_instance`, `source_host`)
- serialized request query params in `properties.query_params`

### Search analytics

`analytics_searches` currently captures:

- `search_id`
- query text
- canonical search URL
- view (`list`, `gallery`, `map`)
- page and per-page
- sort and search field
- total result count and total pages
- `zero_results`
- full serialized constraints in `properties.constraints`
- spelling suggestions in `properties.spelling_suggestions`

### Search impressions

`analytics_search_impressions` currently captures:

- `search_id`
- `resource_id`
- absolute rank
- page
- view

### Resource and click events

`analytics_events` currently captures these implemented event types:

- `result_click`
- `resource_view`
- `next_result`
- `previous_result`
- `download_click`
- `download_prepare_requested`
- `download_prepare_success`
- `download_prepare_failure`
- `metadata_download`
- `web_service_click`
- `visit_source_click`
- `external_geoportal_click`
- `documentation_click`
- `outbound_link_click`
- `permalink_copy`
- `citation_copy`
- `citation_export`

Common event fields include:

- `search_id`
- `resource_id`
- rank / page / view
- link label
- destination URL
- source component
- extra structured properties

## Performance Guardrails

The analytics program is designed around strict no-hot-path rules.

### Backend rules

- API request logging is queued to Celery instead of writing directly to Postgres.
- `/api/v1/analytics/events` validates lightly, enqueues work, and returns `202`.
- If the Celery enqueue step fails, the request still succeeds and the failure is logged.
- Search and resource endpoints do not issue extra Postgres writes for analytics.

### Frontend rules

- Analytics are sent in batches, not per-result requests.
- Search impressions are emitted once per rendered result page.
- `requestIdleCallback` is used when available so analytics dispatch waits for idle time.
- `navigator.sendBeacon()` is preferred to avoid blocking navigation or unload.
- `fetch(..., { keepalive: true })` is the fallback path.

### Cross-origin guardrail

The Geoportal only adds custom analytics headers on same-origin browser API requests. That avoids unnecessary CORS preflight latency for cross-origin browser requests.

## Storage, Retention, and Rollups

### Default retention windows

Current defaults:

```text
ANALYTICS_RETENTION_API_USAGE_DAYS=30
ANALYTICS_RETENTION_SEARCH_DAYS=90
ANALYTICS_RETENTION_IMPRESSION_DAYS=30
ANALYTICS_RETENTION_EVENT_DAYS=90
ANALYTICS_PARTITION_HISTORY_MONTHS=2
ANALYTICS_PARTITION_FUTURE_MONTHS=2
ANALYTICS_ROLLUP_MAX_DAYS_PER_RUN=31
```

Retention is enforced by dropping whole monthly partitions after rollups have safely covered the relevant dates.

### Rollup behavior

The maintenance job:

1. Ensures raw monthly partitions exist
2. Rolls up completed days into daily summary tables
3. Drops expired raw partitions only after rollup checkpoints have advanced past them

Important detail:

- Daily rollups only process **completed days**, up through yesterday
- It is normal for same-day raw data to exist while the daily rollup tables remain empty for that date

### Why we do not `DELETE` old rows

Large `DELETE` jobs create table bloat and vacuum pressure in Postgres. Monthly partition drops are much cheaper and more predictable.

## Operations

### Run migrations

Local Docker:

```bash
docker compose exec -T api bash -lc 'cd /app/backend && python scripts/run_migrations.py'
```

Kamal / remote:

```bash
kamal app exec -d dev1 --roles web "bash -lc 'cd /app/backend && /opt/venv/bin/python scripts/run_migrations.py'"
```

### Run analytics maintenance

Local:

```bash
make analytics-maintenance
make analytics-size-report
```

Direct script:

```bash
cd backend
python scripts/manage_analytics_storage.py --mode maintenance
python scripts/manage_analytics_storage.py --mode size-report
python scripts/manage_analytics_storage.py --mode ensure
```

Remote:

```bash
kamal app exec -d dev1 --roles web "bash -lc 'cd /app/backend && /opt/venv/bin/python scripts/manage_analytics_storage.py --mode maintenance'"
```

### Scheduled maintenance

The Kamal cron container currently runs analytics maintenance daily at `4:45 AM`.

### `db-sync` preservation

`make db-sync` preserves destination-local analytics tables by default:

- `analytics_api_usage_logs`
- `analytics_searches`
- `analytics_search_impressions`
- `analytics_events`

This prevents local or environment-specific analytics history from being overwritten during syncs.

## Extending the Program

### Add a new frontend event

1. Emit it with `scheduleAnalyticsBatch(...)` in the relevant component.
2. Include stable identifiers such as `search_id`, `resource_id`, `label`, `destination_url`, and `source_component` when relevant.
3. Prefer structured fields over unbounded strings in `properties`.
4. Add or update frontend tests if the event is behaviorally important.

### Add a new API client identity

1. Send `X-BTAA-Client-*` headers from the client or proxy.
2. Reuse `X-Visit-Token` where session continuity matters.
3. Keep the client name stable across releases.
4. Use `client_version` for release or build identification.

### Add long-term metrics

If a raw field needs to survive beyond raw retention:

1. Add it to a daily rollup table, or create a new rollup table
2. Update the maintenance SQL in `backend/db/migrations/analytics_storage.py`
3. Re-run migrations and maintenance

## Known Limitations

- `analytics_daily_search_metrics` and `analytics_daily_resource_metrics` do not include the current day until the next maintenance run.
- `analytics_daily_resource_metrics` summarizes resource-scoped events. Events without `resource_id` are not preserved there.
- Search impression counts are preserved in `analytics_daily_search_metrics`; there is not currently a separate daily impression rollup table.
- Raw data outside retention windows is intentionally discarded once its month is safely rolled up.

## Related Docs

- [Service Tiers & Rate Limiting Runbook](service_tiers_runbook.md)
- [Backend Scripts](scripts.md)
- [Kamal Deployment](kamal_deployment.md)
- [Makefile Tasks](../make_tasks.md)
