# Performance Testing

This page documents the public-safe k6 harness for local development and
non-sensitive test setup.

Detailed performance reports, deployed targets, API-key locations, request-rate
thresholds, capacity ceilings, bottlenecks, launch-readiness conclusions, and
production baselines are restricted operations material.

## Harness

k6 scripts live under `performance/k6/`:

- `smoke.js` - quick frontend/API smoke coverage.
- `stress.js` - mixed frontend/API stress traffic.
- `endpoint_capacity.js` - fixed-rate endpoint exercise for development
  investigation.

Run from the repository root:

```bash
make k6-smoke K6_BASE_URL=http://host.docker.internal:8000
make k6-stress K6_BASE_URL=http://host.docker.internal:8000
make k6-endpoint-capacity K6_BASE_URL=http://host.docker.internal:8000
```

Use localhost or Docker-reachable local URLs for public examples. Do not commit
deployed URLs, API keys, run output from restricted environments, or capacity
findings to this repository.

## Common Local Variables

Useful variables include:

- `K6_BASE_URL`
- `K6_QUERY`
- `K6_RESOURCE_ID`
- `K6_ENABLE_FRONTEND`
- `K6_ENABLE_API`
- endpoint target and request-rate variables
- p95/p99 threshold variables for local experiments

Keep any variable values that identify deployed environments, internal traffic
profiles, or service limits in the restricted operations documentation.

## Output Hygiene

- Store local scratch output under `tmp/k6/`.
- Do not commit generated k6 summaries, HARs, screenshots, API keys, or
  dashboard exports.
- Summaries that describe deployed capacity, bottlenecks, failures, baselines,
  or launch readiness belong in restricted operations docs.

## Related Public Docs

- [Make Tasks](../make_tasks.md)
- [Caching Guide](caching.md)
- [Security Documentation Policy](../security_docs_policy.md)
