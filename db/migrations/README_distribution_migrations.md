# Distribution Migrations

This directory contains migrations for creating and populating the new distribution tables that replace the `dct_references_s` JSON field with a proper relational structure.

> **📖 For comprehensive documentation, see [Distribution Tables Documentation](../../docs/distribution_tables.md)**

## Overview

The migrations create two new tables:
- `distribution_types`: Lookup table for distribution type definitions
- `resource_distributions`: Table for storing resource distribution data

## Migration Files

### 1. `create_distribution_tables.py`
Creates both tables with proper indexes and constraints:
- Creates `distribution_types` table with 28 reference types from `reference_types.csv`
- Creates `resource_distributions` table with foreign key to `distribution_types`
- Sets up indexes for optimal query performance
- Adds triggers for automatic `updated_at` timestamp updates

### 2. `populate_resource_distributions.py`
Populates the new tables from existing data:
- Extracts distribution data from `dct_references_s` JSON field in `resources` table
- Maps distribution URIs to distribution type IDs
- Creates records in `resource_distributions` table
- Handles JSON parsing errors gracefully

### 3. `run_distribution_migrations.py`
Master script that runs all migrations in the correct order:
- Runs table creation migration
- Runs data population migration
- Provides comprehensive logging and error handling

### 4. `test_distribution_migrations.py`
Test script to verify migrations worked correctly:
- Checks table existence and data integrity
- Validates foreign key relationships
- Reports distribution statistics
- Identifies any orphaned records

## Usage

### Run All Migrations
```bash
python db/migrations/run_distribution_migrations.py
```

### Run Individual Migrations
```bash
# Create tables only
python db/migrations/create_distribution_tables.py

# Populate data only (requires tables to exist)
python db/migrations/populate_resource_distributions.py
```

### Test Migrations
```bash
python db/migrations/test_distribution_migrations.py
```

## Table Structures

### distribution_types
```sql
CREATE TABLE distribution_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    distribution_type VARCHAR(255) NOT NULL,
    distribution_uri VARCHAR(500) NOT NULL,
    label BOOLEAN DEFAULT FALSE,
    note TEXT,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### resource_distributions
```sql
CREATE TABLE resource_distributions (
    id SERIAL PRIMARY KEY,
    friendlier_id VARCHAR(255) NOT NULL,
    distribution_type_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    label VARCHAR(255),
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    import_distribution_id VARCHAR(255),
    FOREIGN KEY (distribution_type_id) REFERENCES distribution_types(id) ON DELETE RESTRICT
);
```

## Data Mapping

The migration maps JSON from `dct_references_s` like this:
```json
{
  "http://iiif.io/api/image": "https://digital.lib.uiowa.edu/iiif/2/ui:glo_67~JP2~~default/info.json",
  "http://schema.org/url": "https://digital.lib.uiowa.edu/islandora/object/ui:glo_67"
}
```

To relational records in `resource_distributions` with proper foreign keys to `distribution_types`.

## Benefits

1. **Normalized Structure**: Replaces JSON with proper relational tables
2. **Better Performance**: Indexed lookups instead of JSON parsing
3. **Data Integrity**: Foreign key constraints ensure data consistency
4. **Queryability**: Standard SQL queries instead of JSON operations
5. **Extensibility**: Easy to add new distribution types and metadata

## Next Steps

After running the migrations:

1. **Update Application Code**: Modify your application to use the new tables instead of `dct_references_s`
2. **API Endpoints**: Update API endpoints to return distribution data from the new tables
3. **Data Validation**: Ensure all existing data was migrated correctly
4. **Performance Testing**: Verify query performance improvements
5. **Deprecation**: Consider deprecating the `dct_references_s` field after migration is complete

## Troubleshooting

### Common Issues

1. **JSON Parse Errors**: Some `dct_references_s` values may not be valid JSON
   - The migration logs warnings for these cases
   - Check logs for specific resource IDs with issues

2. **Unknown Distribution URIs**: Some URIs in the JSON may not match distribution types
   - These are logged as debug messages
   - Consider adding new distribution types if needed

3. **Foreign Key Violations**: Ensure `distribution_types` table is populated before running data migration
   - Run `create_distribution_tables.py` first
   - Verify with `test_distribution_migrations.py`

### Verification Queries

```sql
-- Check table counts
SELECT 'distribution_types' as table_name, COUNT(*) as count FROM distribution_types
UNION ALL
SELECT 'resource_distributions', COUNT(*) FROM resource_distributions;

-- Check for orphaned records
SELECT COUNT(*) as orphaned_count
FROM resource_distributions rd
LEFT JOIN distribution_types dt ON rd.distribution_type_id = dt.id
WHERE dt.id IS NULL;

-- Top distribution types
SELECT dt.distribution_type, COUNT(rd.id) as count
FROM distribution_types dt
LEFT JOIN resource_distributions rd ON dt.id = rd.distribution_type_id
GROUP BY dt.id, dt.distribution_type
ORDER BY count DESC;
```
