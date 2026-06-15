# Scripts Documentation

This document provides an overview of the utility scripts available in the project.

## Overview

The `scripts/` directory contains various utility scripts for managing the application's data, testing functionality, and performing maintenance tasks.

## Available Scripts

### 1. `process_allmaps.py`

**Purpose**: Processes and generates Allmaps annotations for resources in the database.

**Key Features**:
- Processes individual resources or all resources in the database
- Generates Allmaps IDs and annotations
- Updates item records with Allmaps attributes
- Supports reprocessing of existing resources
- Implements logging and error handling

**Usage**:
```bash
# Process a specific item
python process_allmaps.py --item-id "9139578d-7803-4f4f-9ed3-a62ab810a256"

# Process all items
python process_allmaps.py --all
```

**Requirements**:
- Database connection must be properly configured
- Item must have a valid manifest URL
- Item must not already have Allmaps attributes (unless reprocessing)

**Output**:
- Updates the `item_allmaps` table with generated Allmaps data
- Logs processing status and any errors encountered

### 2. `populate_relationships.py`

**Purpose**: Manages and populates relationship data between documents in the database.

**Key Features**:
- Processes various types of document relationships (isPartOf, hasMember, isVersionOf, etc.)
- Maintains bidirectional relationships
- Clears existing relationships before populating new ones
- Implements logging to both console and file

**Usage**:
```bash
python scripts/populate_relationships.py
```

From the project root you can run:
```bash
make populate-relationships
```
(See [relationships.md](relationships.md) for how relationships interact with search and how to query the DB.)

### 3. `generate_fast_embeddings.py`

**Purpose**: Generates and stores embeddings for FAST gazetteer data using OpenAI's API.

**Key Features**:
- Uses OpenAI's text-embedding-3-small model
- Processes records in batches
- Stores embeddings in the database
- Implements error handling and logging

**Requirements**:
- OpenAI API key must be set in environment variables

**Usage**:
```bash
python scripts/generate_fast_embeddings.py
```

### 4. `run_migration.py`

**Purpose**: Executes database migrations.

**Key Features**:
- Supports multiple migration types
- Implements command-line argument parsing
- Provides logging of migration progress

**Available Migrations**:
- `add_fast_gazetteer`: Adds FAST gazetteer data to the database

**Usage**:
```bash
python scripts/run_migration.py add_fast_gazetteer
```

### 5. `import_fast.py`

**Purpose**: Imports OCLC FAST Dataset Geographic entries into the database.

**Key Features**:
- Asynchronous data import
- Progress tracking and reporting
- Error handling and logging
- Performance metrics (records processed, elapsed time)

**Usage**:
```bash
python scripts/import_fast.py
```

### 6. `clear_cache.py`

**Purpose**: Clears the Redis cache used by the application.

**Key Features**:
- Clears all Redis databases
- Reports memory usage after clearing
- Configurable Redis connection parameters
- Error handling and logging

**Usage**:
```bash
python scripts/clear_cache.py
```

### 7. `clear_cache_by_type.py`

**Purpose**: Clears cache by type using tag-based invalidation. Used by `make kamal-clear-cache` when the exec container cannot reach the public API URL (avoids curl/HTTP).

**Key Features**:
- Tag-based invalidation (search, resource, suggest, map, all)
- Connects directly to Redis; no HTTP required
- Same behavior as the admin cache-clear endpoint

**Usage**:
```bash
python scripts/clear_cache_by_type.py [search|resource|suggest|map|all]
python scripts/clear_cache_by_type.py search   # default
python scripts/clear_cache_by_type.py all
```

### 8. `test_gazetteer_api.py`

**Purpose**: Tests the functionality of gazetteer API endpoints.

**Key Features**:
- Tests multiple gazetteer sources (GeoNames, Who's on First, BTAA)
- Provides detailed output of test results
- Configurable base URL for testing different environments
- Pretty-prints JSON responses

**Usage**:
```bash
python scripts/test_gazetteer_api.py [--base-url URL]
```

### 9. `bootstrap_kamal_deploy_user.sh`

**Purpose**: Bootstraps the shared `deploy` SSH account used for Kamal deployments on remote hosts.

**Key Features**:
- Creates the `deploy` group and user if needed
- Adds `deploy` to the `docker` group
- Seeds `/home/deploy/.ssh/authorized_keys` from the current remote operator
- Prepares `/var/lib/btaa-geospatial-api` for shared bind mounts
- Pre-creates the Elasticsearch bind-mount directory with GID 0 write access for fresh hosts

**Usage**:
```bash
backend/scripts/bootstrap_kamal_deploy_user.sh \
  --host lib-geoportal-dev-web-01.oit.umn.edu \
  --ssh-user your_existing_admin_user
```

**Requirements**:
- Run from the repo root on your local machine
- The existing remote SSH user must already have passwordless `sudo`
- Docker should already be installed on the target host

See also `docs/backend/kamal_deployment.md` for the full Kamal runbook.

### 10. `manage_analytics_storage.py`

**Purpose**: Maintains analytics partitions, rollups, and retention.

See also [Analytics Program](analytics_program.md) for the full analytics architecture and operating model.

**Key Features**:
- Ensures monthly partitions exist for raw `analytics_*` tables
- Rolls up completed daily analytics into compact summary tables
- Drops expired raw partitions only after rollups have caught up
- Prints relation sizes for analytics parents, partitions, and rollups

**Usage**:
```bash
cd backend
python scripts/manage_analytics_storage.py --mode maintenance
python scripts/manage_analytics_storage.py --mode size-report
python scripts/manage_analytics_storage.py --mode ensure
```

From the project root you can run:
```bash
make analytics-maintenance
make analytics-size-report
```

### 11. `backup_postgres_to_s3.py`

**Purpose**: Creates a production-gated PostgreSQL/ParadeDB `pg_dump` custom
archive and uploads it to S3 with a JSON manifest.

**Usage**:
```bash
python scripts/backup_postgres_to_s3.py
```

From the project root you can run against Kamal production:
```bash
make kamal-backup-postgres KAMAL_DEST=prd
```

### 12. `backup_elasticsearch.py`

**Purpose**: Manages Elasticsearch snapshots for disaster recovery. It supports
the historical filesystem repository and the production S3 repository.

**Usage**:
```bash
python scripts/backup_elasticsearch.py --create --wait --retain-count 3
python scripts/backup_elasticsearch.py --list
python scripts/backup_elasticsearch.py --restore <snapshot-name> --wait
```

From the project root you can run against Kamal production:
```bash
make kamal-backup-elasticsearch KAMAL_DEST=prd
make kamal-backup-list-elasticsearch KAMAL_DEST=prd
```

See [disaster_recovery.md](disaster_recovery.md) for S3 configuration,
retention, and restore procedures.

## Common Features

All scripts share some common features:
- Logging configuration
- Error handling
- Environment variable support
- Python path configuration for module imports

## Environment Variables

Several scripts require specific environment variables:

- `OPENAI_API_KEY`: Required by `generate_fast_embeddings.py`
- `REDIS_HOST` and `REDIS_PORT`: Used by `clear_cache.py`
- `BACKUP_ENABLED`, `BACKUP_S3_BUCKET`, `BACKUP_S3_PREFIX`,
  `BACKUP_RETENTION_COUNT`, and AWS credentials: used by the disaster recovery
  backup scripts.

### API rate limiting and service tiers

Rate limiting for the public API is enforced by middleware backed by Redis:

- Documentation shell routes (`/api/docs`, `/api/redoc`, `/api/openapi.json`,
  and docs branding assets) bypass throttling so users can always load the API
  reference. Interactive requests made from those docs still hit the normal API
  endpoints and remain rate limited.

- Tables and seed data are created by the standard migration script:

  ```bash
  .venv/bin/python scripts/run_migrations.py
  ```

  This will ensure:

  - `api_service_tiers` – service tier definitions and per-minute limits
  - `api_keys` – hashed API keys associated with tiers
  - `analytics_api_usage_logs` – analytics for incoming requests
  - `analytics_searches` – normalized Geoportal search analytics
  - `analytics_search_impressions` – result impressions with rank/page/view
  - `analytics_events` – resource views, result clicks, downloads, and outbound link events
  - `analytics_daily_api_usage_metrics`, `analytics_daily_search_metrics`, `analytics_daily_resource_metrics` – compact daily rollups
  - `analytics_maintenance_state` – rollup checkpoint state

- Runtime configuration is controlled via environment variables (see also
  [../development.md](../development.md)):

  ```bash
  RATE_LIMIT_ENABLED=true
  RATE_LIMIT_REDIS_DB=2
  REDIS_HOST=redis
  REDIS_PORT=6379
  REDIS_PASSWORD=optional_password
  ANALYTICS_RETENTION_API_USAGE_DAYS=30
  ANALYTICS_RETENTION_SEARCH_DAYS=90
  ANALYTICS_RETENTION_IMPRESSION_DAYS=30
  ANALYTICS_RETENTION_EVENT_DAYS=90
  ```

To create and manage API keys from the command line, you can call the admin endpoints with basic auth, for example:

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
  -X POST "http://localhost:8000/api/v1/admin/api-keys" \
  -H "Content-Type: application/json" \
  -d '{"tier_name": "anonymous", "name": "local test key"}'
```

The response will include the plaintext `api_key` (shown once) and the numeric `key_id`. You can then use the key in API requests via:

- `X-API-Key` header
- `Authorization: Bearer <api_key>` header
- `api_key=<api_key>` query parameter
- `LOG_PATH`: Optional path for log files

## Logging

All scripts implement logging with the following characteristics:
- Log level: INFO by default
- Format: Timestamp, logger name, level, and message
- Output: Console and/or file depending on the script 
