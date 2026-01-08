## `dct_references_s` Usage Inventory

The legacy `dct_references_s` JSON blob is still referenced across the codebase. The sections below summarize each usage to inform the refactor towards `resource_distributions`.

### Application Services & API
- `app/services/search_service.py` – parses `dct_references_s` when enriching Elasticsearch documents for resource detail responses.
- `app/services/download_service.py` – derives download options, including IIIF and direct file links.
- `app/services/viewer_service.py` – builds viewer attributes and geometry information from the reference map.
- `app/services/image_service.py` – resolves thumbnail URLs based on schema.org and IIIF references.
- `app/services/link_service.py` – generates categorized external links (visit source, web services, metadata, ArcGIS, documentation).
- `app/services/citation_service.py` – extracts the primary URL for citation strings.
- `app/services/admin_service.py` – exposes `dct_references_s` within admin payload builders (e.g., `AdminService.get_resource_details`).
- `app/services/ogm_field_mapper.py` – maps database rows to OGM fields, passing through `dct_references_s`.
- `app/api/v1/endpoint_modules/resources.py` – returns the raw field via `process_resource` and other helper responses.
- `app/api/v1/utils.py` / `process_resource` – sanitizes and forwards `dct_references_s` in JSON:API payloads.
- `app/tasks/allmaps.py` – reads reference URLs during Allmaps processing.

### Elasticsearch Layer
- `app/elasticsearch/index.py` – includes `dct_references_s` when indexing documents.
- `app/elasticsearch/mappings.py` – defines mapping (`type: object`, `enabled: false`) for the field.
- `app/elasticsearch/search.py` and related utilities – treat the field as part of the indexed source passed to services.

### Database & Migration Scripts
- `db/models.py` – retains the column definition in the ORM metadata.
- `db/migrations/bridge_old_production.py` – extracts the JSON column while building the materialized view bridge.
- `db/migrations/create_*` / `populate_*` scripts – reference the field in transformation logic.
- `scripts/populate_distributions.py`, `scripts/ogm_importer.py`, `scripts/load_test_data.py` – parse the JSON blob when seeding data.
- `data/parade_db_gbl_table.py`, `data/btaa_ogm_api.txt`, `data/aardvark_json_schema.json` – treat the column as part of exported schema definitions.

### Tests
- `tests/services/*` suites (download, viewer, citation, image, link, admin, search) – construct fixtures using `dct_references_s` payloads for behavior verification.
- `tests/api/v1/*` and `tests/elasticsearch/test_mappings.py` – assert presence/types of the field in API and ES responses.
- `tests/test_mappings.py`, `tests/load_test_fixtures.py`, `tests/fixtures/gbl_fixtures_data.csv` – include references to the JSON blob.

### Documentation
- `docs/backend/old_database_migration.md`, `docs/backend/distribution_tables.md` – mention the field as the historical storage mechanism.

### Frontend Build Artifact
- `frontend/dist/assets/index-*.js` – legacy bundle still looks for `dct_references_s` keys (to be updated alongside backend changes).

This inventory will guide the refactor: each consumer listed above must rely on helpers that read `resource_distributions` (and, where relevant, `distribution_types`) instead of parsing `dct_references_s`.

