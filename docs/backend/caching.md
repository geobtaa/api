# Caching Guide (Redis + HTTP Semantics)

This document explains how **response caching** works in the BTAA Geospatial API backend and how to **verify** it end-to-end.

The caching system is designed to be:

- **Fast**: serve hot endpoints from Redis.
- **Correct**: cache keys include request representation inputs; invalidation is tag-based.
- **Resilient**: protects against stampedes and supports stale serving on upstream errors.

---

## What is cached?

Caching is implemented as a decorator on selected endpoints:

- `/api/v1/search` (GET/POST), `/api/v1/search/facets/{facet_name}`, `/api/v1/suggest`
- `/api/v1/resources/{id}`, `/api/v1/resources/`, `/api/v1/resources/{id}/distributions`
- selected gazetteer endpoints

The decorator lives in:

- `backend/app/services/cache_service.py` (`cached_endpoint`)

Cached endpoint responses use Redis as the hot L1 cache and Postgres
`generated_api_responses` / `generated_api_response_tags` as a durable L2 cache.
On a Redis miss, the app can rehydrate Redis from Postgres before recomputing an
expensive endpoint response.

`/api/v1/search` also has a semantic response-core cache below the endpoint
response cache. It stores the expensive request-independent core (`meta`, search
`data`, and optional `included`) keyed by actual search inputs such as query,
page, sort, fields, facets, legacy `fq`, include/exclude filters, and advanced
query clauses. It intentionally excludes request URL noise such as cache-buster
params, callback, and pagination-link host details, then rebuilds request-specific
links for every caller. These entries are tagged as `search`, so the existing
search-cache clear workflow invalidates them.

Caching can be turned on/off globally via env.

---

## Enable caching

### Required environment variables

Set these in `.env`, your deployment environment, or container env:

```text
ENDPOINT_CACHE=true

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=optional_password
REDIS_DB=0
```

### Docker Compose note

If you run the API via Docker Compose, ensure the `api` service passes `ENDPOINT_CACHE` through from `.env` (rather than hard-coding it), so local toggles like `ENDPOINT_CACHE=false` take effect after a container recreate.

### Useful debug/ops flags

```text
# Adds X-Cache headers (MISS/HIT/STALE/WAIT_HIT) so you can verify behavior quickly.
CACHE_DEBUG_HEADERS=true

# Logs structured-ish cache events to the app logger.
CACHE_LOG_EVENTS=true

# Optional: version the cache namespace (safe rollouts without manual purges).
CACHE_VERSION=v2
CACHE_APP_VERSION=2026-01-07

# Durable L2 response cache (Kamal enables this by default).
API_RESPONSE_DURABLE_CACHE_STORE=database

# Semantic search-result core cache below the endpoint cache.
SEARCH_RESULT_CACHE=true
SEARCH_RESULT_CACHE_TTL=3600
SEARCH_RESULT_CACHE_VERSION=v1

# Live search diagnostics; not stored in endpoint response-cache records.
SEARCH_TIMING_HEADERS=true
```

---

## How the cache works (behavioral model)

### 1) Cache keying (correctness)

Cache keys are built from:

- **HTTP method**
- **URL path**
- **Normalized query string** (sorted, preserves duplicates and bracket notation; uses `request.scope["query_string"]`)
- **Selected request headers that affect representation**:
  - `Accept`
  - `Accept-Encoding`
- **Endpoint parameters** (function args excluding the `request` object)

This prevents collisions like:

- `?a=1&b=2` vs `?b=2&a=1`
- gzip vs identity encoding
- different `Accept` values

### 2) Two-level serving path

For public cached GET endpoints, the serving path is:

1. Try Redis L1.
2. If Redis misses, try durable Postgres L2.
3. If Postgres L2 hits, rehydrate Redis and return that response.
4. If both miss, compute the endpoint response, store Redis L1, store Postgres
   L2, and tag both.

The durable L2 rows use the same hard expiry as the Redis response records. They
are a rebuildable cache warehouse, not an archive.

Create or repair the durable response cache tables with:

```bash
make api-response-cache-init
make kamal-api-response-cache-init KAMAL_DEST=dev1
```

Prune expired durable response rows with:

```bash
make api-response-cache-prune
make kamal-api-response-cache-prune KAMAL_DEST=dev1
```

Kamal cron runs this prune hourly so the Postgres L2 response cache stays
bounded even when Redis has been reset or public search traffic is high.

### 3) Stored payloads (binary-safe)

We cache **the full response body bytes** plus minimal metadata:

- `status` (only 200 responses are cached)
- `headers` (filtered subset; excludes hop-by-hop and runtime headers)
- `etag` (weak ETag derived from body bytes)
- `soft_exp` and `hard_exp` timestamps

This avoids fragile “serialize a Response object” behavior.

### 4) TTL model: Soft TTL + Hard TTL

Each cached record has:

- **Soft TTL** (the endpoint’s configured TTL)
  - before soft TTL: **HIT**
  - after soft TTL: **STALE** (still served, but triggers refresh in background)
- **Hard TTL** (`CACHE_HARD_TTL_SECONDS`, default = `2 * ttl`)
  - after hard TTL: treated as a miss

### 5) Stampede protection (singleflight)

On a miss, the system attempts to acquire a per-key Redis lock:

- If lock is acquired, it recomputes once and stores the result.
- If lock is not acquired, it briefly waits (`CACHE_LOCK_WAIT_SECONDS`) for another worker to fill the cache, then serves that cached value if available.

### 6) stale-if-error

If refresh/recompute fails, the system can extend the **hard expiry** by `STALE_IF_ERROR_SECONDS` (bounded by `MAX_STALE_EXTENSION_SECONDS`) so clients still get responses during upstream outages.

---

## HTTP semantics: ETag + 304 + Cache-Control

Cached endpoints include:

- `ETag: W/"<sha256>"`
- `Cache-Control: public, max-age=0, s-maxage=<ttl>, stale-while-revalidate=<...>, stale-if-error=<...>`
- `Vary: Accept-Encoding, Accept`

If the client sends `If-None-Match: <etag>`, the API will return **304 Not Modified** (when served from cache).

---

## Asset endpoints (thumbnails + static maps)

This repo has two *image asset* families that are backed by Redis object caches and
durable database storage:

- Thumbnails: `GET /api/v1/thumbnails/{resource_id}`
- Static maps: `GET /api/v1/static-maps/{resource_id}`

Generated thumbnail/static-map bytes are persisted in `generated_visual_assets`;
resource-to-asset mappings are persisted in `generated_visual_asset_links`.
On a Redis miss, the API can recover the resource alias, serve the durable
asset, and rehydrate Redis. Redis is the hot serving layer; the database is the
durable fallback across cache churn, restarts, and deploys.
`VISUAL_ASSET_CACHE_TTL_SECONDS=0` stores these hot Redis keys without expiry.
Kamal environments set `VISUAL_ASSET_CACHE_TTL_SECONDS=604800` so Redis DB 1
stays bounded while Postgres remains the durable visual asset store.
Kamal Redis also starts with `--maxmemory` (default `12gb`) and
`--maxmemory-policy volatile-lru`, so TTL-backed cache keys are evicted before
cache growth can consume the whole VM. Override with `REDIS_MAXMEMORY` /
`REDIS_MAXMEMORY_POLICY` only after sizing the host.

### Best-practice semantics used here

- **Revalidation-style caching** on the image endpoints:
  - `ETag` + `If-None-Match` → `304 Not Modified`
  - `Cache-Control: public, max-age=0, s-maxage=...` with SWR / stale-if-error
  - This allows CDNs to cache aggressively, while ensuring clients don’t get pinned to stale/broken images when the Redis object TTL expires.

- **Priming for hot paths**:
  - `make prime-thumbnail-cache`, `make prime-static-map-cache`, and `make prime-visual-caches` generate assets ahead of user traffic.
  - On Kamal, `make kamal-prime-visual-caches KAMAL_DEST=dev1` warms thumbnail plus static-map/icon Redis entries; pair it with `make kamal-prime-resource-cache KAMAL_DEST=dev1` before collecting performance HARs.
  - Run `make resource-aux-init` before first priming on a new environment so `generated_visual_assets` and `generated_visual_asset_links` exist.
  - After a Redis reset, priming first tries to rehydrate from durable visual storage before regenerating remote thumbnails or static maps.
  - Full static-map priming defaults to durable assets/links plus small Redis aliases only. Use `PRIME_STATIC_MAP_HYDRATE_ASSETS=1` only for small hotsets when Redis DB 1 should hold the PNG bodies. Full-corpus static-map body hydration is refused unless `PRIME_ALLOW_FULL_HYDRATION=1` is also set.
  - Static-map and resource-class-icon priming also writes a latest-asset alias, letting hot gallery redirects skip the database and jump straight to the immutable `/static-map-assets/{hash}` URL.
  - Resource/search JSON only needs those immutable asset URLs, so resource representation generation rehydrates aliases from durable storage without pulling full static-map PNG bodies back into Redis.
  - Priming scripts default `VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS=900`, so if Redis restarts and reports `Redis is loading the dataset in memory`, the job waits and retries instead of counting thousands of transient cache operations as failed resources.
  - For large local catch-up runs on disk-constrained laptops, temporarily start Redis in in-memory mode with `REDIS_APPENDONLY=no` and `REDIS_SAVE=""`. The durable bytes and resource-to-asset links still land in Postgres, while Redis avoids building giant AOF/RDB files during the warm-up.
  - After a local priming run, `make visual-assets-export` can package just those generated asset rows, and `make visual-assets-sync-all` can promote them to `dev1`, `dev2`, and `prd` without repeating expensive generation on every server. Exports now include a small manifest with row counts and asset byte totals so each destination can verify the staged import before cutover.
  - When you only need one Kamal destination and local disk is tight, `make visual-assets-stream-import KAMAL_DEST=dev1` streams those same rows directly from local ParadeDB into staged remote tables without writing a large local dump archive first. The live remote tables stay in place until the staged counts verify, then the staged tables swap in atomically and the previous live copy is preserved in `visual_asset_backup`.
  - Priming logs individual broken upstream assets without exiting nonzero, so a handful of bad provider images do not block the rest of the warming run. Use `python scripts/prime_thumbnail_cache.py --strict-failures` or `python scripts/prime_static_map_cache.py --strict-failures` when a diagnostic run should fail on any asset error.

- **Non-cacheable placeholders** for “not ready” states:
  - `GET /api/v1/resources/{id}/static-map` always returns an **image** (SVG placeholder while a background job generates the PNG), with `Cache-Control: no-store`.
  - Placeholders must be `no-store` so intermediate caches don’t pin “processing” responses.

---

## Tag-based invalidation (fast, safe)

Each cached response is indexed under one or more **tags** in Redis and durable
Postgres L2, for example:

- `search` (all search-related cached responses)
- `suggest`
- `resource` (all resource endpoints)
- `resource:<id>` (specific resource)
- `gazetteer`
- `facet:<facet_name>`
- `ns:<python_namespace_of_handler>` (fine-grained namespace tag)

### Admin purge endpoint (basic auth required)

There is an admin endpoint to purge caches:

- `POST /api/v1/admin/cache/purge`

Examples:

```bash
# Purge all search caches
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
  -X POST "http://localhost:8000/api/v1/admin/cache/purge" \
  -H "Content-Type: application/json" \
  -d '{"tags":["search"]}'

# Purge a specific resource
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
  -X POST "http://localhost:8000/api/v1/admin/cache/purge" \
  -H "Content-Type: application/json" \
  -d '{"tags":["resource:123-abc"]}'

# Emergency nuke (flush the Redis DB used by the app)
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
  -X POST "http://localhost:8000/api/v1/admin/cache/purge" \
  -H "Content-Type: application/json" \
  -d '{"flush_all":true}'
```

### Document/event-driven invalidation

When documents/resources are updated (or background tasks modify a resource), the code invalidates:

- `resource:<id>`
- `search` (coarse, because resource updates affect search results)

See:

- `backend/app/events/document_events.py`
- `backend/app/services/admin_service.py`

---

## End-to-end verification (copy/paste)

### 1) Confirm caching is enabled and headers are visible

Ensure:

```text
ENDPOINT_CACHE=true
CACHE_DEBUG_HEADERS=true
```

Then hit a cacheable endpoint twice:

```bash
curl -sD - -o /dev/null "http://localhost:8000/api/v1/search?q=test" | egrep -i 'x-cache|etag|cache-control|vary'
curl -sD - -o /dev/null "http://localhost:8000/api/v1/search?q=test" | egrep -i 'x-cache|etag|cache-control|vary'
```

Expected:

- First request: `X-Cache: MISS`
- Second request: `X-Cache: HIT` (or `STALE` if you’re past the soft TTL)

### 2) Verify query-string normalization (same params, different order)

```bash
curl -sD - -o /dev/null "http://localhost:8000/api/v1/search?a=1&b=2" | egrep -i 'x-cache'
curl -sD - -o /dev/null "http://localhost:8000/api/v1/search?b=2&a=1" | egrep -i 'x-cache'
```

The second request should be a HIT (same canonical key).

### 3) Verify 304 Not Modified (ETag)

```bash
ETAG=$(curl -sD - -o /dev/null "http://localhost:8000/api/v1/search?q=test" | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r')
curl -sD - -o /dev/null -H "If-None-Match: $ETAG" "http://localhost:8000/api/v1/search?q=test" | head
```

Expected: `HTTP/1.1 304 Not Modified`

### 4) Verify gzip + caching interop

Because the cache varies on `Accept-Encoding`, gzip and identity responses are keyed separately.

```bash
curl -sD - -o /dev/null -H "Accept-Encoding: gzip" "http://localhost:8000/api/v1/search?q=test" | egrep -i 'content-encoding|x-cache|etag|vary'
curl -sD - -o /dev/null -H "Accept-Encoding: gzip" "http://localhost:8000/api/v1/search?q=test" | egrep -i 'content-encoding|x-cache|etag|vary'
```

Expected:

- `Content-Encoding: gzip` (if gzip middleware is enabled)
- `X-Cache: MISS` then `HIT`

---

## Operational tips (production)

### Start conservative, then dial up

- Turn on caching only for public endpoints (already the case via decorators).
- Start with low TTLs on `/search` (e.g., 30–120s) and higher TTLs for stable resources.

### Safe cache rollouts

If you change the cache record format or want a clean slate:

- bump `CACHE_APP_VERSION` (recommended), or
- bump `CACHE_VERSION` (bigger hammer)

This avoids needing a live `flush_all`.

### Troubleshooting checklist

- **No cache hits**:
  - confirm `ENDPOINT_CACHE=true`
  - verify Redis connectivity (`REDIS_HOST/PORT/PASSWORD/DB`)
  - set `CACHE_DEBUG_HEADERS=true` and watch `X-Cache`
- **Unexpected misses**:
  - check `Vary` inputs: `Accept`, `Accept-Encoding`
  - confirm query strings are identical after normalization
- **Redis latency**:
  - tune `REDIS_TIMEOUT_SECONDS`
  - keep Redis close to the API network-wise
