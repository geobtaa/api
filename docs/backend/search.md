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

## Pagination links

Search and gazetteer pagination links use the scheme and host (including any port)
from `APPLICATION_URL` when it is set. This keeps links on HTTPS when the public
API uses HTTPS but the backend receives HTTP requests. The request path is
preserved, so an `/api/v1/` suffix in `APPLICATION_URL` is not duplicated.
Allowed query parameters, including repeated filters, remain in each link.

When `APPLICATION_URL` is unset or empty, links use the request URL's origin.
Local development can use an HTTP value such as `http://localhost:8000`.

## Parameters

The `/api/v1/search` endpoint supports a variety of query and filter parameters for flexible searching and faceting. Below is a table of all supported parameters:

| Parameter         | Type     | Required | Description                                                                                      | Example Value(s)                                  |
|-------------------|----------|----------|--------------------------------------------------------------------------------------------------|---------------------------------------------------|
| `q`               | string   | No       | Search query string                                                                              | `roads minnesota`                                 |
| `adv_q`           | JSON array | No     | Ordered advanced clauses with `op`, `f`, and `q` keys                                            | `[{"op":"AND","f":"dct_spatial_sm","q":"Wisconsin"}]` |
| `page`            | integer  | No       | Page number (1-based)                                                                            | `1`, `2`                                          |
| `per_page`        | integer  | No       | Number of resources per page                                                                         | `10`, `25`                                        |
| `sort`            | string   | No       | Sort option: `relevance`, `year_desc`, `year_asc`, `title_asc`, `title_desc`                     | `year_desc`                                       |
| `callback`        | string   | No       | JSONP callback name (for JSONP support)                                                          | `myCallback`                                      |
| `include_non_public` | boolean | No       | Include unpublished and suppressed records in Elasticsearch-backed responses                      | `true`                                            |
| `include_filter_operator` | `or` \| `and` | No | Combine repeated values within one include-filter field. The API default is `or`; the web search UI sends `and` for drill-down faceting. | `and` |
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

## Record group searches

Keyword search includes the source Code (`b1g_code_s`) and administrative Tags
(`b1g_adminTags_sm`). For example, share `/search?q=%2220d-0006%22` for a code
or `/search?q=missing_bbox` for a tag. These keyword fields match whole values;
ordinary searches retain the existing title and description relevance boosts.

An ISO day query such as `/search?q=2026-06-30` also matches records accessioned
on that UTC day, including timestamps after midnight. It can also match text
containing that date. To restrict matches to accession dates, use an advanced
clause (supported by results, facets, and maps):

```json
[{"op":"AND","f":"b1g_dateAccessioned_dt","q":"2026-06-30"}]
```

Both `b1g_dateAccessioned_dt` and the legacy `b1g_dateAccessioned_s` field are
supported in advanced clauses and the API's `search_field` parameter. For
example: `/api/v1/search?search_field=b1g_dateAccessioned_dt&q=2026-06-30`.
Day matching starts at midnight UTC and excludes midnight of the next day.
Publication and suppression filters still apply to all group searches. Keyword day searches check both accession-date fields; field-specific searches
check only the selected field. The index mapping explicitly declares the `_dt`
field as a date. Use `make reindex` to rebuild a local index with this mapping.

## Advanced Boolean queries

The advanced search builder sends its ordered rows in `adv_q`. Each `AND` row
starts a required positive group, and each `OR` row joins the preceding positive
group. `NOT` rows are global exclusions. A leading `OR` has no left-hand
alternative and therefore behaves like a single required clause.

For example:

```json
[
  {"op": "AND", "f": "dct_spatial_sm", "q": "Wisconsin"},
  {"op": "AND", "f": "schema_provider_s", "q": "Provider A"},
  {"op": "OR", "f": "schema_provider_s", "q": "Provider B"},
  {"op": "NOT", "f": "dct_accessRights_s", "q": "Restricted"}
]
```

is evaluated as `Wisconsin AND (Provider A OR Provider B) AND NOT Restricted`.
An ordinary `q` parameter, when present, is also required alongside the complete
advanced expression. Search results, facet-value suggestions, and map counts all
compile `adv_q` through the same Boolean query builder.

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
- Repeating a value for one field uses the API-compatible OR default unless `include_filter_operator=and` is supplied. The web search UI always supplies `and`, so every selected facet value narrows the result set. Advanced Boolean clauses remain separate in `adv_q`.
- Frontends typically **do not need** per-item facet URLs; they can update query params directly.

## Facet values endpoint (`/api/v1/search/facets/{facet_name}`)

The facet values endpoint is used for pagination/sorting/search-within-facet. It returns:

- `data`: array of `facet_value` resources with minimal attributes:
  - `attributes.value`
  - `attributes.hits`
  - `attributes.label` may be omitted (clients can display `String(value)`)
- `links.applyTemplate`: single template URL to apply a facet value in the current search context

Pass the same `include_filter_operator` used for the results request so facet
counts and result totals use identical semantics. The map H3 endpoint accepts
the option for the same reason.

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

### BBox relevance score: containment + IoU

Whenever the bbox filter is present (`type=bbox` with `top_left`/`bottom_right`), the search query is wrapped in an Elasticsearch `script_score`.

For each candidate resource, the script computes:

- `intersection_area`: area of overlap between the query bbox and the document bbox (both treated as axis-aligned rectangles)
- `doc_area`: area of the document bbox
- `query_area`: area of the query bbox
- `union_area = doc_area + query_area - intersection_area`
- `overlapRatio = intersection_area / union_area` (this is an IoU-style overlap)
- `containmentRatio = intersection_area / doc_area` (the fraction of the resource
  extent covered by the query)

It combines the two spatial signals and Elasticsearch's *base* score (`_score`) using:

`spatialScore = 0.7 * containmentRatio + 0.3 * overlapRatio`

`final_score = baseScore * (1 + 0.8 * spatialScore)`

Where `baseScore` comes from the rest of the query:

- If you are doing a bbox-only search (no `q` and no `adv_q`), the query effectively becomes `match_all`, so `baseScore` is ~constant. In that case, ranking is driven by the combined containment and IoU score.
- If you also provide a text query (`q`) and/or advanced query (`adv_q`), then `baseScore` varies by document. In that case, bbox “fit” is a multiplier, not the only signal.

### Overlap “threshold”: preventing near-zero matches

In addition to the `relation`-based geo-shape filter, bbox searches also apply a hard filter that rejects documents when the query covers only a trivial fraction of the resource bbox:

- `containmentRatio >= MIN_BBOX_IOU_OVERLAP_RATIO`
- Default: `MIN_BBOX_IOU_OVERLAP_RATIO = 0.001` (0.1%)

The environment-variable name is retained for backward compatibility. The threshold
uses document containment rather than IoU so that a city-sized resource fully inside
a state-sized query remains eligible. It still removes very large resources when the
query touches less than 0.1% of their bbox. The threshold affects eligibility; the
combined containment and IoU score controls relevance ordering.

### Why `Overlap` may not look like “Best Fit” / “Closest Fit”

If you expect “Best Fit” ordering (highest overlap first), there are a few reasons it may not be obvious:

1. **Text relevance can dominate when `q` is present**
   - Because `final_score` multiplies by `(1 + 0.8 * spatialScore)`, the spatial boost is bounded between 1.0 and 1.8.
   - If `baseScore` differs significantly across documents, those differences can reorder results even when some documents overlap the query bbox better.

2. **`Overlap` is not centroid-distance scoring**
   - The bbox scoring uses bbox rectangle IoU computed from numeric `bbox_*` extents, not centroid distance and not polygon geometry overlap.
   - If stakeholders expect “closest” by distance-to-center (or similar), this implementation will not match that intuition.

3. **`Within` changes the meaning of IoU**
   - For documents that are truly `within` the query envelope, the intersection area is effectively the document bbox area, so IoU becomes driven mainly by the *size* of the document bbox relative to the query bbox (not by exact placement within the query).

4. **Sort can override relevance**
   - If the UI/API uses a sort other than `relevance`, the ES bbox score ordering won’t be used.

### Checking what the backend thinks the “fit” is

The API attaches `bbox_overlap_ratio`, `bbox_containment_ratio`, and
`bbox_spatial_score` to per-resource metadata when a bbox filter is active.

To verify “Best Fit” ordering in practice:

- Request `sort=relevance`
- Use an empty `q` (bbox-only) so `baseScore` is constant
- Compare `bbox_spatial_score` across results: higher values should correspond to higher `final_score` for bbox-only searches.

### Environment variables

You can tune how aggressively near-zero bbox overlaps are filtered via:

- `MIN_BBOX_IOU_OVERLAP_RATIO` (default `0.001`; retained name, applied as a
  minimum document-containment ratio)

## Catalog relevance v2

`SEARCH_RELEVANCE_VERSION=legacy|v2` defaults to `legacy`. V2 requires a full
source reindex; merely updating a mapping or search analyzer does not populate
new analyzed fields. An index readiness marker prevents using an incomplete
build. Existing original text and keyword fields are preserved.

The `catalog_english` analyzer tokenizes words, removes English possessives,
lowercases, removes English stop words, and applies `light_english` stemming.
For example, `maps` and `map` match each other. This is English lexical matching,
not semantic search: `routes`, `tracks`, and `lines` are not declared synonyms.

Ordinary unscoped queries first require all analyzed terms across titles,
descriptions, summaries, subjects, keywords, creators, publishers, providers,
spatial labels, display notes, themes, resource classes/types, local collection
labels, and inherited collection titles. Original title/phrase matches receive
additional ranking weight. A successful strict search is never broadened just
because a requested page or map viewport contains no hits.

Only after a successful zero-hit probe under all active logical filters does
v2 use `minimum_should_match: "2<75%"`. One- and two-term queries still require
all terms; three terms require two, four require three, and five require three.
No further relaxation occurs. Partial searches also boost matching title terms
and spatial labels: real-Elasticsearch regression testing found that the original
full-phrase boosts alone could rank an unrelated city's streetcar map too highly
for a conversational query. These are scoring signals, not geographic filters.

Quotes, Boolean syntax, wildcards, explicit search fields, advanced clauses,
identifiers, and accession dates retain literal search behavior. Empty searches
still browse; a nonempty search reduced entirely to stop words returns no hits.
Errors and timeouts do not trigger broader matching. All explicit filters and
publication/suppression rules remain in effect.

### Collection context

The index-only `collection_titles` field contains deduplicated titles of direct,
published, unsuppressed parent Collections resolved through `pcdm_memberOf_sm`
and `dct_isPartOf_sm`. It is not exported as Aardvark metadata. Local collection
labels are independently searchable. No ancestors or external URLs are followed.
Batch lookups are shared by full and incremental indexing. Updating or deleting
a parent refreshes direct members from their stored relationship arrays, so stale
titles are removed even after the parent disappears.

This helps find already-indexed sheets by collection name; it does not ingest
sheets that exist only in an external index map.

### Response metadata

V2 search and facet responses include optional `meta.matching`:

```json
{"mode":"partial_terms","broadened":true,"version":"v2"}
```

Modes are `literal`, `all_terms`, and `partial_terms`. The H3 endpoint returns the
same object as top-level `matching`. The web interface shows
“No results matched all search terms. Showing partial matches.” only when partial
matches exist; the original query remains in the input and URL.

The matching stage is shared across results, facets, and maps. Rendering viewports
and facet autocomplete text do not affect its selection. Stage decisions cache for
60 seconds and include the concrete index generation/revision and logical query.
On a stage-cache miss, short result searches (up to three whitespace-delimited
words) use the strict response's total hit count as the existence check. A zero
total triggers one partial request, reusing the strict response's spelling
suggestions. Longer queries retain the lightweight probe: computing a complete
strict response first made cold natural-language misses slower in the synthetic
benchmark. This scheduling threshold does not change analysis, term requirements,
ranking, or filters. Empty pagination pages do not broaden the query.
Aggregation-only requests also use a candidate-only strict probe; ranking boosts
are omitted from that probe.

An in-process LRU holds at most 4,096 stage decisions for 60 seconds, ahead of the
shared cache. It also works when endpoint caching is disabled. Every request
still reads the authoritative index revision from Elasticsearch before consulting
these decisions. Mapping validation is projected to the required fields and
reused only within that request; it is never cached across requests. This keeps
revision changes and alias cutovers visible without repeating the same metadata
call at each response-cache layer. Result retrieval requests only IDs and numeric
extents from Elasticsearch; PostgreSQL hydration still supplies public metadata.

Result and aggregation caches also separate generations and matching behavior.
Browser search, facet, and map request URLs carry a response-version token to
bypass older responses. Their server proxies preserve matching metadata and use
`private, no-store`: only the backend knows the current index revision, so it
owns response caching. This prevents proxy caches from retaining an earlier
matching stage after indexing or a relevance-version change.
Incremental indexing advances the search revision after refreshing writes.
Atomic builds compare source row versions, replay changed records and affected
members, and remove deleted records before marking the new index ready. A source
table SHARE lock covers final reconciliation and alias cutover; catalog reads
continue while resource writes wait. Incremental batches pin their concrete index
before loading source rows, preventing delayed writes to a newly switched alias.
The frontend proxies pass the JSON body through without a separate response cache.

### Local relevance validation

Use an isolated Elasticsearch 9 instance and run:

```bash
make test-search-relevance SEARCH_RELEVANCE_TEST_URL=http://localhost:19283
```

This target uses unique `test-search-relevance-*` indices and removes only its own
indices. It does not rebuild the application index or require a database clone.
The test instance must already be running. The ordinary backend suite skips these
integration cases unless `SEARCH_RELEVANCE_TEST_URL` is supplied.

Fixtures capture public metadata on 2026-11-13, including the 14 Minneapolis
streetcar records and the collection in issue #483. Synthetic distractors are
explicitly named in the tests. A/B/C recall and top-result ranking are checked,
as are normalization, exact syntax, collection matching, spatial constraints,
visibility, pagination, and aggregation parity.

For local source rebuilding, use `make reindex`. Detailed activation, concurrent
import coordination, and rollback procedures belong in restricted operations
documentation. Before activation, the maintainer must update that runbook and
validate full-catalog indexing completeness and relevance, cache invalidation,
and latency; investigate a greater-than-20% p95 regression. Keep legacy behavior
available until validation succeeds.

Optionally supply `SEARCH_RELEVANCE_TEST_DB_URL` pointing at a separate disposable
PostgreSQL service to exercise real membership queries, row-version detection,
and cutover locking. Those tests create and remove a uniquely named schema;
they never use the application's resource table. Without that variable, only the
PostgreSQL-specific cases skip.

Set `SEARCH_RELEVANCE_BENCHMARK_REPORT` to an output JSON path to run the optional
fixture microbenchmark. It compares fresh legacy/v2 indices, uncached response
p95, index size, and bulk ingestion duration, and flags p95 growth above 20%.
It interleaves legacy, a frozen original-v2 execution path, and optimized v2 with
a reproducible shuffle and 40 warmup queries per mode. All response and facet
caches are disabled; each sample records individual Elasticsearch call timings.

Use `SEARCH_RELEVANCE_BENCHMARK_WORKLOAD=results` for the real result execution
path, including facets and suggestions but excluding PostgreSQL hydration and
HTTP/proxy overhead. The default `query` workload retains the original planner
microbenchmark, including the separate aggregation-style existence probe.
`SEARCH_RELEVANCE_BENCHMARK_STAGE_CACHE=cold` (default) clears stage decisions
before every request; `warm` measures reuse of stage decisions without caching
result responses. Both must be reported separately.
Both reference and optimized modes use the same stage-cache implementation in
this benchmark, so warm comparisons isolate request planning and payload changes,
not Redis/L1 savings or request-scope deduplication across API cache layers.
The iteration count defaults
to 100 per query/mode and is configurable with
`SEARCH_RELEVANCE_BENCHMARK_ITERATIONS`. `SEARCH_RELEVANCE_BENCHMARK_COPIES=200`
creates 4,800 explicitly synthetic copies of fixture documents for a larger
retrieval workload. This is not a representative full-catalog benchmark or an
ingestion benchmark for collection-title resolution.

These diagnostics do not replace full-catalog activation validation. In
particular, a genuinely cold partial search still requires a second retrieval;
do not use warm-stage numbers to waive a cold-stage latency regression. Keep v2
disabled until the remaining performance gate has been assessed on the catalog.
The results-page analytics properties include the matching metadata so partial
match usage can be distinguished from strict searches, including cached responses.
