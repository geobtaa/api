# AGENTS.md - Context for AI agents

This file gives agents a compact reference for public, local-development work in
this repository. Detailed deployment, incident, host, secret, backup, and
production operations are restricted operations material and must not be
mirrored here.

For documentation classification rules, see
[docs/security_docs_policy.md](docs/security_docs_policy.md).

---

## Git Workflow And Pull Requests

This repository uses git-flow. Treat `develop` as the normal integration branch
for feature and bugfix work.

- Open pull requests against `develop`, not `main`, unless the user explicitly
  asks for a different base branch.
- Before creating or retargeting a PR, verify the base branch is `develop`.
- If a PR is accidentally opened against another branch, retarget it to
  `develop` and make sure GitHub Actions run afterward.

---

## Lint, Format, And Test

### Backend

Run from the project root:

- `make lint` - backend ruff check.
- `make format` - backend ruff format plus safe fixes.
- `make lint-check` - CI-style backend lint/format check with no edits.
- `make test` - backend tests with coverage, with Docker services available.
- `make test-no-coverage` - backend tests without coverage threshold.
- `make test-fast` - parallel backend tests without coverage.
- `make test-fresh-db` - recreate the local test database, then run tests.
- `make lint-test` - `lint-check` then backend tests.

Common test overrides include `COVERAGE_THRESHOLD`, `PARALLEL_WORKERS`,
`WALLCLOCK_TIMEOUT_SECONDS`, `TIMEOUT_GRACE_SECONDS`, and
`TIMEOUT_DUMP_STACKS`. See `Makefile` and [docs/make_tasks.md](docs/make_tasks.md).

### Frontend

Run from `frontend/`:

- `npm run lint`
- `npm run lint:fix`
- `npm run format`
- `npm run format:check`
- `npm test`
- `npm run test:watch`
- `npm run test:coverage`

See [docs/frontend/linting-and-formatting.md](docs/frontend/linting-and-formatting.md)
and [docs/frontend/testing.md](docs/frontend/testing.md).

---

## Local Docker

Local development uses Docker Compose for the API, frontend, database, search,
cache, worker, and Flower services.

- Start all: `docker compose up -d`
- Stop all: `docker compose down`
- Logs: `docker compose logs -f [service]`
- Rebuild one service: `docker compose up -d --build [service]`
- Restart one service: `docker compose restart [service]`

Require a local `.env`; copy from `.env.example` if needed. Do not commit local
credential values.

After changing frontend dependencies or Vite config, use
`make frontend-reset`, then hard-refresh the browser.

---

## Makefile

Prefer Makefile targets for shared local workflows so behavior and environment
loading stay consistent.

Useful local target groups:

- Code quality: `make lint`, `make format`, `make lint-check`, `make lint-test`
- Tests: `make test`, `make test-no-coverage`, `make test-fast`
- Local indexing: `make reindex`, `make reindex-benchmark`,
  `make verify-h3-index`
- Local caches/assets: `make clear_cache`, `make prime-thumbnail-cache`,
  `make prime-static-map-cache`, `make refresh-resource-caches`
- Public docs: `make docs-serve`, `make docs-build`
- CLI: `make cli-test`, `make cli-lint`, `make cli-format`, `make cli-build`

Remote deployment, backup, cache, indexing, bridge, worker, cron, host, and
network operations are restricted operations material. Public docs should keep
only safe stubs for those topics.

---

## Ingest And Index

BTAA and GBL fixture ingestion scripts live under `backend/scripts/`.
OpenGeoMetadata harvesting is implemented through the backend app, Celery, and
the OGM service modules.

Local reindexing:

```bash
make reindex
```

or:

```bash
docker compose exec api bash -lc "cd /app/backend && python scripts/reindex_atomic.py"
```

See [docs/backend/scripts.md](docs/backend/scripts.md) and
[docs/backend/ogm_harvesting.md](docs/backend/ogm_harvesting.md).

---

## Public Documentation Hygiene

- Do not duplicate long docs in `AGENTS.md`; link to safe public docs.
- When adding or changing Makefile targets, developer workflows, or
  developer-facing features, update the relevant `docs/*` files.
- Keep public docs focused on local development, tests, public API behavior,
  code architecture, and non-operational explanations.
- Keep hostnames, deployment commands, secret-file details, backup/restore
  procedures, incident playbooks, capacity reports, dashboard IDs, and deployed
  integration setup out of this public repo.
- If a requested documentation change touches restricted operations material,
  create or update a safe public stub and remind the maintainer to update the
  restricted operations docs.
