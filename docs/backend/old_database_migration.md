# Old Database Migration Guide

## Overview

This guide explains how to migrate data from the old production database (`geoportal_production_20251030`) to the new resources table in the current application. The migration uses a materialized view bridge approach to transform and map data between the two schemas.

## Architecture

The migration process consists of two phases:

1. **Bridge Creation**: Creates a materialized view in the old database that transforms `kithe_models` records into the new schema format
2. **Data Import**: Imports the transformed data from the materialized view into the new database

## Prerequisites

1. **Old production database accessible**: The `geoportal_production_20251030` database must be accessible on the same ParadeDB container
2. **Environment configuration**: Ensure database connection parameters are set in your `.env` file:

```bash
# Database connection (existing)
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=2345
DB_NAME=btaa_geospatial_api

# Old database name (add this)
OLD_DB_NAME=geoportal_production_20251030
```

3. **Database backups**: Always backup both databases before starting the migration
   - New database: `make db-export`
   - Old database: Connect and export if needed

## Schema Mapping

The old database uses a `kithe_models` table with:
- `id`: Record ID
- `title`: Record title
- `type`: Record type (we filter for `'Document'`)
- `json_attributes`: JSONB column containing all metadata fields

The new database uses a `resources` table with all OGM Aardvark and BTAA-specific fields as separate columns.

### Field Mapping

Most fields map directly from `json_attributes` to the new column names. The field names are designed to match OGM Aardvark standards:

| Old Schema (JSON key) | New Schema (Column) | Notes |
|----------------------|---------------------|-------|
| `id` | `id` | Direct mapping |
| `title` | `dct_title_s` | Direct mapping |
| `publication_state` | `publication_state` | Carried over from `kithe_models` column |
| `import_id` | `import_id` | Carried over from `kithe_models` column |
| All other fields | Same name | Mapped from json_attributes JSON |

### Array Fields

Fields ending with `_sm` or `_im` are treated as arrays and cast appropriately:
- `_sm`: String arrays (`text[]`)
- `_im`: Integer arrays (`integer[]`)

## Migration Process

### Step 1: Verify Field Mapping

First, check how fields map between the old and new schemas:

```bash
python db/migrations/bridge_old_production.py --verify
```

This will:
- Sample records from the old database
- Compare JSON keys with the new schema fields
- Report matching fields, unmapped fields, and new fields

**Expected output**:
```
Found X unique JSON keys in sampled records
Keys matching new schema: Y
Unmapped keys: Z
```

Review any unmapped fields to determine if they should be included in the migration.

### Step 2: Create Materialized View

Create the materialized view bridge in the old database:

```bash
python db/migrations/bridge_old_production.py --create-view
```

This will:
- Create the `kithe_to_resources_bridge` materialized view
- Extract fields from `json_attributes` JSON
- Apply proper type casting (arrays, dates, booleans, JSON, etc.)
- Filter for `type = 'Document'` records with `publication_state = 'published'`
- Create an index on the `id` field
- Populate the view with data

**Expected output**:
```
✓ Materialized view created successfully
✓ Index created
✓ Materialized view refreshed
✓ Materialized view contains X records
```

### Step 3: View Summary (Optional)

Get a summary of the materialized view:

```bash
python db/migrations/bridge_old_production.py --summary
```

This displays:
- Total record count
- Sample IDs and titles
- Verification of view contents

### Step 4: Dry Run Import

Test the import process without writing data:

```bash
python db/migrations/import_from_old_production.py --dry-run --batch-size 1000
```

This will:
- Connect to both databases
- Process records in batches
- Simulate the import without writing
- Report how many records would be imported

Review the output to ensure everything looks correct before running the actual import.

### Step 5: Execute Import

Run the actual import:

```bash
python db/migrations/import_from_old_production.py --batch-size 1000 --conflict update
```

**Conflict handling options**:
- `update`: Update existing records with incoming data (recommended so the old production values using `friendlier_id` take precedence)
- `skip`: Skip records with duplicate IDs (useful for incremental loads when no overwrite is desired)
- `fail`: Stop on first conflict

**Expected output**:
```
Processing X records in batches of 1000...
Progress: 1000/X (Y%)
...
✓ Import complete
Total records: X
Imported: Y
Skipped: Z
```

### Step 6: Verify Import

Verify the imported data and spot-check a sample:

```bash
python db/migrations/import_from_old_production.py --verify
```

This will:
- Compare record counts between old and new databases
- Sample records and verify they match
- Report any discrepancies
- Log how many rows were updated versus newly inserted based on the conflict strategy

## Maintenance Operations

### Refresh Materialized View

If you need to update the materialized view (e.g., after data changes in old DB):

```bash
python db/migrations/bridge_old_production.py --refresh
```

### Export Bridge Data

Export the transformed data for backup or analysis:

```bash
python db/migrations/bridge_old_production.py --export /path/to/output.json
```

The export is in JSON Lines format, one record per line.

### Sample Records

Sample and inspect the old database structure:

```bash
python db/migrations/bridge_old_production.py --sample 10
```

This helps understand the `json_attributes` structure.

## Troubleshooting

### Materialized View Doesn't Exist

**Error**: "Materialized view does not exist"

**Solution**: Run the bridge creation step:
```bash
python db/migrations/bridge_old_production.py --create-view
```

### Connection Errors

**Error**: "Could not connect to database"

**Solution**: 
1. Verify Docker containers are running: `docker compose ps`
2. Check environment variables in `.env` file
3. Ensure `DB_HOST` is set to `localhost` (not `paradedb`)

### Field Mapping Issues

**Error**: Unexpected field names or types

**Solution**:
1. Run `--verify` to see field mapping details
2. Inspect sample data: `--sample`
3. Check the `kithe_models.json_attributes` structure in the old database
4. Update the bridge script if field names differ

### Import Conflicts

**Error**: "Integrity error" or "duplicate key"

**Solution**:
1. Use `--conflict skip` to skip duplicates
2. Or use `--conflict update` to update existing records
3. Check for ID duplicates in source data

### Performance Issues

**Symptom**: Import is very slow

**Solution**:
1. Increase batch size: `--batch-size 5000`
2. Check database indexes are properly created
3. Monitor resource usage: `docker stats`
4. Consider running during low-traffic period

## Rollback

If you need to rollback the migration:

1. **Restore from backup**:
   ```bash
   make db-import
   ```
   `make db-import` now preserves destination-local `api_service_tiers`, `api_keys`, `analytics_api_usage_logs`, `analytics_searches`, `analytics_search_impressions`, and `analytics_events` by default, along with their owned `*_id_seq` sequences. If you need a full overwrite during rollback, rerun `make db-export DB_SYNC_PRESERVE_LOCAL_TABLES=false` and `make db-import DB_SYNC_PRESERVE_LOCAL_TABLES=false`.

2. **Or manually clean**:
   ```sql
   -- Connect to new database
   TRUNCATE TABLE resources CASCADE;
   ```

3. **Restore from backup file**:
   ```bash
   gunzip -c tmp/btaa_geospatial_api_export.sql.gz | docker exec -i btaa-geospatial-api-paradedb psql -U postgres -d btaa_geospatial_api
   ```

## Post-Migration Tasks

After successful migration:

1. **Update Elasticsearch index**:
   ```bash
   python run_index.py
   ```

2. **Refresh cached data**:
   - Clear Redis cache if needed
   - Restart application services

3. **Verify API endpoints**:
   - Test search functionality
   - Check individual resource views
   - Verify facets and filters

4. **Monitor**:
   - Check application logs
   - Monitor database performance
   - Verify API response times

## Field Mapping Reference

Complete list of fields in the resources table:

### Core Fields
- `id`, `dct_title_s`

### Descriptive Fields
- `dct_alternative_sm`, `dct_description_sm`, `dct_language_sm`, `gbl_displayNote_sm`

### Creator and Publisher
- `dct_creator_sm`, `dct_publisher_sm`, `schema_provider_s`

### Classification
- `gbl_resourceClass_sm`, `gbl_resourceType_sm`

### Subject and Themes
- `dct_subject_sm`, `dcat_theme_sm`, `dcat_keyword_sm`

### Temporal
- `dct_temporal_sm`, `dct_issued_s`, `gbl_indexYear_im`, `gbl_dateRange_drsim`

### Spatial
- `dct_spatial_sm`, `locn_geometry`, `dcat_bbox`, `dcat_centroid`

### Relationships
- `dct_relation_sm`, `pcdm_memberOf_sm`, `dct_isPartOf_sm`, `dct_source_sm`
- `dct_isVersionOf_sm`, `dct_replaces_sm`, `dct_isReplacedBy_sm`

### Rights
- `dct_rights_sm`, `dct_rightsHolder_sm`, `dct_license_sm`, `dct_accessRights_s`

### Technical
- `dct_format_s`, `gbl_fileSize_s`, `gbl_wxsIdentifier_s`, `dct_references_s`

### Identifiers and Metadata
- `dct_identifier_sm`, `gbl_mdModified_dt`, `gbl_mdVersion_s`
- `gbl_suppressed_b`, `gbl_georeferenced_b`

### BTAA-Specific Fields
- `b1g_code_s`, `b1g_status_s`, `b1g_dct_accrualMethod_s`, `b1g_dct_accrualPeriodicity_s`
- `b1g_dateAccessioned_s`, `b1g_dateAccessioned_sm`, `b1g_dateRetired_s`, `b1g_child_record_b`
- `b1g_dct_mediator_sm`, `b1g_access_s`, `b1g_image_ss`, `b1g_geonames_sm`
- `b1g_publication_state_s`, `b1g_language_sm`, `b1g_creatorID_sm`
- `b1g_dct_conformsTo_sm`, `b1g_dcat_spatialResolutionInMeters_sm`
- `b1g_geodcat_spatialResolutionAsText_sm`, `b1g_dct_provenanceStatement_sm`
- `b1g_adminTags_sm`
- `b1g_adms_supportedSchema_sm`, `b1g_dcat_endpointDescription_s`, `b1g_dcat_endpointURL_s`
- `b1g_dcat_inSeries_sm`, `b1g_localCollectionLabel_sm`
- `b1g_prov_softwareAgent_sm`, `b1g_prov_wasGeneratedBy_sm`
- `date_created_dtsi`, `date_modified_dtsi`, `geomg_id_s`

## Additional Resources

- [OGM Aardvark Schema](https://opengeometadata.github.io/aardvark/aardvarkMetadata.html)
- [ParadeDB Documentation](https://docs.paradedb.com/)
- [PostgreSQL Materialized Views](https://www.postgresql.org/docs/current/sql-creatematerializedview.html)
