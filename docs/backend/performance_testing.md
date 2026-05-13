# Performance testing

This repo includes a small k6 suite for exercising both the public frontend and
the backend API at the same time.

The suite is designed to answer two related questions:

1. Can the rendered frontend continue serving page traffic under load?
2. Can the API continue serving search/resource traffic under load?

By default, the k6 targets hit `dev1`:

```text
https://lib-btaageoapi-dev-app-01.oit.umn.edu
```

## What the suite covers

### Frontend traffic

The frontend scenario requests:

- `/`
- `/manifest.webmanifest`
- `/registerSW.js`
- `/search?q=<query>`
- `/search?q=<query>&include_filters[...][]=...`
- `/resources/<resource_id>`

This gives us light coverage of the public page shell, static frontend assets,
search results page rendering, faceted search page rendering, and resource
detail rendering.

### API traffic

The API scenario requests:

- `/api/v1/search`
- `/api/v1/search` with live discovered `include_filters[...][]` facet params
- `/api/v1/search/facets/<facet_name>`
- `/api/v1/suggest`
- `/api/v1/resources/`
- `/api/v1/resources/<resource_id>`
- `/api/v1/home/blog-posts`

This gives us direct backend pressure on the core search/resource endpoints plus
the homepage blog payload used by the frontend. The faceted calls are built from
live facet values returned by the seed search response so the suite keeps
testing realistic filter combinations instead of relying on brittle hard-coded
facet values.

## Quick start

### Smoke test

Run one end-to-end iteration:

```bash
make k6-smoke
```

### Stress test

Run the default concurrent frontend + API stress mix:

```bash
make k6-stress
```

The suite will use a local `k6` binary when present. If `k6` is not installed,
the Makefile falls back to Docker with `grafana/k6:latest`.

Summaries are written to:

- `tmp/k6/smoke-summary.json`
- `tmp/k6/stress-summary.json`

## Useful overrides

### Point at another environment

```bash
make k6-stress K6_BASE_URL=https://lib-btaageoapi-dev-app-01.oit.umn.edu
make k6-stress K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu
```

### Change the query or pin a known resource

```bash
make k6-stress K6_QUERY=chicago
make k6-stress K6_RESOURCE_ID=p16022coll206:283
```

If `K6_RESOURCE_ID` is not provided, the suite discovers one from the first
search result for `K6_QUERY`.

For varied-query stress runs, pass a comma- or pipe-separated query pool. The
seed search still uses `K6_QUERY` to discover a stable resource id and facet
values, while each frontend/API iteration rotates the actual search and suggest
terms through `K6_QUERY_POOL`:

```bash
make k6-stress K6_QUERY_POOL="minnesota|chicago|water|roads|imagery"
```

### Tune frontend and API pressure separately

```bash
make k6-stress K6_FRONTEND_TARGET_VUS=6 K6_API_TARGET_VUS=12
make k6-stress K6_FRONTEND_HOLD=5m K6_API_HOLD=5m
```

Available knobs:

- `K6_FRONTEND_TARGET_VUS`
- `K6_FRONTEND_RAMP_UP`
- `K6_FRONTEND_HOLD`
- `K6_FRONTEND_RAMP_DOWN`
- `K6_FRONTEND_THINK_TIME_SECONDS`
- `K6_FRONTEND_P95_THRESHOLD_MS`
- `K6_FRONTEND_P99_THRESHOLD_MS`
- `K6_API_TARGET_VUS`
- `K6_API_RAMP_UP`
- `K6_API_HOLD`
- `K6_API_RAMP_DOWN`
- `K6_API_THINK_TIME_SECONDS`
- `K6_API_P95_THRESHOLD_MS`
- `K6_API_P99_THRESHOLD_MS`
- `K6_QUERY`
- `K6_QUERY_POOL`
- `K6_SUGGEST_QUERY`
- `K6_RESOURCE_ID`
- `K6_API_KEY`
- `K6_SEARCH_PER_PAGE`
- `K6_CACHE_BUST_SEARCH`
- `K6_CACHE_BUST_SEED`
- `K6_ENDPOINT_BREAKDOWN`
- `K6_SEARCH_DIAGNOSTICS`

### Test one endpoint at a fixed request rate

Use `make k6-endpoint-capacity` when you need a defensible endpoint p95 at a
known request rate instead of a blended scenario p95 from VU-based stress. The
target endpoint is exercised with k6's `constant-arrival-rate` executor, so
`K6_REQUEST_RATE=50` means k6 tries to start 50 iterations per second for that
single endpoint:

```bash
make k6-endpoint-capacity \
  K6_ENDPOINT_TARGET=frontend_search_results_api \
  K6_REQUEST_RATE=50 \
  K6_ENDPOINT_DURATION=3m \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_API_KEY=...
```

Supported `K6_ENDPOINT_TARGET` values:

- `frontend_search_results_api`
- `frontend_faceted_search_results_api`
- `frontend_resource_page`
- `api_search`
- `api_faceted_search`

Useful fixed-rate knobs:

- `K6_REQUEST_RATE`
- `K6_RATE_TIME_UNIT`
- `K6_ENDPOINT_DURATION`
- `K6_PRE_ALLOCATED_VUS`
- `K6_MAX_VUS`
- `K6_ENDPOINT_P95_THRESHOLD_MS`
- `K6_ENDPOINT_P99_THRESHOLD_MS`

### Force search miss-path traffic

When you want to bypass the URL-level endpoint response cache for search/facet
requests, enable cache busting for search-like requests:

```bash
make k6-stress K6_CACHE_BUST_SEARCH=1
```

On production-like environments with `RATE_LIMIT_ENABLED=true`, pass a
service-tier key so the direct API scenario measures backend capacity instead
of the anonymous 10 requests/minute throttle:

```bash
make k6-stress K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu K6_API_KEY=...
```

For local repeat runs, store a k6-only key in an ignored file such as
`tmp/k6/prd-k6.env`:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-stress K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu
```

`dev2` is the rate-limiting capacity proving ground. It keeps rate limiting
enabled and caps per-worker database pools so k6 can exercise the production
API-key path without using production traffic:

```bash
make k6-stress K6_BASE_URL=https://geodev.btaa.org K6_API_KEY=...
```

The relevant server-side knobs are:

- `API_KEY_TIER_CACHE_TTL_SECONDS`: short process-local cache for successful
  API-key/tier lookups.
- `API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS`: minimum interval between
  `api_keys.last_used_at` writes per key/process.
- `DB_POOL_MAX`: cap for the shared `databases` pool in each API worker.
- `SQLALCHEMY_ASYNC_POOL_SIZE` and `SQLALCHEMY_ASYNC_MAX_OVERFLOW`: caps for
  SQLAlchemy async engine pools used by search/resource/cache helpers.

This appends an ignored `k6cb=...` query param to:

- `/search`
- faceted `/search`
- `/api/v1/search`
- faceted `/api/v1/search`
- `/api/v1/search/facets/<facet_name>`

That preserves the existing API/HTML payload shape while forcing unique
search/facet request URLs. The backend may still reuse semantic search-result
cache entries when the actual query/filter/page/sort inputs are unchanged; this
is intentional because it represents protection against transport noise and
duplicated frontend/API/QGIS/MCP search intent. Disable `SEARCH_RESULT_CACHE`
only when you need to measure the full search-result assembly miss path.

The cache-bust token includes a generated per-run seed so repeated smoke/stress
runs do not accidentally reuse old endpoint-cache entries. Set
`K6_CACHE_BUST_SEED=<value>` only when you intentionally need reproducible URLs.

Add `K6_ENDPOINT_BREAKDOWN=1` when you need per-endpoint `p95`/`p99` rows in
the k6 summary. This is useful after scenario-level thresholds fail and you
need to see which tagged endpoint is carrying the tail latency.

Search diagnostics are enabled by default with `K6_SEARCH_DIAGNOSTICS=1`.
Search-like requests record custom k6 metrics from `X-Search-Semantic-Cache`
and `Server-Timing` headers:

- `search_semantic_cache_hit_rate`
- `search_semantic_cache_hits`
- `search_semantic_cache_misses`
- `search_semantic_cache_observed`
- `search_semantic_cache_unknown`
- `search_response_duration`
- `search_server_timing_total`
- `search_server_timing_search`
- `search_server_timing_response_build`
- `search_server_timing_resource_cache_lookup`
- `search_server_timing_db_fallback`
- `search_server_timing_miss_prefetch`
- `search_server_timing_miss_build`
- `search_server_timing_semantic_cache_lookup`
- `search_server_timing_semantic_cache_wait`
- `search_server_timing_semantic_cache_store`

These metrics help distinguish true cache misses from cache hits that are slow
because of worker queueing, frontend fetch timing, or downstream response
composition. Disable them with `K6_SEARCH_DIAGNOSTICS=0` only when you need the
lowest possible test-client overhead.

The frontend scenario treats `/search` as a browser flow: it requests the HTML
shell and then requests `/search/results` for the JSON data that the hydrated
client fetches through the keyed frontend BFF route. This keeps the API-key
throttling path represented in frontend load tests without blocking SSR on the
search payload. In Kamal single-host deployments, nginx handles the exact
`/search/results` JSON route directly: it injects the server-side API key and
proxies to the internal FastAPI pool. That keeps the browser/API-key contract
intact while avoiding the React Router worker queue for facet-heavy result
payloads. For keyed k6 runs, `/search/results` preserves the caller's
`X-API-Key` and does not add the frontend Turnstile gate markers, so mixed tests
can exercise the frontend JSON route without needing a Cloudflare browser
challenge session.

## Mixed-load worker isolation

When mixed frontend/API stress shows high client-observed latency but low
`search_server_timing_total`, check for worker queue contention before changing
search payload shape. The Kamal web container separates public API traffic from
frontend BFF traffic with:

- `WEB_UVICORN_WORKERS`: public `/api/...` FastAPI workers.
- `WEB_INTERNAL_UVICORN_WORKERS`: loopback-only FastAPI workers used by SSR/BFF
  fetches through `API_BASE_URL` and nginx's direct `/search/results` BFF proxy.

On the current 12-vCPU production host, the serving profile is:

- Public API: `WEB_UVICORN_WORKERS=4`
- Internal frontend API pool: `WEB_INTERNAL_UVICORN_WORKERS=6`
- Frontend SSR/BFF: `WEB_SSR_WORKERS=4`
- Web container ceiling: `cpus: 8`, `memory: 5120m`

The worker container is capped at `cpus: 1.75`, giving Celery more room for
bridge syncs, cache warming, and maintenance while still reserving host CPU for
Elasticsearch, Postgres, Redis, and the OS. The 8-vCPU dev hosts keep the
smaller `3 / 4 / 3` web-worker profile with `web cpus: 5` unless a test run
explicitly changes those destination overrides. The next validation step after
changing these values is to rerun the mixed `18 API VUs + 6 frontend VUs`
profile and compare API p95 against the API-only baseline.

The production Postgres accessory currently has `max_connections=100`, so each
Kamal destination must keep per-process DB pools bounded. Production uses:

- `DB_POOL_MAX=2` for the shared `databases` async pool.
- `SQLALCHEMY_ASYNC_POOL_SIZE=1` and `SQLALCHEMY_ASYNC_MAX_OVERFLOW=0` for
  SQLAlchemy async engines.
- `SQLALCHEMY_SYNC_POOL_SIZE=1` and `SQLALCHEMY_SYNC_MAX_OVERFLOW=0` for sync
  SQLAlchemy engines used by request-path thumbnail/visual-asset helpers.

These caps intentionally trade some request queueing inside each app process
for a hard ceiling on database connections. If p95 rises under load, increase
Postgres `max_connections` or add a pooler before raising these per-process
pool values.

If the API pool remains healthy but frontend resource page tails stay high,
check the SSR layer next. `WEB_SSR_WORKERS` controls how many local
`react-router-serve` processes nginx balances across. Raising this reduces
single-process Node queueing for HTML routes, while `/search/results` data
traffic should stay on the nginx -> internal FastAPI path.

## Backend search knobs

These backend env vars are useful when tuning facet-heavy search behavior:

- `SEARCH_FACET_CACHE_TTL`
  Controls how long normalized search facet blocks and facet-value buckets stay
  hot in Redis. Default: `3600` seconds.
- `SEARCH_RESULT_CACHE`
  Enables the semantic `/api/v1/search` response-core cache below the endpoint
  response cache. Default: `true`.
- `SEARCH_RESULT_CACHE_TTL`
  Controls how long semantic search response cores stay hot in Redis. Default:
  same as `SEARCH_CACHE_TTL` (`3600` seconds).
- `SEARCH_RESULT_CACHE_VERSION`
  Bumps only the semantic search response-core namespace when the cached core
  format changes. Default: `v1`.
- `SEARCH_RESULT_CACHE_LOCK_WAIT_SECONDS`
  Controls how briefly a request waits for another worker to fill the semantic
  cache before computing the response itself. Default: `0.25` seconds.
- `SEARCH_TIMING_LOG_THRESHOLD_MS`
  Controls when the backend logs aggregation timing summaries at `info` instead
  of `debug`. Default: `750` milliseconds.
- `SEARCH_RESPONSE_TIMING_LOG_THRESHOLD_MS`
  Controls when `/api/v1/search` response-assembly timing logs are emitted at
  `info` instead of `debug`. Default: `750` milliseconds.
- `SEARCH_TIMING_HEADERS`
  Adds live `Server-Timing` and `X-Search-Semantic-Cache` headers to search
  responses. Default: `true`. These diagnostics are not stored in endpoint
  response-cache records.

The new aggregation timing logs are emitted from the backend search layer and
distinguish cache hits from full Elasticsearch aggregation misses, which makes
it easier to compare warm and miss-path behavior during k6 runs.

The API search endpoint also emits `search_response_timing` logs that break down
the `/api/v1/search` assembly path into semantic-cache lookup/wait/store, search,
representation-cache lookup, DB fallback, miss prefetch, miss build, and
response-build stages.

### Run only one side of the stack

```bash
make k6-stress K6_ENABLE_FRONTEND=0
make k6-stress K6_ENABLE_API=0
```

At least one of `K6_ENABLE_FRONTEND` or `K6_ENABLE_API` must remain enabled.

## Warm-cache testing on Kamal

For warm-cache performance runs on `dev1`, prime the major caches first:

```bash
make kamal-prime-resource-cache KAMAL_DEST=dev1
make kamal-prime-visual-caches KAMAL_DEST=dev1
```

That helps separate cache-warming misses from steady-state behavior when you are
collecting comparison baselines.

## Local Docker note

When the Makefile falls back to Docker, the k6 container can hit public URLs
without extra setup. If you want to point the suite at a local app instead of a
public host, use a Docker-reachable hostname such as:

```bash
make k6-smoke K6_BASE_URL=http://host.docker.internal:8000
```
