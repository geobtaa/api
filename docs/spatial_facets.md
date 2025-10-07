# Spatial Facets Service

## Overview

The Spatial Facets Service provides hierarchical geographic faceting for resources based on their bounding boxes. It uses Who's on First (WOF) gazetteer data to determine which geographic entities (countries, regions/states, counties) a resource's bounding box overlaps with.

## Architecture

### Components

1. **SpatialFacetService** (`app/services/spatial_facet_service.py`)
   - Core service that computes spatial facets from bounding boxes
   - Validates and processes ENVELOPE format bounding boxes
   - Queries WOF gazetteer data using PostGIS spatial operations

2. **Celery Tasks** (`app/tasks/spatial_facets.py`)
   - `index_spatial_facets_batch`: Processes batches of resources
   - `index_all_spatial_facets`: Orchestrates full indexing of all resources
   - `reindex_spatial_facets_resource`: Reindexes a single resource

3. **Database Storage** (`resource_spatial_facets` table)
   - Stores computed spatial facets as JSONB
   - Indexed for fast querying
   - Includes timestamps for tracking updates

4. **Elasticsearch Integration** (`app/elasticsearch/index.py`)
   - Transforms WOF data into pipe-delimited strings for faceting
   - Indexes spatial facets for search aggregations

## Data Flow

```
Resource (dcat_bbox)
    ↓
SpatialFacetService._parse_bbox_to_geometry()
    ↓
Validation & Special Case Handling
    ├── Global datasets (geo_global = true)
    ├── Point locations (auto-buffered)
    └── Polar datasets (latitude-dependent validation)
    ↓
PostGIS Spatial Queries against WOF Gazetteer
    ├── Country (centroid-based)
    ├── Regions (intersection-based)
    └── Counties (intersection-based with threshold)
    ↓
Store in resource_spatial_facets table
    ↓
Index into Elasticsearch for faceting
```

## Hierarchical Facet Structure

### 1. Global (geo_global)
- **Type**: Boolean
- **Logic**: Detects if bbox covers entire world (or near-global with 1° tolerance)
- **Format**: `true` or `false`
- **Use Case**: Identifies worldwide datasets

### 2. Country (geo_country)
- **Type**: Single dictionary (JSONB in DB, formatted string in ES)
- **Logic**: Centroid-based - uses center point of bbox
- **Format**: 
  - DB: `{"name": "United States", "wok_id": 85633793, "parent_id": 102191575}`
  - ES: `"85633793|102191575|United States"` (wok_id|parent_id|name)
- **WOF Source**: `gazetteer_wof_spr` joined with `gazetteer_wof_geojson`
- **Filter**: `placetype = 'country'` and `source = 'quattroshapes'`

### 3. Region/State (geo_region)
- **Type**: Array of dictionaries
- **Logic**: Intersection-based - all regions that overlap bbox
- **Format**:
  - DB: `[{"name": "Indiana", "wok_id": 85688709, "parent_id": 85633793}]`
  - ES: `["85688709|85633793|Indiana"]`
- **WOF Source**: `gazetteer_wof_spr` joined with `gazetteer_wof_geojson`
- **Filter**: `placetype = 'region'`, `country = 'US'`, `source = 'quattroshapes'`
- **Ordering**: By intersection area (largest first)

### 4. County (geo_county)
- **Type**: Array of dictionaries
- **Logic**: Intersection-based with 0.1% overlap threshold
- **Format**:
  - DB: `[{"name": "Marion", "wok_id": 102086465, "parent_id": 85688709, "state_abbrev": "IN"}]`
  - ES: `["102086465|85688709|IN|Marion"]` (wok_id|parent_id|state_abbrev|name)
- **WOF Source**: `county_state_relationships` materialized view
- **Optimization**: Pre-joined county-state relationships for performance
- **Threshold**: Resources must overlap at least 0.1% of bbox area
- **Ordering**: By intersection area (largest first)
- **Limit**: Maximum 100 counties per resource

## Bounding Box Validation

The service includes sophisticated validation to handle various geographic edge cases:

### Valid Coordinate Ranges
- Longitude: -180° to 180°
- Latitude: -90° to 90°
- Min/max relationships must be valid (xmin < xmax, ymin < ymax)

### Special Cases

#### 1. Global Datasets
```python
# Detects: ENVELOPE(-180, 180, 90, -90) and near-global variants
# Tolerance: ±1° on each edge
# Result: geo_global = true, no hierarchical facets computed
```

#### 2. Point Locations
```python
# Detects: ENVELOPE(x, x, y, y) where coordinates are identical
# Action: Auto-buffer by 0.001° (~100m at equator)
# Result: Creates valid bbox for spatial processing
```

#### 3. Polar Datasets
```python
# Challenge: Lines of longitude converge at poles
# Solution: Latitude-dependent longitude span validation
# At equator (0°): max 90° longitude span
# At poles (90°): max 180° longitude span
# Linear interpolation between: max_span = 90 + (|avg_lat| / 90) * 90
```

#### 4. Line Features
```python
# Detects: Vertical lines (xmin = xmax) or horizontal lines (ymin = ymax)
# Action: Buffer by 0.001° in the collapsed dimension
# Result: Creates valid bbox with area
```

### Invalid Patterns Rejected
- Antipodal edges (spans ≥180° longitude, except global)
- Extremely large non-polar bounding boxes (>90° latitude span)
- Zero-area bounding boxes (<0.001° in any dimension)
- Coordinate range violations

## Who's on First Integration

### Data Sources

The service queries three main gazetteer tables:

1. **gazetteer_wof_spr** (Simplified Point Records)
   - Core WOF metadata: name, placetype, parent relationships
   - Indexed by `wok_id`, `placetype`, `country`

2. **gazetteer_wof_geojson** (Geometry Data)
   - PostGIS geometry for spatial operations
   - Multiple geometry sources per feature (primary, quattroshapes, etc.)
   - Spatially indexed for performance

3. **county_state_relationships** (Materialized View)
   - Pre-joined county and state data
   - Optimized for fast county lookups
   - Includes state abbreviations and hierarchical IDs

### Spatial Query Strategy

#### Country Determination
```sql
-- Uses centroid of bbox, finds containing country
WITH bbox AS (
    SELECT ST_SetSRID(ST_MakeEnvelope(xmin, ymin, xmax, ymax), 4326) AS geom
),
centroid AS (
    SELECT ST_PointOnSurface(bbox.geom) AS point FROM bbox
)
SELECT wof.name, wof.wok_id, wof.parent_id
FROM gazetteer_wof_spr wof
JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
WHERE wof.placetype = 'country'
  AND ST_Contains(geojson.geometry, centroid.point)
```

#### Region/State Determination
```sql
-- Finds all regions that intersect bbox, ordered by overlap area
WITH bbox AS (
    SELECT ST_SetSRID(ST_MakeEnvelope(xmin, ymin, xmax, ymax), 4326) AS geom
)
SELECT wof.name, wof.wok_id, wof.parent_id
FROM gazetteer_wof_spr wof
JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
WHERE wof.placetype = 'region'
  AND wof.country = 'US'
  AND ST_Intersects(geojson.geometry, bbox.geom)
ORDER BY ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) DESC
```

#### County Determination
```sql
-- Finds counties with minimum 0.1% overlap threshold
WITH bbox AS (
    SELECT ST_SetSRID(ST_MakeEnvelope(xmin, ymin, xmax, ymax), 4326) AS geom
),
bbox_area AS (
    SELECT ST_Area(bbox.geom::geography) AS total_area FROM bbox
)
SELECT csr.county_name, csr.county_wok_id, csr.state_wok_id, csr.state_abbrev
FROM county_state_relationships csr
JOIN gazetteer_wof_geojson geojson ON csr.county_wok_id = geojson.wok_id
WHERE ST_Intersects(geojson.geometry, bbox.geom)
  AND ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) / 
      bbox_area.total_area >= 0.001
ORDER BY ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) DESC
LIMIT 100
```

### Geometry Source Selection

WOF provides multiple geometry sources. The service prioritizes:
- **quattroshapes** for countries and regions (more accurate administrative boundaries)
- **Primary geometries** as fallback
- Filters out alt_label variants to avoid duplicates

## Database Schema

### resource_spatial_facets Table

```sql
CREATE TABLE resource_spatial_facets (
    resource_id VARCHAR(255) PRIMARY KEY,
    geo_global BOOLEAN DEFAULT FALSE,
    geo_country JSONB,
    geo_region JSONB,
    geo_county JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);

-- Indexes for faceting
CREATE INDEX idx_resource_spatial_facets_geo_global ON resource_spatial_facets (geo_global);
CREATE INDEX idx_resource_spatial_facets_geo_country_gin ON resource_spatial_facets USING GIN (geo_country);
CREATE INDEX idx_resource_spatial_facets_geo_region_gin ON resource_spatial_facets USING GIN (geo_region);
CREATE INDEX idx_resource_spatial_facets_geo_county_gin ON resource_spatial_facets USING GIN (geo_county);
```

### Data Format Examples

```json
{
  "resource_id": "example-123",
  "geo_global": false,
  "geo_country": {
    "name": "United States",
    "wok_id": 85633793,
    "parent_id": 102191575
  },
  "geo_region": [
    {
      "name": "Indiana",
      "wok_id": 85688709,
      "parent_id": 85633793
    },
    {
      "name": "Illinois",
      "wok_id": 85688697,
      "parent_id": 85633793
    }
  ],
  "geo_county": [
    {
      "name": "Marion",
      "wok_id": 102086465,
      "parent_id": 85688709,
      "state_abbrev": "IN"
    }
  ]
}
```

## Elasticsearch Integration

### Mapping

```json
{
  "geo_global": {"type": "boolean"},
  "geo_country": {"type": "keyword"},
  "geo_region": {"type": "keyword"},
  "geo_county": {"type": "keyword"}
}
```

### Transformation for Indexing

The `get_spatial_facets()` function in `app/elasticsearch/index.py` transforms JSONB data:

```python
# Country: dict → pipe-delimited string
{"name": "United States", "wok_id": 85633793, "parent_id": 102191575}
→ "85633793|102191575|United States"

# Regions: array of dicts → array of pipe-delimited strings
[{"name": "Indiana", "wok_id": 85688709, "parent_id": 85633793}]
→ ["85688709|85633793|Indiana"]

# Counties: array of dicts → array of pipe-delimited strings
[{"name": "Marion", "wok_id": 102086465, "parent_id": 85688709, "state_abbrev": "IN"}]
→ ["102086465|85688709|IN|Marion"]
```

### Aggregations

Elasticsearch aggregations are configured in `app/elasticsearch/search.py`:

```python
"aggs": {
    "geo_global_agg": {
        "terms": {"field": "geo_global", "size": 10}
    },
    "geo_country_agg": {
        "terms": {"field": "geo_country", "size": 20}
    },
    "geo_region_agg": {
        "terms": {"field": "geo_region", "size": 50}
    },
    "geo_county_agg": {
        "terms": {"field": "geo_county", "size": 100}
    }
}
```

## Processing Workflow

### Initial Indexing

1. **Trigger**: Call `/api/v1/admin/spatial-facets/index` or run Celery task
2. **Query**: Fetch all resources with `dcat_bbox IS NOT NULL`
3. **Batch**: Split into batches of 100 resources
4. **Process**: For each resource:
   - Parse and validate bounding box
   - Check for global/point/special cases
   - Query WOF gazetteer with PostGIS
   - Store results in `resource_spatial_facets`
5. **Elasticsearch**: Reindex to include spatial facets

### Updating a Single Resource

```python
from app.tasks.spatial_facets import reindex_spatial_facets_resource

# Recompute and update spatial facets for one resource
result = reindex_spatial_facets_resource.delay("resource-id-123")
```

### Monitoring Progress

```bash
# Check indexing status
SELECT 
    COUNT(*) as total_indexed,
    COUNT(*) FILTER (WHERE geo_global = true) as global_datasets,
    COUNT(*) FILTER (WHERE geo_country IS NOT NULL) as with_country,
    COUNT(*) FILTER (WHERE geo_region IS NOT NULL) as with_regions,
    COUNT(*) FILTER (WHERE geo_county IS NOT NULL) as with_counties
FROM resource_spatial_facets;
```

## Debug Mode

Enable debug mode to include overlap percentages in results:

```python
service = SpatialFacetService(resource_dict)
facets = await service.get_spatial_facets(session, debug=True)

# Results include overlap_percent:
# {
#   "geo.region": [
#     {"name": "Indiana", "wok_id": 85688709, "parent_id": 85633793, "overlap_percent": 85}
#   ]
# }
```

This is useful for:
- Understanding spatial coverage
- Debugging edge cases
- Analyzing multi-region datasets

## Performance Considerations

### Optimizations

1. **Spatial Indexes**: All geometries in `gazetteer_wof_geojson` are spatially indexed
2. **Materialized View**: `county_state_relationships` pre-joins county and state data
3. **Batch Processing**: Celery processes resources in parallel batches
4. **Connection Pooling**: Database connections are pooled and reused
5. **Overlap Threshold**: 0.1% threshold for counties reduces noise

### Bottlenecks

- PostGIS spatial operations (especially for complex polygons)
- Large bounding boxes that intersect many counties
- Concurrent processing limited by database connections

### Scaling Tips

- Increase Celery worker count for faster batch processing
- Adjust batch size based on bbox complexity (smaller for complex geometries)
- Monitor database connection pool usage
- Consider caching for frequently accessed spatial facets

## Troubleshooting

### No Spatial Facets Computed

**Symptoms**: Resources have bounding boxes but no facets

**Possible Causes**:
1. Invalid bounding box format → Check ENVELOPE syntax
2. Bbox outside WOF coverage → Currently only US regions/counties supported
3. Bbox fails validation → Check for point locations, extreme sizes, etc.

**Solution**: Check logs for "Invalid bounding box" or "Could not parse" warnings

### Global Dataset Not Detected

**Symptoms**: Worldwide dataset gets country/region facets instead of geo_global

**Possible Causes**:
1. Bbox not exactly (-180, 180, 90, -90)
2. Bbox outside 1° tolerance for near-global detection

**Solution**: Verify bbox coordinates, adjust tolerance if needed

### Missing Counties

**Symptoms**: Bbox overlaps counties but none are returned

**Possible Causes**:
1. Overlap below 0.1% threshold
2. Missing county geometry data in WOF
3. Quattroshapes geometry not available

**Solution**: 
- Lower threshold in query
- Check `gazetteer_wof_geojson` for county geometries
- Verify WOF import completed successfully

## Related Documentation

- [Gazetteer Data Management](gazetteer_data_management.md) - WOF import and updates
- [Gazetteer API](gazetteer_api.md) - Querying gazetteer data
- [Search API](search.md) - Using spatial facets in search
- [Testing](testing.md) - Spatial facet test coverage

## API Endpoints

### Get Spatial Facets for a Resource
```
GET /api/v1/resources/{id}/spatial_facets?debug=true
```

### Trigger Full Reindexing
```
POST /api/v1/admin/spatial-facets/index
```

### Check Indexing Status
```
GET /api/v1/admin/spatial-facets/status
```

