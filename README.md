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
- Includes a QGIS plugin and command-line client for users who want access
  outside the browser.

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
- `docs/`: Internal development, architecture, operations, testing, deployment,
  and runbook documentation.
- `mkdocs/`: Public documentation site for API specifications, linked data,
  tutorials, and external-facing reference material.
- `config/`: Deployment and runtime configuration, including Kamal and cron
  assets.
- `performance/`: k6 and related performance testing assets.
- `scripts/`: Repository-level utility scripts.
- `data/`: Local data volumes and development data artifacts.
- `docker-compose.yml`: Local application stack for the API, frontend dev
  server, Postgres/ParadeDB, Elasticsearch, Redis, Celery, and Flower.
- `Makefile`: Main developer/operator entry point for linting, tests, ingest,
  reindexing, cache work, docs, and deployment-support tasks.

## Documentation

Setup, development, and operations notes live in `docs/`:

- Local setup and development: [docs/development.md](docs/development.md)
- Codebase overview: [docs/backend/codebase_overview.md](docs/backend/codebase_overview.md)
- Backend testing: [docs/backend/testing.md](docs/backend/testing.md)
- Frontend docs: [docs/frontend/README.md](docs/frontend/README.md)
- Make tasks: [docs/make_tasks.md](docs/make_tasks.md)
- OpenGeoMetadata harvesting: [docs/backend/ogm_harvesting.md](docs/backend/ogm_harvesting.md)
- MCP / Claude Desktop: [docs/mcp/README.md](docs/mcp/README.md)
- QGIS plugin testing: [qgis-plugin/docs/testing.md](qgis-plugin/docs/testing.md)

The public documentation site is maintained separately under `mkdocs/`.
