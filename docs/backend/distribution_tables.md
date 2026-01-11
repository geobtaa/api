# Distribution Tables Documentation

## Overview

The distribution tables provide a normalized, relational structure for storing resource distribution data that was previously stored in the `dct_references_s` JSON field. This migration improves data integrity, query performance, and enables better API endpoints for accessing distribution information.

## Table Structure

### `distribution_types`

A lookup table containing standardized distribution type definitions based on the OpenGeoMetadata Aardvark specification.

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

#### Fields

- **`id`**: Primary key, auto-incrementing integer
- **`name`**: Unique identifier for the distribution type (e.g., `download`, `iiif_manifest`)
- **`distribution_type`**: Human-readable name (e.g., "Download file", "IIIF Presentation API Manifest")
- **`distribution_uri`**: Standard URI for the distribution type (e.g., `http://schema.org/downloadUrl`)
- **`label`**: Boolean indicating if this type typically includes labels
- **`note`**: Additional documentation or usage notes
- **`position`**: Display order for UI purposes
- **`created_at`**: Timestamp when record was created
- **`updated_at`**: Timestamp when record was last updated (auto-updated via trigger)

#### Indexes

- Primary key on `id`
- Unique index on `name`
- Index on `distribution_uri`
- Index on `position`

### `resource_distributions`

The main table storing individual distribution records for each resource.

```sql
CREATE TABLE resource_distributions (
    id SERIAL PRIMARY KEY,
    resource_id VARCHAR(255) NOT NULL,
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

#### Fields

- **`id`**: Primary key, auto-incrementing integer
- **`resource_id`**: Foreign key to the resource (matches `resources.id`)
- **`distribution_type_id`**: Foreign key to `distribution_types.id`
- **`url`**: The actual URL for this distribution
- **`label`**: Optional label for the distribution (e.g., "PDF", "Original JPEG")
- **`position`**: Order of this distribution within the resource
- **`created_at`**: Timestamp when record was created
- **`updated_at`**: Timestamp when record was last updated (auto-updated via trigger)
- **`import_distribution_id`**: Optional tracking ID from the original import

#### Indexes

- Primary key on `id`
- Index on `resource_id` for fast lookups by resource
- Index on `distribution_type_id` for filtering by type
- Index on `url` for URL-based queries
- Index on `position` for ordering
- Index on `import_distribution_id` for import tracking
- Composite index on `(resource_id, distribution_type_id)` for efficient filtering

## Migration Scripts

### 1. `create_distribution_tables.py`

Creates both distribution tables with proper structure, indexes, and constraints.

**Usage:**
```bash
python db/migrations/create_distribution_tables.py
```

**What it does:**
- Creates `distribution_types` table
- Creates `resource_distributions` table with foreign key constraint
- Inserts 27 predefined distribution types from the Aardvark specification
- Creates all necessary indexes for optimal performance
- Sets up update triggers for automatic `updated_at` timestamp management
- Updates table statistics for query optimization

**Distribution Types Included:**
- ArcGIS services (DynamicMapLayer, FeatureLayer, ImageMapLayer, TiledMapLayer)
- Cloud Optimized GeoTIFF (COG)
- Documentation types (download, external, data dictionary)
- IIIF services (Image API, Presentation API)
- Metadata formats (FGDC, ISO 19139, MODS, HTML)
- Web services (WMS, WFS, WCS, WMTS)
- Tile services (XYZ, TMS, PMTiles, TileJSON)
- Other formats (GeoJSON, oEmbed, OpenIndexMap)

### 2. `populate_resource_distributions.py`

Migrates distribution data from the `dct_references_s` JSON field to the new relational structure.

**Usage:**
```bash
python db/migrations/populate_resource_distributions.py
```

**What it does:**
- Extracts distribution data from `dct_references_s` JSON field in `resources` table
- Maps distribution URIs to distribution type IDs
- Handles both simple string URLs and complex array structures
- Creates individual records for each distribution
- Preserves labels and ordering information
- Provides detailed logging and error reporting

**Data Transformation:**

**Simple Case:**
```json
{
  "http://schema.org/url": "https://example.com/resource"
}
```
Becomes:
```sql
INSERT INTO resource_distributions (resource_id, distribution_type_id, url, position)
VALUES ('resource-id', 7, 'https://example.com/resource', 0);
```

**Complex Case (Multiple Distributions):**
```json
{
  "http://schema.org/downloadUrl": [
    {"url": "https://example.com/file1.pdf", "label": "PDF"},
    {"url": "https://example.com/file2.jpg", "label": "Original JPEG"}
  ]
}
```
Becomes:
```sql
INSERT INTO resource_distributions (resource_id, distribution_type_id, url, label, position)
VALUES ('resource-id', 8, 'https://example.com/file1.pdf', 'PDF', 0);
INSERT INTO resource_distributions (resource_id, distribution_type_id, url, label, position)
VALUES ('resource-id', 8, 'https://example.com/file2.jpg', 'Original JPEG', 1);
```

### 3. `rename_friendlier_id_to_resource_id.py`

Renames the `friendlier_id` column to `resource_id` for consistency with other relational tables.

**Usage:**
```bash
python db/migrations/rename_friendlier_id_to_resource_id.py
```

**What it does:**
- Safely renames `friendlier_id` column to `resource_id`
- Drops and recreates indexes with new column names
- Preserves all data and constraints
- Handles both test and production databases

### 4. `run_distribution_migrations.py`

Master script that runs all distribution migrations in the correct order.

**Usage:**
```bash
python db/migrations/run_distribution_migrations.py
```

**Migration Order:**
1. Create distribution tables
2. Populate resource distributions
3. Verify migration success

### 5. `test_distribution_migrations.py`

Test script to verify migrations worked correctly.

**Usage:**
```bash
python db/migrations/test_distribution_migrations.py
```

**What it checks:**
- Table existence and structure
- Data integrity and foreign key relationships
- Distribution statistics and counts
- Orphaned records detection
- Index performance

## API Integration

### New Endpoint: `/resources/{id}/distributions`

The new API endpoint provides access to distribution data in JSON:API format.

**URL:** `GET /api/v1/resources/{id}/distributions`

**Response Format:**
```json
{
  "jsonapi": {
    "version": "1.1",
    "profile": [
      "https://gin.btaa.org/ld/profiles/ogm-aardvark-btaa.profile.jsonld",
      "https://gin.btaa.org/ld/profiles/ogm-ui.profile.jsonld"
    ]
  },
  "links": {
    "self": "http://localhost:8000/api/v1/resources/{id}/distributions"
  },
  "data": {
    "type": "distributions",
    "id": "{resource_id}",
    "attributes": {
      "distributions": [
        {
          "id": 123,
          "resource_id": "resource-id",
          "url": "https://example.com/file.pdf",
          "label": "PDF",
          "position": 0,
          "created_at": "2025-10-06T20:18:39.046143+00:00",
          "updated_at": "2025-10-06T20:18:39.046143+00:00",
          "import_distribution_id": null,
          "distribution_type_id": 8,
          "distribution_type_name": "download",
          "distribution_type": "Download file",
          "distribution_uri": "http://schema.org/downloadUrl",
          "distribution_note": "Link to download file..."
        }
      ],
      "count": 1
    }
  }
}
```

**Features:**
- JSON:API compliant response format
- Cached with 24-hour TTL
- Proper error handling (404 for non-existent resources)
- Includes full distribution type information
- Ordered by position and creation date

## Benefits

### 1. **Normalized Structure**
- Replaces complex JSON parsing with standard SQL queries
- Eliminates data duplication and inconsistencies
- Enables proper foreign key constraints

### 2. **Better Performance**
- Indexed lookups instead of JSON field scanning
- Optimized queries for specific distribution types
- Reduced memory usage for large datasets

### 3. **Data Integrity**
- Foreign key constraints ensure referential integrity
- Standardized distribution type definitions
- Validation of distribution URIs

### 4. **Queryability**
- Standard SQL queries instead of JSON operations
- Easy filtering by distribution type
- Efficient aggregation and reporting

### 5. **Extensibility**
- Easy to add new distribution types
- Support for additional metadata fields
- API versioning and evolution

## Migration Results

### Production Database Statistics

- **Resources processed**: 74,579
- **Total distributions created**: 270,997
- **Success rate**: 100% (0 errors)
- **Distribution types**: 27 different types
- **Resources with labels**: 50,165 distributions

### Distribution Type Breakdown

| Type | Count | Description |
|------|-------|-------------|
| Documentation (External) | 72,159 | External documentation links |
| Download file | 61,410 | File downloads with labels |
| oEmbed | 27,270 | oEmbed service endpoints |
| Web Mapping Service (WMS) | 25,668 | WMS service endpoints |
| IIIF Presentation API Manifest | 24,635 | IIIF manifest URLs |
| Web Feature Service (WFS) | 18,411 | WFS service endpoints |
| Metadata in FGDC | 11,931 | FGDC metadata records |
| IIIF Image API | 8,803 | IIIF image service endpoints |
| Data dictionary | 8,514 | Supplemental documentation |
| Web Coverage Service (WCS) | 7,261 | WCS service endpoints |
| Cloud Optimized GeoTIFF (COG) | 2,634 | COG file references |
| Metadata in ISO 19139 | 1,873 | ISO metadata records |
| OpenIndexMap | 166 | OpenIndexMap references |
| Metadata in HTML | 80 | HTML metadata records |
| ArcGIS FeatureLayer | 77 | ArcGIS feature services |
| ArcGIS ImageMapLayer | 53 | ArcGIS image services |
| GeoJSON | 19 | GeoJSON file references |
| PMTiles | 17 | PMTiles references |
| ArcGIS DynamicMapLayer | 6 | ArcGIS dynamic services |
| Thumbnail file | 4 | Thumbnail images |
| WMTS | 2 | WMTS service endpoints |
| XYZ tiles | 2 | XYZ tile services |
| TileJSON | 1 | TileJSON references |
| Tile Mapping Service (TMS) | 1 | TMS service endpoint |

## Usage Examples

### Query All Distributions for a Resource

```sql
SELECT 
    rd.url,
    rd.label,
    dt.distribution_type,
    dt.distribution_uri
FROM resource_distributions rd
JOIN distribution_types dt ON rd.distribution_type_id = dt.id
WHERE rd.resource_id = '13020-j01t-wq81'
ORDER BY rd.position;
```

### Find Resources with Specific Distribution Types

```sql
SELECT DISTINCT rd.resource_id
FROM resource_distributions rd
JOIN distribution_types dt ON rd.distribution_type_id = dt.id
WHERE dt.name = 'download';
```

### Count Distributions by Type

```sql
SELECT 
    dt.distribution_type,
    COUNT(rd.id) as count
FROM distribution_types dt
LEFT JOIN resource_distributions rd ON dt.id = rd.distribution_type_id
GROUP BY dt.id, dt.distribution_type
ORDER BY count DESC;
```

### Find Resources with Multiple Download Formats

```sql
SELECT 
    rd.resource_id,
    COUNT(*) as download_count,
    STRING_AGG(rd.label, ', ') as labels
FROM resource_distributions rd
JOIN distribution_types dt ON rd.distribution_type_id = dt.id
WHERE dt.name = 'download'
GROUP BY rd.resource_id
HAVING COUNT(*) > 1
ORDER BY download_count DESC;
```

## Maintenance

### Adding New Distribution Types

1. Insert new record into `distribution_types` table:
```sql
INSERT INTO distribution_types (name, distribution_type, distribution_uri, note, position)
VALUES ('new_type', 'New Distribution Type', 'http://example.com/uri', 'Description', 100);
```

2. Update application code to handle the new type
3. Re-run population script if needed for existing data

### Updating Distribution Data

```sql
-- Update a distribution URL
UPDATE resource_distributions 
SET url = 'https://new-url.com', updated_at = NOW()
WHERE id = 123;

-- Update distribution position
UPDATE resource_distributions 
SET position = 1, updated_at = NOW()
WHERE resource_id = 'resource-id' AND id = 123;
```

### Monitoring and Maintenance

- Monitor distribution counts and types
- Check for orphaned records
- Verify foreign key constraints
- Update table statistics regularly
- Monitor query performance

## Future Enhancements

### Potential Improvements

1. **Additional Metadata Fields**
   - File size information
   - MIME type detection
   - Access rights and restrictions
   - Geographic coverage for spatial distributions

2. **Enhanced API Features**
   - Filtering by distribution type
   - Pagination for large distribution sets
   - Bulk operations for multiple resources

3. **Data Quality Improvements**
   - URL validation and health checking
   - Duplicate detection and removal
   - Automatic label generation

4. **Performance Optimizations**
   - Materialized views for common queries
   - Partitioning for large datasets
   - Advanced indexing strategies

This migration successfully transforms the distribution data from an unstructured JSON format into a robust, queryable relational structure that supports the growing needs of the BTAA OGM API.
