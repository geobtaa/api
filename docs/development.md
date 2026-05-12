# Local Setup and Development

This page collects the practical notes for running and working on the BTAA
Geospatial API repository. For a broader architectural tour, see
[backend/codebase_overview.md](backend/codebase_overview.md).

## Quick Start With Docker

Docker Compose is the recommended local path because it runs the API, frontend
development server, database, search index, Redis, Celery worker, and Flower
with one command.

1. Install Docker Desktop and make sure it is running.
2. Create a local environment file:

   ```bash
   cp .env.example .env
   ```

3. Start the stack from the repository root:

   ```bash
   docker compose up -d
   ```

4. Open the local services:

   - Website: `http://localhost:3000`
   - API docs: `http://localhost:8000/api/docs`
   - Flower: `http://localhost:5555`

Stop the stack with:

```bash
docker compose down
```

## Docker Services

The local stack is defined in `docker-compose.yml`.

| Service | Container name | Purpose |
| --- | --- | --- |
| `api` | `btaa-geospatial-api-app` | FastAPI app on port 8000 |
| `frontend` | `btaa-geospatial-api-frontend` | Vite/React dev server on port 3000 |
| `elasticsearch` | `btaa-geospatial-api-elasticsearch` | Elasticsearch on port 9200 |
| `paradedb` | `btaa-geospatial-api-paradedb` | PostgreSQL/ParadeDB |
| `redis` | `btaa-geospatial-api-redis` | Redis cache and Celery broker |
| `celery_worker` | `btaa-geospatial-api-celery` | Background job worker |
| `flower` | `btaa-geospatial-api-flower` | Celery monitoring UI on port 5555 |

Common commands:

```bash
docker compose up -d
docker compose down
docker compose logs -f api
docker compose restart api celery_worker
docker compose up -d --build api
```

After changing frontend dependencies or Vite config, run:

```bash
make frontend-reset
```

Then hard-refresh the browser or use a fresh private/incognito window.

## Local Development Without Full Docker

Most developers still run infrastructure services in Docker, even when editing
backend or frontend code on the host.

### Prerequisites

- Node.js 20 or later
- Python 3.11 or later
- uv, from <https://github.com/astral-sh/uv>
- Docker Desktop for Postgres/ParadeDB, Elasticsearch, Redis, and Celery

### Backend

From the repository root:

```bash
cp .env.example .env
docker compose up -d paradedb elasticsearch redis celery_worker flower
cd backend
python3 -m venv venv
source venv/bin/activate
uv pip install -e '.[dev]'
```

Run backend commands from the repository root through the Makefile whenever
possible:

```bash
make lint
make format
make lint-check
make test-no-coverage
make test
```

Backend tests expect the Docker database services to be available. See
[backend/testing.md](backend/testing.md) and [make_tasks.md](make_tasks.md) for
the full testing and task reference.

### Frontend

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Common frontend checks:

```bash
npm run lint
npm run lint:fix
npm run format
npm run format:check
npm test
```

More detail lives in [frontend/README.md](frontend/README.md),
[frontend/testing.md](frontend/testing.md), and
[frontend/linting-and-formatting.md](frontend/linting-and-formatting.md).

## Data, Ingest, and Indexing

Prefer Makefile targets for routine data and indexing work so local behavior
matches the documented operational workflow.

```bash
make ingest
make ingest-featured
make bridge-sync
make populate-distributions
make reindex
make verify-h3-index
make clear_cache
```

OpenGeoMetadata harvests and local reindexing are described in
[backend/ogm_harvesting.md](backend/ogm_harvesting.md). The full Makefile
reference is in [make_tasks.md](make_tasks.md).

## MCP, CLI, Slack, and QGIS

- MCP bridge helpers are documented in [mcp/README.md](mcp/README.md).
- The command-line client is documented in [../cli/README.md](../cli/README.md).
- Slackbot setup is documented in [slack/README.md](slack/README.md).
- QGIS plugin test and development notes live in
  [../qgis-plugin/docs/testing.md](../qgis-plugin/docs/testing.md).

## Troubleshooting

- If the website does not load immediately after `docker compose up -d`, wait a
  minute or two while the database, search index, and Redis finish startup.
- If Redis reports unhealthy right after startup, it may still be replaying its
  local append-only cache. Wait briefly, then run `docker compose up -d` again.
- If port 3000 is busy, check for another local Vite process or an existing
  `frontend` container.
- To restart from clean containers while keeping repository files:

  ```bash
  docker compose down
  docker compose up -d
  ```
