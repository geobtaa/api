# BTAA Geospatial API

This project powers a Big Ten Academic Alliance geospatial catalog. If you're a librarian or non-technical user, the goal here is simple:

- Start the project on your computer
- Open the website in your browser
- Search and view records

You do **not** need to know Python, databases, or Docker internals to use it.

## What you get

- **The website (frontend)**: where you browse and search (runs at `http://localhost:3000`)
- **The API (backend)**: the "data service" the website talks to (runs at `http://localhost:8000`)
- **The QGIS plugin**: a desktop tool to search the catalog and load spatial datasets directly within QGIS

## Quick start (Docker - recommended)

This is the easiest way to run the project. All dependencies are handled automatically.

### Prerequisites

1. Install **Docker Desktop** for your operating system and make sure it's running.
2. Make a local settings file:

```bash
cp .env.example .env
```

If you already have a `.env`, you can keep using it.

### Start the project

This starts the full stack (API + website + database services):

```bash
docker compose up -d
```

Then open:

- **Website**: `http://localhost:3000`
- **API docs (for technical staff)**: `http://localhost:8000/api/docs`

To stop everything later:

```bash
docker compose down
```

### Frontend development mode (`frontend-dev`)

If you are actively changing the website code, use `frontend-dev`. It updates instantly as files change.

Important: `frontend-dev` uses **the same port (3000)** as the normal website container, so you can run **one or the other**.

```bash
# Start backend services
docker compose up -d api paradedb elasticsearch redis celery_worker flower

# Stop the normal website container (port 3000)
docker compose stop frontend

# Start the dev website (profile "dev")
docker compose --profile dev up -d frontend-dev
```

## Local development setup (for developers)

If you're developing the code locally (not using Docker), you'll need to install prerequisites and set up dependencies manually.

### Prerequisites

- **Node.js 20** or later
- **Python 3.11** or later
- **UV** (Python package manager) - install from https://github.com/astral-sh/uv

### Setup

1. Make a local settings file:

```bash
cp .env.example .env
```

2. Install backend dependencies:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
uv pip install -e '.[dev]'
```

This installs the package in editable mode with development dependencies.

3. Install frontend dependencies:

```bash
cd ../frontend
npm install
```

4. Set up services:

You'll need to set up the database, Elasticsearch, Redis, and other services. You can use Docker Compose for just the services:

```bash
docker compose up -d paradedb elasticsearch redis celery_worker flower
```

Or consult the documentation in `docs/` for manual setup details.

## Troubleshooting (quick)

- **The website won't load**: wait ~60–120 seconds after `docker compose up -d` (databases need time to start, and Redis may need extra time to replay its local append-only cache)
- **Docker Desktop says `redis` is unhealthy right after start**: that usually means Redis is still replaying persisted local cache data. Wait a minute, then run `docker compose up -d` again.
- **Port 3000 is busy**: stop whichever frontend container is running: `docker compose stop frontend frontend-dev`
- **Start fresh** (wipes local containers; keeps your project files):

```bash
docker compose down
docker compose up -d
```

## QGIS Plugin

In addition to the website and API, this repository contains a **QGIS Plugin** that connects to the Geoportal API. It allows users to search the catalog and load spatial data directly into their map canvas.

- **Source code**: Located in the `qgis-plugin/` directory.
- **Testing & Development**: See `qgis-plugin/docs/testing.md` for instructions on running tests and linting.

## Claude Desktop / MCP

This repository now includes the same MCP bridge layer that existed in the older `ogm-api` project:

- `mcp/run_mcp_service.py` runs the stdio MCP server from the repo root
- `mcp/mcp_http_bridge.js` forwards stdio MCP traffic to `POST /api/v1/mcp`
- `mcp/mcp_websocket_bridge.js` forwards stdio MCP traffic to `/api/v1/mcp/ws`
- `mcp/run_mcp_websocket_bridge.py` launches the WebSocket bridge with Node 18+ automatically
- `mcp/claude_mcp_config.json` is a Claude Desktop template (`cwd` = your clone root; see `docs/mcp/`)

More detail is in `docs/mcp/README.md` and `docs/mcp/claude_desktop.md`.

## Documentation (for staff who want details)

All documentation is now in the top-level `docs/` folder:

- **Codebase overview / executive architecture summary**: `docs/backend/codebase_overview.md`
- **Caching**: `docs/backend/caching.md`
- **Search**: `docs/backend/search.md`
- **Service tiers / API keys / rate limiting**: `docs/backend/service_tiers_runbook.md`
- **Scripts (Python utilities)**: `docs/backend/scripts.md`
- **MCP / Claude Desktop**: `docs/mcp/`
- **Frontend docs**: `docs/frontend/`
- **QGIS plugin docs**: `qgis-plugin/docs/`
- **Developer Make tasks**: `docs/make_tasks.md`
- **Old prod migration runbook (GBL Admin -> API -> reindex)**: `docs/make_tasks.md` (section: "GBL Admin migration runbook (old prod -> reindex)")
