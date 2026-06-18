# Backend Scripts

Backend utility scripts live in `backend/scripts/`. This public page documents
safe local-development uses and points restricted operational scripts to the
private operations documentation.

Prefer Makefile targets for repeated workflows so environment loading and Docker
wrapping stay consistent. See [../make_tasks.md](../make_tasks.md).

## Safe Local Scripts

### `process_allmaps.py`

Processes and generates Allmaps annotations for resources in the local database.

```bash
python scripts/process_allmaps.py --item-id "example-id"
python scripts/process_allmaps.py --all
```

### `populate_relationships.py`

Populates relationship data between resources.

```bash
python scripts/populate_relationships.py
make populate-relationships
```

See [relationships.md](relationships.md).

### `generate_fast_embeddings.py`

Generates and stores embeddings for FAST gazetteer data. Requires a configured
OpenAI API key in the local environment.

```bash
python scripts/generate_fast_embeddings.py
```

### `run_migration.py`

Runs script-based local migrations.

```bash
python scripts/run_migration.py add_fast_gazetteer
```

### `import_fast.py`

Imports OCLC FAST geographic records into the local database.

```bash
python scripts/import_fast.py
```

### `clear_cache.py`

Clears local Redis cache data for development and testing.

```bash
python scripts/clear_cache.py
```

### `clear_cache_by_type.py`

Clears local cache entries by tag type.

```bash
python scripts/clear_cache_by_type.py search
python scripts/clear_cache_by_type.py all
```

### `test_gazetteer_api.py`

Exercises gazetteer API endpoints against a configured base URL.

```bash
python scripts/test_gazetteer_api.py --base-url http://localhost:8000/api/v1
```

### `manage_analytics_storage.py`

Maintains local analytics partitions, rollups, and retention tables.

```bash
cd backend
python scripts/manage_analytics_storage.py --mode maintenance
python scripts/manage_analytics_storage.py --mode size-report
python scripts/manage_analytics_storage.py --mode ensure
```

From the project root:

```bash
make analytics-maintenance
make analytics-size-report
```

## Restricted Operational Scripts

Some scripts are intended for deployment bootstrap, remote maintenance, backup,
restore, deployed cache handling, or incident response. Public docs must not
include hostnames, destination names, command blocks, secret names, storage
layouts, credential setup, or recovery procedures for those scripts.

Use the restricted operations documentation for:

- deployment bootstrap scripts;
- remote backup and restore scripts;
- deployed search/cache/database maintenance;
- deployed analytics maintenance;
- deployed service-tier and API-key operations;
- incident response and recovery playbooks.

## API Rate Limiting And Service Tiers

Rate limiting for the public API is enforced by middleware backed by Redis.
Tables and seed data are created by the standard migration script:

```bash
.venv/bin/python scripts/run_migrations.py
```

Public docs may describe the implementation model and local testing. Production
key provisioning, deployed tier changes, monitoring, and troubleshooting are
restricted operations material.

For code-level context, see:

- [Analytics Program](analytics_program.md)
- [API Keys And Service Tiers](api_keys_and_service_tiers.md)
- [Service Tiers And Rate Limiting](service_tiers_runbook.md)

## Maintenance Checklist

- Add a Makefile target when a script becomes part of a repeated local
  development workflow.
- Document new public-safe target variables in [../make_tasks.md](../make_tasks.md).
- Add or update backend tests when a script mutates database, cache, index, or
  external service state.
- Keep destructive scripts guarded by clear names, dry-run flags, or Makefile
  comments.
- Do not commit generated outputs from `tmp/`, `logs/`, data volumes, cache
  directories, or Python/Node build artifacts.
