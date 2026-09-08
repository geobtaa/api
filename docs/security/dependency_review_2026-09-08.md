# Dependency security review — September 8, 2026

Reviewed GitHub's open Dependabot and CodeQL alerts after PR #388 merged into
`develop`. The starting snapshot contained 96 dependency alerts (1 critical,
56 high, 31 medium, 8 low) and one high-severity CodeQL alert.

## Changes and expected reduction

Updated backend pins for Pillow, aiohttp, and Tornado, raised the MCP minimum,
and refreshed their locked versions plus cryptography. Updated affected frontend
packages within the existing version ranges and raised the tar override to
`^7.5.21`. The lockfiles were regenerated with the package managers.

Comparing every reported vulnerable range against the updated lockfiles places
92 of the 96 original dependency alerts outside their vulnerable ranges:

| Manifest group | Critical | High | Medium | Low | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Backend | 0 | 28 | 12 | 2 | 42 |
| Frontend | 1 | 25 | 19 | 5 | 50 |

These are expected reductions, not confirmed GitHub closures. GitHub must ingest
the updated manifests on its monitored branch. Some backend advisories appear
against both the manifest and lockfile; these counts represent alerts, not
unique vulnerabilities. The fresh npm audit additionally reports 17 affected
package entries, including parent packages and findings outside the original
GitHub snapshot; its counts are not directly comparable to Dependabot alerts.

## Remaining priorities

- [Jaeger propagator #352](https://github.com/geobtaa/api/security/dependabot/352):
  high-severity malformed-header denial of service. Upgrade the OpenTelemetry
  SDK/instrumentation chain together and verify tracing compatibility. This is
  the next runtime dependency priority.
- [sharp #354](https://github.com/geobtaa/api/security/dependabot/354): high-severity
  native image-library vulnerabilities. The PWA asset toolchain retains a
  vulnerable version; update that toolchain to support sharp 0.35 or later.
- [extract-zip #385](https://github.com/geobtaa/api/security/dependabot/385):
  high-severity archive path traversal in the accessibility tooling's Puppeteer
  dependency chain. GitHub reports no patched version. Track an upstream fix or
  replacement; do not apply npm's suggested major downgrade blindly.
- [body-parser #348](https://github.com/geobtaa/api/security/dependabot/348):
  GitHub labels this low severity, while the fresh npm audit labels the affected
  chain moderate. Update Express/body-parser together; the current Express
  dependency retains an affected parser version.
- [CodeQL #98](https://github.com/geobtaa/api/security/code-scanning/98): the
  SHA-256 API-key fallback supports legacy stored hashes and migrates them to
  PBKDF2 after successful validation. New keys already use PBKDF2. Retiring this
  fallback needs a compatibility/migration plan for unused older keys. The
  fallback is unchanged and the alert has not been dismissed or suppressed.

## Validation

- Backend manifest/lockfile consistency: `uv lock --project backend --check`.
- Backend `make lint-check`: passed using the locked development environment.
- Focused static-map, MCP service/API, and image-worker regressions: 56 passed
  using the updated backend environment.
- Broader image-service run: 47 passed before interruption during Celery
  connection handling; this was not a complete backend suite pass.
- Frontend `npm ci --ignore-scripts`: passed; lifecycle scripts were disabled.
- Frontend `npm test -- --run`: 81 files, 999 tests passed.
- Frontend `npm run build`: passed.
- Frontend `npm run lint`: 91 errors and 18 warnings in unchanged application
  source; frontend lint remains a separate quality backlog.
- Local `make frontend-reset`: completed after the dependency changes.
