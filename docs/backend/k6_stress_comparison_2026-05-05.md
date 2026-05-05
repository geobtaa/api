# k6 stress comparison, 2026-05-05

Production was recently resized to 12 vCPUs. This run compared the current
dev1 and prd code/config path using the k6 mixed frontend/API profile, then
checked production with direct API-only profiles after creating a k6-only
unlimited production API key.

## Executive summary

- dev1 cleanly sustained the mixed `6 frontend VUs + 18 API VUs` profile at
  40.09 requests/second with 0% HTTP failures and API p95 of 988 ms.
- prd did not yet show the expected 12-vCPU headroom under the same mixed
  profile. The first valid keyed mixed run reached 19.01 requests/second, but
  had 14.1% HTTP failures and API p95 of 4.95 s.
- The mixed prd failures are not a raw CPU capacity result. The frontend
  `/search/results` BFF route is still being evaluated as the anonymous
  10-requests/minute tier because nginx injects the server-side
  `BTAA_GEOSPATIAL_API_KEY`, and that key is not currently a valid unlimited API
  key in production.
- Direct keyed API traffic on prd is clean at lower concurrency:
  `6 API VUs` sustained 6.40 requests/second with 0% failures, 100% checks, and
  API p95 of 1.49 s.
- Direct keyed API traffic at `18 API VUs` stayed error-free but missed the API
  latency SLO: 7.91 requests/second, 0% failures, API p95 of 4.86 s.
- Search server timing stayed low while client latency rose. The likely
  bottleneck is outside Elasticsearch/search assembly, with the strongest
  candidate being per-request API-key validation: `API_KEY_HASH_ITERATIONS` is
  600,000 PBKDF2 rounds and validation runs before the unlimited-tier rate
  limit skip can take effect.

## AppSignal baseline

Previous AppSignal production traffic analysis covered
`2026-02-01T00:00:00Z` through `2026-05-01T00:00:00Z` for the `web`
namespace `transaction_duration` count.

| Metric | Value |
| --- | ---: |
| Total web transactions | 20,019,759 |
| Hourly samples | 2,137 |
| Average traffic | 9,368/hour, 2.60 requests/second |
| Peak hourly traffic | 35,270/hour, 9.80 requests/second |

## Test matrix

All k6 runs used cache-busted search/facet URLs and per-endpoint breakdowns.
Production runs used `https://lib-geoportal-prd-web-01.oit.umn.edu`; the public
`https://geo.btaa.org` hostname returned the legacy Rails/Blacklight surface for
these API paths and is not the Kamal API target for this test.

| Environment/profile | Result | Requests/sec | Requests/hour | vs avg AppSignal | vs peak AppSignal | Failure rate | API p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev1 mixed, 6 frontend VUs + 18 API VUs | Clean | 40.09 | 144,341 | 15.4x | 4.1x | 0.0% | 988 ms |
| prd mixed, keyed, 6 frontend VUs + 18 API VUs | Not valid capacity | 19.01 | 68,437 | 7.3x | 1.9x | 14.1% | 4.95 s |
| prd API-only, keyed, 18 API VUs | Error-free, latency failed | 7.91 | 28,467 | 3.0x | 0.8x | 0.0% | 4.86 s |
| prd API-only, keyed, 6 API VUs | Clean | 6.40 | 23,053 | 2.5x | 0.7x | 0.0% | 1.49 s |

## Key setup

A k6-only production API key was created on 2026-05-05 and assigned to the
unlimited `btaa_secondary` tier. The key id is `130`. The key value is stored
locally in the ignored file `tmp/k6/prd-k6.env` as `K6_API_KEY=...`.

Use it like this:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-stress K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu
```

Do not commit the key or paste it into reports.

## Commands run

dev1 mixed:

```bash
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-dev1-6frontend-18api-cache-bust-endpoint-breakdown-summary.json \
  K6_BASE_URL=https://lib-btaageoapi-dev-app-01.oit.umn.edu \
  K6_FRONTEND_TARGET_VUS=6 \
  K6_API_TARGET_VUS=18 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1
```

prd mixed, keyed:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-prd-6frontend-18api-cache-bust-endpoint-breakdown-keyed-summary.json \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_FRONTEND_TARGET_VUS=6 \
  K6_API_TARGET_VUS=18 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1
```

prd API-only, keyed:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-prd-api-only-18-cache-bust-endpoint-breakdown-keyed-summary.json \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_ENABLE_FRONTEND=0 \
  K6_API_TARGET_VUS=18 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1
```

prd API-only lower-concurrency check:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-prd-api-only-6-cache-bust-endpoint-breakdown-keyed-summary.json \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_ENABLE_FRONTEND=0 \
  K6_API_TARGET_VUS=6 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1
```

## Endpoint observations

dev1 mixed endpoint p95s:

| Endpoint | p95 |
| --- | ---: |
| direct `/api/v1/search` | 1.15 s |
| direct faceted `/api/v1/search` | 1.13 s |
| direct `/api/v1/search/facets/<facet>` | 1.04 s |
| frontend `/search/results` | 2.39 s |
| frontend faceted `/search/results` | 2.21 s |
| frontend resource page | 2.34 s |

prd keyed mixed endpoint p95s:

| Endpoint | p95 |
| --- | ---: |
| direct `/api/v1/search` | 6.28 s |
| direct faceted `/api/v1/search` | 6.69 s |
| direct `/api/v1/search/facets/<facet>` | 5.26 s |
| frontend `/search/results` | 1.34 s |
| frontend faceted `/search/results` | 1.34 s |
| frontend resource page | 1.75 s |

prd keyed API-only, 6 VUs:

| Endpoint | p95 |
| --- | ---: |
| direct `/api/v1/search` | 1.85 s |
| direct faceted `/api/v1/search` | 1.66 s |
| direct `/api/v1/search/facets/<facet>` | 1.53 s |
| `/api/v1/resources/` | 909 ms |
| `/api/v1/resources/<resource_id>` | 958 ms |
| `/api/v1/suggest` | 998 ms |
| `/api/v1/home/blog-posts` | 940 ms |

## What moved the needle?

The extra production CPUs are allocated in a sensible place for the current
single-host layout:

- `WEB_UVICORN_WORKERS=4` for the public API pool.
- `WEB_INTERNAL_UVICORN_WORKERS=6` for frontend/BFF/internal API traffic.
- `WEB_SSR_WORKERS=4` for React Router SSR/BFF workers.

That should give prd more isolation than dev1's smaller `3 / 4 / 3` profile.
The k6 result does not prove that the extra CPUs are ineffective; it proves that
the current production request path is spending enough work before or around
rate limiting/API-key validation to mask the extra worker capacity.

The strongest evidence is the gap between client latency and search server
timing:

| Profile | Client search p95 | `search_server_timing_total` p95 |
| --- | ---: | ---: |
| dev1 mixed | 1.29 s | 54 ms |
| prd mixed keyed | 5.03 s | 119 ms |
| prd API-only keyed, 18 VUs | 6.02 s | 62 ms |
| prd API-only keyed, 6 VUs | 1.76 s | 12 ms |

The search work itself is not where the multi-second tail is coming from.

## Required follow-up

1. Rotate or register the production `BTAA_GEOSPATIAL_API_KEY` used by nginx for
   `/search/results` so frontend BFF requests land in an unlimited tier instead
   of anonymous rate limiting.
2. Add a short-lived API-key validation cache or otherwise remove the
   600,000-round PBKDF2 check from every request on hot paths. Unlimited-tier
   requests still pay validation before the rate-limit check is skipped.
3. Rerun the same mixed `6 frontend VUs + 18 API VUs` profile after the BFF key
   and key-validation changes.
4. Treat the current clean production sustain number as `6.40 requests/second`
   under the API-only SLO. That is about 2.5x average historic traffic, but only
   about 65% of the historic hourly peak. The production goal should be to clear
   the mixed profile at or above dev1's 40 requests/second result, which would
   represent roughly 4x the historic hourly peak with the current k6 mix.
