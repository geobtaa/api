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
make k6-stress K6_BASE_URL=https://geo.btaa.org
```

### Change the query or pin a known resource

```bash
make k6-stress K6_QUERY=chicago
make k6-stress K6_RESOURCE_ID=p16022coll206:283
```

If `K6_RESOURCE_ID` is not provided, the suite discovers one from the first
search result for `K6_QUERY`.

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
- `K6_API_TARGET_VUS`
- `K6_API_RAMP_UP`
- `K6_API_HOLD`
- `K6_API_RAMP_DOWN`
- `K6_API_THINK_TIME_SECONDS`
- `K6_QUERY`
- `K6_SUGGEST_QUERY`
- `K6_RESOURCE_ID`
- `K6_SEARCH_PER_PAGE`
- `K6_CACHE_BUST_SEARCH`
- `K6_ENDPOINT_BREAKDOWN`

### Force search miss-path traffic

When you want to measure the uncached search/facet path instead of the warmed
response-cache path, enable cache busting for search-like requests:

```bash
make k6-stress K6_CACHE_BUST_SEARCH=1
```

This appends an ignored `k6cb=...` query param to:

- `/search`
- faceted `/search`
- `/api/v1/search`
- faceted `/api/v1/search`
- `/api/v1/search/facets/<facet_name>`

That preserves the existing API/HTML payload shape while forcing unique
search/facet request URLs, which is useful for finding the true miss-path
latency ceiling on `dev1` or `prd`.

Add `K6_ENDPOINT_BREAKDOWN=1` when you need per-endpoint `p95`/`p99` rows in
the k6 summary. This is useful after scenario-level thresholds fail and you
need to see which tagged endpoint is carrying the tail latency.

The frontend scenario treats `/search` as a browser flow: it requests the HTML
shell and then requests `/search/results` for the JSON data that the hydrated
client fetches through the keyed frontend BFF route. This keeps the API-key
throttling path represented in frontend load tests without blocking SSR on the
search payload.

## Backend search knobs

Two backend env vars are useful when tuning facet-heavy search behavior:

- `SEARCH_FACET_CACHE_TTL`
  Controls how long normalized search facet blocks and facet-value buckets stay
  hot in Redis. Default: `3600` seconds.
- `SEARCH_TIMING_LOG_THRESHOLD_MS`
  Controls when the backend logs aggregation timing summaries at `info` instead
  of `debug`. Default: `750` milliseconds.

The new aggregation timing logs are emitted from the backend search layer and
distinguish cache hits from full Elasticsearch aggregation misses, which makes
it easier to compare warm and miss-path behavior during k6 runs.

The API search endpoint also now emits `search_response_timing` debug logs that
break down the `/api/v1/search` assembly path into search, representation-cache
lookup, DB fallback, miss prefetch, miss build, and response-build stages.

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
