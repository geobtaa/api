# GEOMG Admin Prototype

GEOMG is a local admin prototype for metadata management workflows. It runs as a
standalone FastAPI app and does not start the public API, frontend,
Elasticsearch, Redis, Celery, or Flower.

## Start The App

From the repository root:

```bash
make geomg
```

Open:

```text
http://127.0.0.1:8010/resources
```

Useful alternate port:

```bash
GEOMG_PORT=8011 make geomg
```

The `make geomg` target uses `GEOMG_PYTHON` when set. By default it prefers
`backend/.venv/bin/python` if that exists, otherwise `python3` from `PATH`.

## Views

- `/resources` - compact resource dashboard.
- `/harvest-records` - harvest records dashboard.
- `/health` - simple health check.

## Fixtures

Prototype-specific fixtures live here:

```text
geomg/fixtures/
  harvest-records/
  resources/
```

The harvest records are connected to associated resources by `b1g_code_s`.

The resource dashboard still also loads a small set of existing backend fixture
records from `backend/data/fixtures`.
