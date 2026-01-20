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

### 7. `test_gazetteer_api.py`

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

### 8. `regenerate_api_keys.py`

**Purpose**: Regenerate API keys created before the PBKDF2 hashing change (January 20, 2026).

**Key Features**:
- Identifies API keys created before the PBKDF2 migration date
- Creates replacement keys with identical tier and settings
- Optionally deactivates old keys after creating replacements
- Dry-run mode to preview changes without making them
- Detailed migration report with old key ID to new API key mapping

**Background**:
On January 20, 2026, API key hashing was upgraded from SHA-256 to PBKDF2-HMAC-SHA256 for improved security. Keys created before this date are no longer valid and need to be regenerated.

**Usage**:
```bash
# Dry run to see what would be regenerated (recommended first step)
python scripts/regenerate_api_keys.py --dry-run

# Actually regenerate keys (old keys remain active)
python scripts/regenerate_api_keys.py

# Regenerate and deactivate old keys
python scripts/regenerate_api_keys.py --deactivate-old

# Use a custom cutoff date
python scripts/regenerate_api_keys.py --cutoff-date 2026-01-15
```

**Options**:
- `--cutoff-date YYYY-MM-DD`: Keys created before this date will be regenerated (default: 2026-01-20)
- `--dry-run`: Show what would be regenerated without making changes
- `--deactivate-old`: Deactivate old keys after creating replacements

**Output**:
The script generates a detailed report showing:
- Total keys found
- Keys needing regeneration
- Successfully regenerated keys
- Failed regenerations (if any)
- Mapping of old key IDs to new API keys

**Important Notes**:
- Always run with `--dry-run` first to preview changes
- The script outputs new API keys in plaintext - secure them immediately
- Old keys remain active unless `--deactivate-old` is used
- Each regenerated key maintains the same tier, name, and IP restrictions as the original

**Requirements**:
- Database connection must be properly configured
- Access to the `api_keys` and `api_service_tiers` tables
- Sufficient permissions to create and update API keys

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

### API rate limiting and service tiers

Rate limiting for the public API is enforced by middleware backed by Redis:

- Tables and seed data are created by the standard migration script:

  ```bash
  .venv/bin/python scripts/run_migrations.py
  ```

  This will ensure:

  - `api_service_tiers` – service tier definitions and per-minute limits
  - `api_keys` – hashed API keys associated with tiers
  - `api_usage_logs` – analytics for incoming requests

- Runtime configuration is controlled via environment variables (see also `README.md`):

  ```bash
  RATE_LIMIT_ENABLED=true
  RATE_LIMIT_REDIS_DB=2
  REDIS_HOST=redis
  REDIS_PORT=6379
  REDIS_PASSWORD=optional_password
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