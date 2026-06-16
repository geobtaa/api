# Elasticsearch

## Indexing

### Indexing all documents
`curl -X POST http://localhost:8000/api/v1/index`

### Indexing a single document
`curl -X POST http://localhost:8000/api/v1/index?id=123`

## Searching

The Elasticsearch index contains all resource rows. Public search, facet, map,
suggestion, and similar-item queries filter to `publication_state=published` and
`gbl_suppressed_b=false` by default. Internal diagnostics can pass
`include_non_public=true` to include unpublished and suppressed records.

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
| `include_non_public` | boolean | No       | Include unpublished and suppressed records in Elasticsearch-backed responses                      | `true`                                            |
| `fq[spatial_agg][]`         | string[] | No       | Filter by spatial location (maps to `dct_spatial_sm`)                                            | `fq[spatial_agg][]=Minnesota`                     |
| `fq[resource_type_agg][]`   | string[] | No       | Filter by resource type (maps to `gbl_resourceType_sm`)                                          | `fq[resource_type_agg][]=Map`                     |
| `fq[resource_class_agg][]`  | string[] | No       | Filter by resource class (maps to `gbl_resourceClass_sm`)                                        | `fq[resource_class_agg][]=Datasets`               |
| `fq[index_year_agg][]`      | string[] | No       | Filter by index year (maps to `gbl_indexYear_im`)                                                | `fq[index_year_agg][]=2020`                       |
| `fq[language_agg][]`        | string[] | No       | Filter by human-readable language (maps to `b1g_language_sm`)                                     | `fq[language_agg][]=English`                      |
| `fq[creator_agg][]`         | string[] | No       | Filter by creator (maps to `dct_creator_sm`)                                                     | `fq[creator_agg][]=University of Minnesota`        |
| `fq[provider_agg][]`        | string[] | No       | Filter by provider (maps to `schema_provider_s`)                                                 | `fq[provider_agg][]=Test Provider`                |
| `fq[access_rights_agg][]`   | string[] | No       | Filter by access rights (maps to `dct_accessRights_s`)                                           | `fq[access_rights_agg][]=Public`                  |
| `fq[georeferenced_agg][]`   | string[] | No       | Filter by georeferenced status (maps to `gbl_georeferenced_b`)                                   | `fq[georeferenced_agg][]=true`                    |
| `fq[id_agg][]`              | string[] | No       | Filter by item ID (maps to `id`)                                                                 | `fq[id_agg][]=abc123`                             |
| `fq[geo_country_agg][]`     | string[] | No       | Filter by country using spatial facets (maps to `geo_country`)                                   | `fq[geo_country_agg][]=12345|0|United States`     |
| `fq[geo_region_agg][]`      | string[] | No       | Filter by region/state using spatial facets (maps to `geo_region`)                               | `fq[geo_region_agg][]=12345|0|Minnesota`         |
| `fq[geo_county_agg][]`      | string[] | No       | Filter by county using spatial facets (maps to `geo_county`)                                     | `fq[geo_county_agg][]=12345|0|MN|Hennepin County` |

## Facets in the response (JSON:API `included`)

Search results include facet aggregations in the top-level JSON:API `included` array.

### Facet resource shape (compact)

Each facet is a JSON:API-like resource:

- `type`: `"facet"`
- `id`: the facet field name (e.g. `dct_spatial_sm`, `gbl_resourceClass_sm`, `geo_region`)
- `attributes.label`: human-readable label
- `attributes.items`: **compact** array of tuples: `[[value, hits], ...]`
- `links.applyTemplate`: single URL template for “apply this facet value in the current search context”
  - placeholder: `{value}`
  - callers must URL-encode the substituted value

Example (illustrative):

```json
{
  "type": "facet",
  "id": "dct_spatial_sm",
  "links": {
    "applyTemplate": "/api/v1/search?q=&include_filters%5Bdct_spatial_sm%5D%5B%5D={value}"
  },
  "attributes": {
    "label": "Spatial Coverage",
    "items": [["Minnesota", 5757], ["Wisconsin", 1234]]
  }
}
```

Notes:

- Older clients may still use legacy query params (`fq[...][]`). Newer clients should prefer `include_filters[...][]` / `exclude_filters[...][]`.
- Frontends typically **do not need** per-item facet URLs; they can update query params directly.

## Facet values endpoint (`/api/v1/search/facets/{facet_name}`)

The facet values endpoint is used for pagination/sorting/search-within-facet. It returns:

- `data`: array of `facet_value` resources with minimal attributes:
  - `attributes.value`
  - `attributes.hits`
  - `attributes.label` may be omitted (clients can display `String(value)`)
- `links.applyTemplate`: single template URL to apply a facet value in the current search context

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

## Geospatial BBox Relevance Ranking (Within vs Overlap)

The UI offers a bbox location filter with two modes:

- `Within`: show resources whose stored bbox is fully contained by the query bbox.
- `Overlap`: show resources whose stored bbox intersects (overlaps) the query bbox.

### How the UI options map to Elasticsearch

When the bbox filter is active, the frontend sends `include_filters[geo]` with:

- `type=bbox`
- `field=dcat_bbox`
- `top_left` / `bottom_right`
- `relation=within` for `Within` mode and `relation=intersects` for `Overlap` mode.

On the backend, `relation` is applied to the Elasticsearch `geo_shape` query (using an `envelope` representation of `dcat_bbox`).

### Candidate selection: `within` vs `intersects`

The `relation` setting affects *which documents are eligible*:

For `relation=within`, Elasticsearch geo-shape semantics require the document envelope to be spatially *within* the query envelope. For `relation=intersects`, Elasticsearch geo-shape semantics require the document envelope to *intersect* the query envelope.

Important: relation controls eligibility, but the *relevance score* for bbox queries is computed separately (see below).

### BBox relevance score: IoU + (optional) text relevance multiplier

Whenever the bbox filter is present (`type=bbox` with `top_left`/`bottom_right`), the search query is wrapped in an Elasticsearch `script_score`.

For each candidate resource, the script computes:

- `intersection_area`: area of overlap between the query bbox and the document bbox (both treated as axis-aligned rectangles)
- `doc_area`: area of the document bbox
- `query_area`: area of the query bbox
- `union_area = doc_area + query_area - intersection_area`
- `overlapRatio = intersection_area / union_area` (this is an IoU-style overlap)

Then it combines this overlap ratio with Elasticsearch’s *base* score (`_score`) using:

`final_score = baseScore * (0.1 + 0.9 * overlapRatio)`

Where `baseScore` comes from the rest of the query:

- If you are doing a bbox-only search (no `q` and no `adv_q`), the query effectively becomes `match_all`, so `baseScore` is ~constant. In that case, ranking is driven mostly by `overlapRatio` (higher IoU comes first).
- If you also provide a text query (`q`) and/or advanced query (`adv_q`), then `baseScore` varies by document. In that case, bbox “fit” is a multiplier, not the only signal.

### Overlap “threshold”: preventing near-zero matches

In addition to the `relation`-based geo-shape filter, bbox searches also apply a hard filter that rejects documents with extremely small IoU:

- `overlapRatio >= MIN_BBOX_IOU_OVERLAP_RATIO`
- Default: `MIN_BBOX_IOU_OVERLAP_RATIO = 0.001` (0.1%)

This threshold affects eligibility (removes “barely touching” results). It does *not* control ordering beyond the fact that low-overlap results get excluded.

### Why `Overlap` may not look like “Best Fit” / “Closest Fit”

If you expect “Best Fit” ordering (highest overlap first), there are a few reasons it may not be obvious:

1. **Text relevance can dominate when `q` is present**
   - Because `final_score` multiplies by `(0.1 + 0.9 * overlapRatio)`, overlap ratio differences are bounded between 0.1 and 1.0.
   - If `baseScore` differs significantly across documents, those differences can reorder results even when some documents overlap the query bbox better.

2. **`Overlap` is not centroid-distance scoring**
   - The bbox scoring uses bbox rectangle IoU computed from numeric `bbox_*` extents, not centroid distance and not polygon geometry overlap.
   - If stakeholders expect “closest” by distance-to-center (or similar), this implementation will not match that intuition.

3. **`Within` changes the meaning of IoU**
   - For documents that are truly `within` the query envelope, the intersection area is effectively the document bbox area, so IoU becomes driven mainly by the *size* of the document bbox relative to the query bbox (not by exact placement within the query).

4. **Sort can override relevance**
   - If the UI/API uses a sort other than `relevance`, the ES bbox score ordering won’t be used.

### Checking what the backend thinks the “fit” is

The API attaches the computed `bbox_overlap_ratio` into per-resource metadata when a bbox filter is active.

To verify “Best Fit” ordering in practice:

- Request `sort=relevance`
- Use an empty `q` (bbox-only) so `baseScore` is constant
- Compare `bbox_overlap_ratio` across results: higher values should correspond to higher `final_score` for bbox-only searches.

### Environment variables

You can tune how aggressively near-zero bbox overlaps are filtered via:

- `MIN_BBOX_IOU_OVERLAP_RATIO` (default `0.001`, meaning 0.1% IoU)
