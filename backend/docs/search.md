# Elasticsearch

## Indexing

### Indexing all documents
`curl -X POST http://localhost:8000/api/v1/index`

### Indexing a single document
`curl -X POST http://localhost:8000/api/v1/index?id=123`

## Searching

### Searching all documents
`curl -X GET http://localhost:9200/geoblacklight/_search?q=*:*&pretty`

curl -X GET http://elasticsearch:9200/geoblacklight/_search?q=*:*&pretty

### View mapping
`curl -X GET http://localhost:9200/geoblacklight/_mapping?pretty`

## Troubleshooting

### Running out of space? Elasticsearch will be upset.

ES will turn read-only if it runs out of disk space. This is a problem because it means that the index is no longer writable.

To fix this, we can disable the disk space threshold and allow the index to be deleted.

```bash
curl -XPUT -H "Content-Type: application/json" http://localhost:9200/_cluster/settings -d '{ "transient": { "cluster.routing.allocation.disk.threshold_enabled": false } }'

curl -XPUT -H "Content-Type: application/json" http://localhost:9200/_all/_settings -d '{"index.blocks.read_only_allow_delete": null}'
```

# Search API Parameters

The `/api/v1/search` endpoint supports a variety of query and filter parameters for flexible searching and faceting. Below is a table of all supported parameters:

| Parameter         | Type     | Required | Description                                                                                      | Example Value(s)                                  |
|-------------------|----------|----------|--------------------------------------------------------------------------------------------------|---------------------------------------------------|
| `q`               | string   | No       | Search query string                                                                              | `roads minnesota`                                 |
| `page`            | integer  | No       | Page number (1-based)                                                                            | `1`, `2`                                          |
| `per_page`        | integer  | No       | Number of resources per page                                                                         | `10`, `25`                                        |
| `sort`            | string   | No       | Sort option: `relevance`, `year_desc`, `year_asc`, `title_asc`, `title_desc`                     | `year_desc`                                       |
| `callback`        | string   | No       | JSONP callback name (for JSONP support)                                                          | `myCallback`                                      |
| `fq[spatial_agg][]`         | string[] | No       | Filter by spatial location (maps to `dct_spatial_sm`)                                            | `fq[spatial_agg][]=Minnesota`                     |
| `fq[resource_type_agg][]`   | string[] | No       | Filter by resource type (maps to `gbl_resourceType_sm`)                                          | `fq[resource_type_agg][]=Map`                     |
| `fq[resource_class_agg][]`  | string[] | No       | Filter by resource class (maps to `gbl_resourceClass_sm`)                                        | `fq[resource_class_agg][]=Datasets`               |
| `fq[index_year_agg][]`      | string[] | No       | Filter by index year (maps to `gbl_indexYear_im`)                                                | `fq[index_year_agg][]=2020`                       |
| `fq[language_agg][]`        | string[] | No       | Filter by language (maps to `dct_language_sm`)                                                   | `fq[language_agg][]=English`                      |
| `fq[creator_agg][]`         | string[] | No       | Filter by creator (maps to `dct_creator_sm`)                                                     | `fq[creator_agg][]=University of Minnesota`        |
| `fq[provider_agg][]`        | string[] | No       | Filter by provider (maps to `schema_provider_s`)                                                 | `fq[provider_agg][]=Test Provider`                |
| `fq[access_rights_agg][]`   | string[] | No       | Filter by access rights (maps to `dct_accessRights_s`)                                           | `fq[access_rights_agg][]=Public`                  |
| `fq[georeferenced_agg][]`   | string[] | No       | Filter by georeferenced status (maps to `gbl_georeferenced_b`)                                   | `fq[georeferenced_agg][]=true`                    |
| `fq[id_agg][]`              | string[] | No       | Filter by item ID (maps to `id`)                                                                 | `fq[id_agg][]=abc123`                             |
| `fq[geo_country_agg][]`     | string[] | No       | Filter by country using spatial facets (maps to `geo_country`)                                   | `fq[geo_country_agg][]=12345|0|United States`     |
| `fq[geo_region_agg][]`      | string[] | No       | Filter by region/state using spatial facets (maps to `geo_region`)                               | `fq[geo_region_agg][]=12345|0|Minnesota`         |
| `fq[geo_county_agg][]`      | string[] | No       | Filter by county using spatial facets (maps to `geo_county`)                                     | `fq[geo_county_agg][]=12345|0|MN|Hennepin County` |

## Spatial Facets

The search endpoint includes spatial hierarchical facets that provide geographic filtering capabilities. These facets use Who's on First (WOF) identifiers and are formatted as pipe-delimited strings:

### Spatial Facet Format

All spatial facets follow the format: `wof_id|parent_id|name`

- **wof_id**: Who's on First identifier for the geographic entity
- **parent_id**: Parent entity's WOF identifier (0 for countries)
- **name**: Human-readable name of the geographic entity

### Spatial Facet Types

1. **Country Facets** (`geo_country_agg`): Format `wof_id|parent_id|name`
   - Example: `12345|0|United States`

2. **Region/State Facets** (`geo_region_agg`): Format `wof_id|parent_id|name`
   - Example: `12345|0|Minnesota`

3. **County Facets** (`geo_county_agg`): Format `wof_id|parent_id|state_abbrev|name`
   - Example: `12345|0|MN|Hennepin County`
   - Note: County facets include an additional state abbreviation field

### Using Spatial Facets

Spatial facets are automatically included in search results under the `included` section of the JSON:API response. You can filter results using these facets by including them in your query parameters:

```bash
# Filter by country
curl "http://localhost:8000/api/v1/search?fq[geo_country_agg][]=12345|0|United States"

# Filter by multiple regions
curl "http://localhost:8000/api/v1/search?fq[geo_region_agg][]=12345|0|Minnesota&fq[geo_region_agg][]=67890|0|Wisconsin"

# Filter by county
curl "http://localhost:8000/api/v1/search?fq[geo_county_agg][]=12345|0|MN|Hennepin County"
```

**Notes:**
- All `fq[...][]` parameters can be repeated to filter by multiple values.
- The `sort` parameter options are: `relevance`, `year_desc`, `year_asc`, `title_asc`, `title_desc`.
- The endpoint supports JSONP via the `callback` parameter.
- Spatial facets are generated from resource bounding boxes using PostGIS spatial queries against Who's on First gazetteer data.

## Facet Size Configuration

The number of facet values returned can be configured via environment variables:

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GEO_COUNTRY_FACET_SIZE` | 20 | Maximum number of country facets returned |
| `GEO_REGION_FACET_SIZE` | 50 | Maximum number of region/state facets returned |
| `GEO_COUNTY_FACET_SIZE` | 100 | Maximum number of county facets returned |
| `DEFAULT_FACET_SIZE` | 10 | Default size for all other facet types |

These limits help control response size and performance while ensuring relevant geographic diversity is available for filtering.