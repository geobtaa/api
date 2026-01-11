# BTAA Geospatial API

This project powers a Big Ten Academic Alliance geospatial catalog. If you’re a librarian or non-technical user, the goal here is simple:

- Start the project on your computer
- Open the website in your browser
- Search and view records

You do **not** need to know Python, databases, or Docker internals to use it.

## What you get

- **The website (frontend)**: where you browse and search (runs at `http://localhost:3000`)
- **The API (backend)**: the “data service” the website talks to (runs at `http://localhost:8000`)

## Before you start

1) Install **Docker Desktop** for your operating system and make sure it’s running.
2) Make a local settings file:

```bash
cp .env.example .env
```

If you already have a `.env`, you can keep using it.

## Start the project (recommended)

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

## Frontend development mode (`frontend-dev`)

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

## Troubleshooting (quick)

- **The website won’t load**: wait ~30–60 seconds after `docker compose up -d` (databases need time to start)
- **Port 3000 is busy**: stop whichever frontend container is running: `docker compose stop frontend frontend-dev`
- **Start fresh** (wipes local containers; keeps your project files):

```bash
docker compose down
docker compose up -d
```

## Documentation (for staff who want details)

All documentation is now in the top-level `docs/` folder:

- **Caching**: `docs/backend/caching.md`
- **Search**: `docs/backend/search.md`
- **Service tiers / API keys / rate limiting**: `docs/backend/service_tiers_runbook.md`
- **Scripts (Python utilities)**: `docs/backend/scripts.md`
- **Frontend docs**: `docs/frontend/`
- **Developer Make tasks**: `docs/make_tasks.md`
