# dev2 k6 launch readiness, 2026-05-06

This report documents the dev2 mixed frontend/API k6 validation after enabling
rate limiting and deploying the API-key/DB-connection capacity fixes.

## Executive summary

- dev2 now clears the 50 RPS launch target with rate limiting enabled.
- The 5-minute launch soak at `4 frontend VUs + 8 API VUs` sustained
  `82.55 requests/second`, with 0 HTTP failures and 100% successful checks.
- The higher headroom step at `6 frontend VUs + 12 API VUs` sustained
  `95.62 requests/second`, also with 0 HTTP failures and 100% successful
  checks.
- A frontend p95 ceiling sweep found the highest passing step at
  `14 frontend VUs + 28 API VUs`: `104.66 requests/second` with frontend
  scenario p95 `2.74 s`.
- The next heavier step, `18 frontend VUs + 36 API VUs`, crossed the
  frontend scenario p95 threshold: `100.41 requests/second` with frontend
  scenario p95 `3.41 s`.
- Against the current AppSignal historic production average
  (`2.69 requests/second`), the launch soak is `30.7x` current average traffic.
- Against the previous historic peak hour (`35,270/hour`, `9.80 requests/second`),
  the launch soak is `8.4x` peak production traffic.
- AppSignal traffic since the prior May 1 baseline did not set a new peak:
  May 1-May 6 max was `20,490/hour`, or `5.69 requests/second`.

## AppSignal traffic baseline

AppSignal production `transaction_duration` count for namespace `web` was
queried on May 6, 2026.

| Window | Total web transactions | Hourly samples | Average/hour | Average RPS | Peak/hour | Peak RPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-02-01 through 2026-05-06 | 21,864,394 | 2,257 | 9,687 | 2.69 | 35,270 | 9.80 |
| 2026-05-01 through 2026-05-06 | n/a | 121 | n/a | n/a | 20,490 | 5.69 |

The 90-day peak remains the earlier `35,270/hour` value captured in
`docs/backend/k6_stress_comparison_2026-05-05.md`; the May 1-May 6 follow-up
window stayed below that peak.

## Query-pool validation

The k6 harness now supports `K6_QUERY_POOL`, a comma- or pipe-separated list of
real search terms. The seed search still uses `K6_QUERY` to discover a stable
resource and facet values, while each frontend/API iteration rotates the actual
search and suggest terms through the pool.

The query-pool smoke run confirmed that varied search terms exercised the
semantic-cache miss path:

| Run | Requests | Failure rate | Checks | Semantic-cache hit rate | Search p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| query-pool smoke, 2 iterations | 31 | 0.00% | 100% | 0.00% | 1.17 s |

Summary file:

- `tmp/k6/dev2-querypool-smoke/smoke-summary.json`

## Mixed-load results

All runs targeted:

```text
https://lib-geoportal-dev-web-01.oit.umn.edu
```

All runs used:

- rate limiting enabled on dev2;
- the k6-only unlimited API key stored in `tmp/k6/dev2-k6.env`;
- `K6_CACHE_BUST_SEARCH=1`;
- `K6_ENDPOINT_BREAKDOWN=1`;
- `K6_SEARCH_DIAGNOSTICS=1`;
- a 24-term `K6_QUERY_POOL`.

| Profile | Duration | Result | Requests | RPS | Requests/hour | vs avg AppSignal | vs historic peak | vs May 1-May 6 peak | Failure rate | Checks | Overall p95 | API p95 | Frontend p95 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 frontend + 8 API | 5-minute hold | Clean | 29,943 | 82.55 | 297,172 | 30.7x | 8.4x | 14.5x | 0.00% | 100% | 204 ms | 166 ms | 946 ms |
| 6 frontend + 12 API | 3-minute hold | Clean | 23,084 | 95.62 | 344,232 | 35.5x | 9.8x | 16.8x | 0.00% | 100% | 289 ms | 249 ms | 1.27 s |

Summary files:

- `tmp/k6/dev2-launch-4f-8api-querypool-5m/stress-summary.json`
- `tmp/k6/dev2-headroom-6f-12api-querypool-3m/stress-summary.json`

## Frontend p95 ceiling sweep

The sweep below used the same mixed frontend/API flow, same 24-term query pool,
same k6-only unlimited API key, and explicit frontend threshold
`K6_FRONTEND_P95_THRESHOLD_MS=3000`.

| Profile | Result vs frontend scenario p95 < 3.0 s | Requests | RPS | Requests/hour | Failure rate | Checks | API p95 | Frontend scenario p95 | Search BFF p95 | Faceted BFF p95 | Resource page p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 frontend + 8 API | Pass | 29,943 | 82.55 | 297,172 | 0.00% | 100% | 166 ms | 946 ms | 475 ms | 510 ms | 1.71 s |
| 6 frontend + 12 API | Pass | 23,084 | 95.62 | 344,232 | 0.00% | 100% | 249 ms | 1.27 s | 991 ms | 654 ms | 2.05 s |
| 10 frontend + 20 API | Pass | 24,483 | 101.21 | 364,339 | 0.00% | 100% | 467 ms | 2.11 s | 2.11 s | 2.13 s | 3.17 s |
| 14 frontend + 28 API | Pass | 25,175 | 104.66 | 376,793 | 0.00% | 100% | 677 ms | 2.74 s | 3.91 s | 3.25 s | 3.48 s |
| 18 frontend + 36 API | Fail | 24,323 | 100.41 | 361,468 | 0.00% | 100% | 1.02 s | 3.41 s | 5.23 s | 4.44 s | 4.12 s |

The observed scenario-level ceiling is therefore between `14 frontend + 28 API`
and `18 frontend + 36 API`. In practical launch terms, dev2 absorbed about
`105 RPS` before the aggregate frontend p95 crossed `3.0 s`.

There is an important endpoint-level caveat: individual slow frontend paths
crossed `3.0 s` earlier than the aggregate frontend scenario. The resource page
hit p95 `3.17 s` at `10 frontend + 20 API`, and the search-result BFF paths
crossed `3.0 s` at `14 frontend + 28 API`. If the launch bar is "every frontend
endpoint p95 under 3.0 s," the defensible ceiling is below `101 RPS`, with the
last fully clean endpoint-level step at `95.62 RPS`.

Ceiling summary files:

- `tmp/k6/dev2-ceiling-10f-20api-querypool-3m/stress-summary.json`
- `tmp/k6/dev2-ceiling-14f-28api-querypool-3m/stress-summary.json`
- `tmp/k6/dev2-ceiling-18f-36api-querypool-3m/stress-summary.json`

## Endpoint details

### 4 frontend + 8 API launch soak

| Metric | p95 | p99 |
| --- | ---: | ---: |
| API scenario | 166 ms | 324 ms |
| Frontend scenario | 946 ms | 1.63 s |
| Direct `/api/v1/search` | 239 ms | 450 ms |
| Direct faceted `/api/v1/search` | 209 ms | 406 ms |
| Frontend `/search/results` BFF | 475 ms | 909 ms |
| Frontend faceted `/search/results` BFF | 510 ms | 1.01 s |
| Frontend resource page | 1.71 s | 1.88 s |

Search diagnostics:

- `search_response_duration` p95: `219 ms`
- semantic-cache hit rate: `98.97%`
- semantic-cache misses observed: `86`
- backend `search_server_timing_total` p95: `17 ms`

### 6 frontend + 12 API headroom step

| Metric | p95 | p99 |
| --- | ---: | ---: |
| API scenario | 249 ms | 369 ms |
| Frontend scenario | 1.27 s | 2.03 s |
| Direct `/api/v1/search` | 328 ms | 443 ms |
| Direct faceted `/api/v1/search` | 294 ms | 465 ms |
| Frontend `/search/results` BFF | 991 ms | 1.98 s |
| Frontend faceted `/search/results` BFF | 654 ms | 1.77 s |
| Frontend resource page | 2.05 s | 2.57 s |

Search diagnostics:

- `search_response_duration` p95: `318 ms`
- semantic-cache hit rate: `100.00%`
- backend `search_server_timing_total` p95: `27 ms`

The headroom run followed the launch soak, so the 24-term query pool was already
warm. That is acceptable for launch readiness because repeated search intent is
exactly what the semantic cache is designed to absorb. The smoke run above is
the separate proof that query-pool terms can hit the miss path successfully.

## Conclusion

dev2 is launch-ready for the 50 RPS target under this mixed frontend/API profile.
The conservative launch-soak number is `82.55 RPS`, which is `165%` of the
50 RPS goal and `8.4x` the historic production peak hour. The higher headroom
step reached `95.62 RPS`, or `191%` of the 50 RPS goal, without HTTP failures or
threshold failures.

For the specific frontend scenario p95 < `3.0 s` question, the highest passing
step observed was `104.66 RPS`; the next heavier step crossed the line at
frontend scenario p95 `3.41 s`. That makes the current practical frontend
scenario capacity about `100-105 RPS` under this mixed k6 profile.

The slowest remaining path is frontend resource page rendering, not the API
rate-limiting or search path. API p95 remained below `250 ms` even at the
higher headroom step and stayed near `1.02 s` even in the threshold-failing
18 frontend + 36 API run.

## Commands

Smoke:

```bash
make k6-smoke \
  K6_OUTPUT_DIR=tmp/k6/dev2-querypool-smoke \
  K6_BASE_URL=https://lib-geoportal-dev-web-01.oit.umn.edu \
  K6_API_KEY="$K6_API_KEY" \
  K6_ENABLE_FRONTEND=1 \
  K6_ENABLE_API=1 \
  K6_SMOKE_VUS=1 \
  K6_SMOKE_ITERATIONS=2 \
  K6_QUERY_POOL="minnesota|chicago|wisconsin|michigan|illinois|iowa|indiana|roads|water|lakes|rivers|elevation|imagery|land use|parcels|zoning|transportation|hydrology|soil|census|boundaries|historic maps|campus|flood" \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1 \
  K6_SEARCH_DIAGNOSTICS=1
```

Ceiling sweep runs used the same command shape with:

```bash
K6_FRONTEND_TARGET_VUS=10 K6_API_TARGET_VUS=20 K6_OUTPUT_DIR=tmp/k6/dev2-ceiling-10f-20api-querypool-3m
K6_FRONTEND_TARGET_VUS=14 K6_API_TARGET_VUS=28 K6_OUTPUT_DIR=tmp/k6/dev2-ceiling-14f-28api-querypool-3m
K6_FRONTEND_TARGET_VUS=18 K6_API_TARGET_VUS=36 K6_OUTPUT_DIR=tmp/k6/dev2-ceiling-18f-36api-querypool-3m
```

Launch soak:

```bash
make k6-stress \
  K6_OUTPUT_DIR=tmp/k6/dev2-launch-4f-8api-querypool-5m \
  K6_BASE_URL=https://lib-geoportal-dev-web-01.oit.umn.edu \
  K6_API_KEY="$K6_API_KEY" \
  K6_ENABLE_FRONTEND=1 \
  K6_ENABLE_API=1 \
  K6_FRONTEND_TARGET_VUS=4 \
  K6_FRONTEND_HOLD=5m \
  K6_API_TARGET_VUS=8 \
  K6_API_HOLD=5m \
  K6_QUERY_POOL="minnesota|chicago|wisconsin|michigan|illinois|iowa|indiana|roads|water|lakes|rivers|elevation|imagery|land use|parcels|zoning|transportation|hydrology|soil|census|boundaries|historic maps|campus|flood" \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1 \
  K6_SEARCH_DIAGNOSTICS=1
```

Headroom:

```bash
make k6-stress \
  K6_OUTPUT_DIR=tmp/k6/dev2-headroom-6f-12api-querypool-3m \
  K6_BASE_URL=https://lib-geoportal-dev-web-01.oit.umn.edu \
  K6_API_KEY="$K6_API_KEY" \
  K6_ENABLE_FRONTEND=1 \
  K6_ENABLE_API=1 \
  K6_FRONTEND_TARGET_VUS=6 \
  K6_FRONTEND_HOLD=3m \
  K6_API_TARGET_VUS=12 \
  K6_API_HOLD=3m \
  K6_QUERY_POOL="minnesota|chicago|wisconsin|michigan|illinois|iowa|indiana|roads|water|lakes|rivers|elevation|imagery|land use|parcels|zoning|transportation|hydrology|soil|census|boundaries|historic maps|campus|flood" \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1 \
  K6_SEARCH_DIAGNOSTICS=1
```
