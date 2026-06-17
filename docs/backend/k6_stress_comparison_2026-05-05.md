# k6 stress comparison, 2026-05-05

Production was recently resized to 12 vCPUs. This report compares the current
dev1 and prd serving paths with the mixed k6 frontend/API stress profile after
fixing the production API-key path so prd is actually testable.

## Executive summary

- The first production mixed numbers were invalid because `/search/results`
  was falling back to the anonymous tier from the public test path.
- The corrected production BFF key path now returns
  `X-RateLimit-Limit: unlimited` from the same public URL k6 uses.
- dev1 sustained the full `6 frontend VUs + 18 API VUs` profile cleanly at
  `40.09 requests/second`, with API p95 `988 ms` and 0% failures.
- prd does **not** sustain that same full profile yet. At `6 frontend VUs +
  18 API VUs`, prd reached `20.07 requests/second` but failed with 4.84% HTTP
  failures and API p95 `5.04 s`.
- The corrected prd failure mode is real: Postgres reports
  `sorry, too many clients already`, which causes API-key validation and durable
  response-cache DB calls to fail; some requests then fall back into anonymous
  throttling and return 429s.
- prd is currently SLO-safe at `4 frontend VUs + 4 API VUs`: `12.57
  requests/second`, 0% failures, API p95 `1.05 s`, frontend p95 `1.02 s`.
- prd can run `4 frontend VUs + 8 API VUs` without HTTP failures at `14.44
  requests/second`, but API p95 rises to `2.11 s`, above the current 1.5 s API
  threshold.

## Production key fix

Two keys matter in the mixed k6 profile:

- direct API requests use the k6-only `K6_API_KEY`;
- frontend `/search/results` requests are proxied by nginx with the server-side
  `BTAA_GEOSPATIAL_API_KEY`.

The k6-only production key is stored locally in `tmp/k6/prd-k6.env`; its key id
is `130`, and it is assigned to an unlimited tier.

The running production frontend BFF key is key id `129`. It already existed, but
had an IP allowlist:

```text
68.168.169.54, 127.0.0.1, 172.18.0.1
```

That allowed the key to work from inside the host/container path, while public
k6 traffic from outside the host was rejected by the allowlist and treated as
anonymous. I cleared that allowlist for key id `129` so the production frontend
BFF route uses the unlimited tier for the public path.

Post-fix gate checks:

| Public prd request | Expected tier | Result |
| --- | --- | --- |
| `/search/results?...` | frontend BFF key, unlimited | `X-RateLimit-Limit: unlimited` |
| `/api/v1/search?...` with `K6_API_KEY` | k6 key, unlimited | `X-RateLimit-Limit: unlimited` |

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

## Corrected test matrix

All runs used cache-busted search/facet URLs and endpoint breakdowns. Production
runs used `https://lib-geoportal-prd-web-01.oit.umn.edu`.

| Environment/profile | Result | Requests/sec | Requests/hour | vs avg AppSignal | vs peak AppSignal | Failure rate | API p95 | Frontend p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dev1, 6 frontend + 18 API | Clean | 40.09 | 144,341 | 15.4x | 4.1x | 0.00% | 988 ms | 1.87 s |
| prd, 6 frontend + 18 API | Fails | 20.07 | 72,257 | 7.7x | 2.0x | 4.84% | 5.04 s | 1.03 s |
| prd, 4 frontend + 8 API | No failures, API SLO failed | 14.44 | 51,971 | 5.5x | 1.5x | 0.00% | 2.11 s | 1.03 s |
| prd, 4 frontend + 4 API | Clean | 12.57 | 45,258 | 4.8x | 1.3x | 0.00% | 1.05 s | 1.02 s |

## What moved the needle?

The 12-vCPU prd allocation is pointed at the right serving pools:

- public API workers: `WEB_UVICORN_WORKERS=4`
- internal frontend/BFF API workers: `WEB_INTERNAL_UVICORN_WORKERS=6`
- frontend SSR workers: `WEB_SSR_WORKERS=4`

But the extra CPU has exposed a connection-management ceiling rather than
delivering proportional throughput. Under the full dev1-equivalent profile,
Postgres runs out of available clients. The relevant request path includes:

- API-key validation and endpoint SQLAlchemy work, which must share the
  request-path SQLAlchemy engine so they do not multiply per-worker pools;
- durable API response cache reads/writes, which also touch Postgres;
- the normal endpoint database usage.

Once Postgres hits `too many clients already`, API-key validation cannot prove
the unlimited tier, so some requests fall back to anonymous behavior and return
429s. That is why the corrected high-load prd run has real 429 failures even
though both API keys are valid.

## Capacity conclusion

Current SLO-safe production capacity from these corrected k6 runs is
`12.57 requests/second`, or about `45,258 requests/hour`.

Compared with AppSignal historic traffic, that is:

- `4.8x` average production traffic;
- `1.3x` the peak historic hour.

If we allow API p95 to drift above the 1.5 s threshold, prd can run at least
`14.44 requests/second` with 0% HTTP failures, about `1.5x` the historic peak.
That is not the number to advertise as SLO-safe.

prd still does not match dev1's `40.09 requests/second` corrected mixed result.
The gap is not explained by code drift; it is explained by production-only
rate-limit/API-key enforcement plus Postgres connection pressure under the
larger worker profile.

## Commands

dev1 full mixed profile:

```bash
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-dev1-6frontend-18api-cache-bust-endpoint-breakdown-summary.json \
  K6_BASE_URL=https://lib-btaageoapi-dev-app-01.oit.umn.edu \
  K6_FRONTEND_TARGET_VUS=6 \
  K6_API_TARGET_VUS=18 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1
```

prd full mixed profile:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-prd-6frontend-18api-cache-bust-endpoint-breakdown-fixed-bff-summary.json \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_FRONTEND_TARGET_VUS=6 \
  K6_API_TARGET_VUS=18 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1 \
  K6_API_KEY="$K6_API_KEY"
```

prd lower mixed profile:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-prd-4frontend-8api-cache-bust-endpoint-breakdown-fixed-bff-summary.json \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_FRONTEND_TARGET_VUS=4 \
  K6_API_TARGET_VUS=8 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1 \
  K6_API_KEY="$K6_API_KEY"
```

prd SLO-safe mixed profile:

```bash
set -a
. tmp/k6/prd-k6.env
set +a
make k6-run K6_ENTRY=stress.js \
  K6_SUMMARY_EXPORT=tmp/k6/stress-2026-05-05-prd-4frontend-4api-cache-bust-endpoint-breakdown-fixed-bff-summary.json \
  K6_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu \
  K6_FRONTEND_TARGET_VUS=4 \
  K6_API_TARGET_VUS=4 \
  K6_CACHE_BUST_SEARCH=1 \
  K6_ENDPOINT_BREAKDOWN=1 \
  K6_API_KEY="$K6_API_KEY"
```

## Recommended follow-up

1. Fix production DB connection pressure before increasing worker counts again.
   Start with API-key validation and durable response-cache database access.
2. Add a short-lived API-key tier cache so unlimited keys do not require a DB
   lookup on every request.
3. Revisit `NullPool` usage in request hot paths. It protects against some
   event-loop issues, but under multi-worker production load it makes Postgres
   absorb avoidable connection churn.
4. Set explicit Postgres connection budget math for each prd process group:
   public API workers, internal API workers, SSR workers, worker, and cron.
5. Rerun the same three corrected prd profiles after connection changes. The
   success target is the dev1-equivalent `6 frontend + 18 API` profile passing
   with 0% failures and API p95 below 1.5 s.
