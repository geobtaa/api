# Parameter Reference

{% include-markdown "includes/wip.md" %}

## Search Parameters

Applies to `GET /api/v1/search` unless noted otherwise.

| Parameter | Type | Endpoints | Description |
| :---- | :---- | :---- | :---- |
| `q` | string | `/search`, `/search/facets/{facet_name}`, `/suggest`, `/map/h3`, `/ogc/.../items` | Full-text query string. |
| `page` | integer | `/search`, `/search/facets/{facet_name}`, `/ogc/.../items` | Page number (minimum `1`). |
| `per_page` | integer | `/search`, `/search/facets/{facet_name}` | Items per page (`1-100`). |
| `sort` | string | `/search`, `/search/facets/{facet_name}` | `/search`: `relevance`, `year_desc`, `year_asc`, `title_asc`, `title_desc`; facets: `count_desc`, `count_asc`, `alpha_asc`, `alpha_desc`. |
| `search_field` | string | `/search` | Search field hint (`all_fields`, etc). |
| `fields` | string (CSV) | `/search`, `/resources/{id}`, `/resources/`, `/resources/{id}/metadata*` | Comma-separated fields to include in response. |
| `facets` | string (CSV) | `/search` | Comma-separated facets to include in payload. |
| `meta` | boolean | `/search` | Include per-resource `meta` block (default `true`). |
| `format` | string | `/search`, `/resources/{id}`, `/resources/`, `/resources/{id}/metadata/display` | JSON format options (`json`, `jsonp` where supported); metadata display supports `iso`, `fgdc`, `html`. |
| `callback` | string | JSONP-capable endpoints | JSONP callback name (supported only on endpoints that use `create_response` / `create_jsonapi_response`). |
| `adv_q` | string (JSON) | `/search`, `/search/facets/{facet_name}` | JSON array of clauses like `{"op":"AND|OR|NOT","f":"dct_title_s","q":"Iowa"}`. |
| `q_facet` | string | `/search/facets/{facet_name}` | Filters facet values by text. |
| `fq` | object | `/search` (`POST` body) | Legacy/object-style include filters (`field -> values`). |
| `include_filters` | object | `/search`, `/search/facets/{facet_name}`, `/map/h3` | Include filter object (same logical purpose as `fq`). |
| `exclude_filters` | object | `/search`, `/search/facets/{facet_name}`, `/map/h3` | Exclude filter object. |
| `include_filters[geo][type]` | string | `/search` | Spatial filter type (for examples: `bbox`, `distance`, `polygon`). |
| `include_filters[geo][field]` | string | `/search` | Spatial field (typically `dcat_bbox`). |
| `include_filters[geo][relation]` | string | `/search` | Spatial relation such as `within` or `overlap`. |
| `include_filters[geo][top_left][lat|lon]` | number/string | `/search` (bbox) | BBox top-left coordinate values. |
| `include_filters[geo][bottom_right][lat|lon]` | number/string | `/search` (bbox) | BBox bottom-right coordinate values. |
| `bbox` | string (`west,south,east,north`) | `/map/h3`, `/ogc/.../items` | Viewport/OGC bbox constraint. |
| `resolution` | integer | `/map/h3` | H3 resolution (`2-8`). |
| `sortby` | string | `/ogc/.../items` | OGC sort expression (e.g. `title`, `-title`, `modified`). |
| `limit` | integer | `/ogc/.../items`, `/home/blog-posts`, `/ogm/harvest/failures` | Max items returned (endpoint-specific bounds). |
| `datetime` | string | `/ogc/.../items` | OGC temporal filter (currently limited support). |

## Resource Endpoint Parameters

| Parameter | Type | Endpoints | Description |
| :---- | :---- | :---- | :---- |
| `skip` | integer | `/resources/` | Offset for list pagination. |
| `limit` | integer | `/resources/`, `/ogm/harvest/failures`, `/home/blog-posts` | Max rows/items returned. |
| `debug` | boolean | `/resources/{id}/spatial-facets` | Include overlap-ratio diagnostics. |
| `embed` | boolean | `/resources/{id}/ogm-viewer` | Embed mode for iframe-friendly OGM viewer output. |
| `variant` | string | `/resources/{id}/thumbnail`, `/resources/{id}/thumbnail/no-cache` | Placeholder variant (`icon-basemap` default, `icon-gradient`). |
| `theme` | string | `/home/blog-posts` | Theme ID from frontend theme registry. |
| `tag` | string | `/home/blog-posts` | Filter home blog posts by tag (case-insensitive exact match). |
| `repo_name` | string | `/ogm/harvest/failures` | Filter failures to one OGM repository. |
| `include_with_errors` | boolean | `/ogm/harvest/failures` | Include runs with import errors, not only hard-failed runs. |
| `offset` | integer | `/ogm/harvest/failures` | Result offset for paging. |

## Path Parameters

| Parameter | Type | Endpoints | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | `/resources/{id}*` | Canonical resource identifier. |
| `facet_name` | string | `/search/facets/{facet_name}` | Facet field (e.g. `gbl_resourceClass_sm`). |
| `resource_id` | string | `/static-maps/{resource_id}`, `/thumbnails/{resource_id}` | Resource ID for static-map and thumbnail serving. |
| `map_id` | string | `/static-maps/institutions/{map_id}` | Institution map identifier. |
| `map_hash` | string | `/static-map-assets/{map_hash}` | Cache key for generated static-map assets. |
| `recordId` | string | `/api/v1/ogc/collections/btaa-records/items/{recordId}` | OGC single-item identifier. |
