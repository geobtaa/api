# GEOMG Admin

GEOMG is the staff catalog editor for the BTAA Geospatial API. A Resource can belong to one managing Set, which determines its Source and staff editing scope. Confirmed published edits commit the metadata, Activity entry and search refresh request in the same PostgreSQL transaction.

On dev2, confirmation waits briefly for search and detail to serve the saved revision. The editor shows **Live on dev2** once both reads succeed. If indexing takes longer, it shows **Saved · updating dev2** and checks again automatically. Staff can then open the Geoportal search results and record page to see the change.

After a verified full reindex, operators can set `GEOMG_PROJECTION_BASELINE_END` to the timezone-qualified timestamp of the quiescent catalog snapshot. The projector serves staff edits first, followed by later feed changes. Older requests continue through normal verification.

Staff may correct already-published legacy records while required fields are missing. Each edit must preserve every currently populated required field. New publication requires the full publication metadata.

## Local development

From this directory, copy `.env.example` to `.env` and run `docker compose up --build`. The UI listens on port 3000 and the API on port 8000. Run `make backend-migrate` against the local GEOMG development database to initialize the administrative tables. Local PostgreSQL, Python 3.14 with uv, and Node.js 24 are used for development and testing.

Run `make install`, `make check`, and `npm --prefix frontend run build` to install dependencies, check the app and build the UI. Backend integration tests use a disposable PostgreSQL database. Run `make fixtures-check` to verify the Geoportal test corpus.

The sibling app supports a mounted UI at `/admin/` and API at `/admin/api/v1/`. The public API keeps its operational endpoints at `/api/v1/admin`. Alpha accounts use a staff-provided single-use setup code and a local password. Institutional authentication remains the production requirement.

See the [public documentation policy](../docs/security_docs_policy.md) for the boundary around operational runbooks.
