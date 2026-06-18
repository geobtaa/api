# BTAA Geospatial API

This repository is the application platform for the Big Ten Academic Alliance
geospatial discovery experience. It brings together a public search interface,
a standards-oriented API, catalog metadata pipelines, generated map and
thumbnail assets, analytics, MCP access, and client tools for people working
with geospatial library collections.

The work here is centered on a simple idea: make consortium-scale geospatial
metadata easier to discover, reuse, preserve, and connect to other research and
library systems. The website is one expression of that work, but the repository
also supports API consumers, GIS users, campus integrations, operational
workflows, and future agent-facing discovery tools.

## What This System Does

- Serves a public Geoportal web application for searching and viewing BTAA
  geospatial resources.
- Exposes resource, search, facet, map, citation, download, metadata, analytics,
  and administration APIs.
- Stores canonical resource records in Postgres/ParadeDB and indexes discovery
  documents into Elasticsearch.
- Harvests and normalizes metadata from OpenGeoMetadata, legacy GBL Admin data,
  bridge services, fixtures, and related upstream systems.
- Generates and caches thumbnails, static maps, icons, resource representations,
  and API responses so discovery stays fast.
- Provides MCP bridge support so search and resource retrieval can be used from
  Claude Desktop and other Model Context Protocol clients.
- Includes a QGIS plugin, command-line client, and Slack slash command for users
  who want access outside the browser.

## Repository Map

- `backend/`: FastAPI application, service layer, database models, migrations,
  Celery tasks, ingest/index scripts, fixtures, and backend tests.
- `frontend/`: React/TypeScript Geoportal interface, Vite/React Router app
  code, frontend tests, and browser-facing assets.
- `cli/`: Python command-line client for searching the API, reading schemas,
  and fetching resource records.
- `qgis-plugin/`: QGIS desktop plugin for searching the catalog and loading
  spatial resources into a map canvas.
- `mcp/`: Local MCP stdio, HTTP, and WebSocket bridge helpers plus desktop client
  configuration templates.
- `docs/slack/`: Public Slackbot integration stub.
- `docs/`: Local development, architecture, testing, public API, and
  restricted-topic stub documentation.
- `mkdocs/`: Public documentation site for API specifications, linked data,
  tutorials, and external-facing reference material.
- `config/`: Runtime and deployment configuration. Detailed deployed-environment
  procedures are restricted operations material.
- `performance/`: k6 and related performance testing harness assets. Detailed
  capacity reports are restricted operations material.
- `scripts/`: Repository-level utility scripts.
- `data/`: Local data volumes and development data artifacts.
- `docker-compose.yml`: Local application stack for the API, frontend dev
  server, Postgres/ParadeDB, Elasticsearch, Redis, Celery, and Flower.
- `Makefile`: Main developer entry point for linting, tests, ingest,
  reindexing, cache work, and docs. Remote operations targets may exist, but
  public docs do not publish deployed-environment procedures.

## Local Proxy

The local browser-facing proxy is provided by the React Router frontend dev
server at `http://localhost:3000`. It is not a separate service: start the
normal Docker stack and open the frontend URL.

```bash
cp .env.example .env
docker compose up -d
```

The backend API remains available directly at `http://localhost:8000/api/v1`,
but the frontend uses same-origin proxy routes for request paths that should run
through server-side loaders, carry the server-side API key, or avoid browser
CORS/rate-limit surprises. Common local proxy routes include:

- `http://localhost:3000/search/results` -> `/api/v1/search`
- `http://localhost:3000/search/facets/:facetName` ->
  `/api/v1/search/facets/:facetName`
- `http://localhost:3000/map/h3` -> `/api/v1/map/h3`
- `http://localhost:3000/home/blog-posts` -> `/api/v1/home/blog-posts`
- `http://localhost:3000/places/suggest` -> `/api/v1/places/suggest`
- `http://localhost:3000/resources/:id/thumbnail` ->
  `/api/v1/resources/:id/thumbnail`
- `http://localhost:3000/resources/:id/static-map` ->
  `/api/v1/resources/:id/static-map`
- `http://localhost:3000/static-maps/...` and
  `http://localhost:3000/thumbnails/...` for generated map and thumbnail assets

There are two API base URLs to keep straight in local development:

- `VITE_API_BASE_URL` is compiled into browser code. Docker sets it to
  `http://localhost:8000/api/v1` so direct browser API calls use the host port.
- `API_BASE_URL` is read by React Router server-side loaders. Docker sets it to
  `http://api:8000/api/v1` because the frontend container reaches the API by
  service name on the Docker network.

If you run the frontend outside Docker, point the server-side proxy back at the
host API:

```bash
cd frontend
API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

Set `BTAA_GEOSPATIAL_API_KEY` when you want local proxy requests to forward an
API key as `X-API-Key`; otherwise they use the public/anonymous API behavior.
Localhost skips the frontend Turnstile gate by default. To exercise that flow
locally, set `VITE_TURNSTILE_ENABLE_LOCAL=true` along with the Turnstile test
configuration.

If proxy requests fail, first check that the API is reachable from the frontend
server context: use `http://api:8000/api/v1` from Docker and
`http://localhost:8000/api/v1` from host-run dev servers. Useful commands:

```bash
docker compose logs -f frontend api
make frontend-reset
```

## Documentation

Setup, development, and operations notes live in `docs/`:

- Internal documentation handbook: [docs/README.md](docs/README.md)
- Documentation security policy: [docs/security_docs_policy.md](docs/security_docs_policy.md)
- Local setup and development: [docs/development.md](docs/development.md)
- Codebase overview: [docs/backend/codebase_overview.md](docs/backend/codebase_overview.md)
- Backend testing: [docs/backend/testing.md](docs/backend/testing.md)
- Frontend docs: [docs/frontend/README.md](docs/frontend/README.md)
- Make tasks: [docs/make_tasks.md](docs/make_tasks.md)
- Deployment stub: [docs/deploying.md](docs/deploying.md)
- Deployment runbook stub: [docs/backend/deployment.md](docs/backend/deployment.md)
- Analytics stub: [docs/analytics.md](docs/analytics.md)
- OpenGeoMetadata harvesting: [docs/backend/ogm_harvesting.md](docs/backend/ogm_harvesting.md)
- MCP / Claude Desktop: [docs/mcp/README.md](docs/mcp/README.md)
- Slackbot stub: [docs/slack/README.md](docs/slack/README.md)
- QGIS plugin testing: [qgis-plugin/docs/testing.md](qgis-plugin/docs/testing.md)

The public documentation site is maintained separately under `mkdocs/`.
Detailed deployment, host, secret, backup, incident, capacity, dashboard, and
production operations live in restricted operations documentation and are not
published in this repository.
