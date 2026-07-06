# GEOMG Admin Prototype

This is a local-only prototype for the GEOMG administrative metadata tool. It is
intentionally small and isolated from the production API.

The prototype:

- runs as a standalone FastAPI app;
- loads a small set of existing JSON fixtures from `backend/data/fixtures`;
- loads GEOMG prototype harvest/resource fixtures from `geomg/fixtures`;
- keeps records in memory for the current process;
- renders server-side HTML for an internal metadata workflow;
- does not connect to PostgreSQL, Elasticsearch, Redis, Celery, Flower, or the
  public frontend;
- does not persist edits or push records to the public API.

## Run It

From the repository root:

```bash
make geomg
```

Open:

```text
http://127.0.0.1:8010/resources
```

You can override the bind address or port:

```bash
GEOMG_PORT=8011 make geomg
```

The target uses `GEOMG_PYTHON` when set. By default it prefers
`backend/.venv/bin/python` when that exists, otherwise `python3` from `PATH`.
That Python environment needs the backend's normal FastAPI/Jinja/Uvicorn
dependencies installed.

## What To Review

The resource queue shows fixture records in a compact spreadsheet-like admin
table with title, resource class, resource type, provider, publisher, and
publication state. A general search bar searches visible metadata plus hidden
record IDs, and column header dropdowns filter the table.

The harvest records dashboard shows the records in
`geomg/fixtures/harvest-records` as a separate table. Columns are generated from
fields populated in those harvest fixtures, and `b1g_code_s` is used to count
associated resource fixtures in `geomg/fixtures/resources`.

Each row links to a detail page with grouped edit-style sections:

- Overview
- Discovery metadata
- Links / references
- Admin / provenance
- Preview JSON

The detail page includes a record lock placeholder, a fake publication state
control, fixture provenance, parsed references, and lightweight validation
messages. Form fields are editable in the browser only; there is no save handler
yet.

## Code Layout

```text
geomg/
  data.py
  main.py
  fixtures/
    harvest-records/
    resources/
  static/geomg/admin.css
  templates/geomg/
```

The app entry point is `geomg.main:app`. It is not imported by `app.main`, so
normal production API behavior is unchanged.
