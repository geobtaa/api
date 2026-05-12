# Endpoints

<link rel="stylesheet" href="https://pyscript.net/releases/2024.1.1/core.css">
<script type="module" src="https://pyscript.net/releases/2024.1.1/core.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>

<py-config>
packages = ["requests", "pyodide-http"]
</py-config>

<script type="py">
# Normalize requests defaults for browser/Pyodide runtime.
# Browsers reject some transport headers (e.g., Accept-Encoding, Connection),
# which otherwise creates noisy console warnings when requests is patched to fetch.
try:
    import requests

    def _safe_default_headers():
        return {
            "User-Agent": "python-requests/pyodide",
            "Accept": "*/*",
        }

    requests.utils.default_headers = _safe_default_headers
    requests.sessions.default_headers = _safe_default_headers
except Exception:
    # Keep docs functional even if requests import/patching changes.
    pass
</script>

{% include-markdown "includes/wip.md" %}

<script>
function copyCode(codeId) {
    const codeElement = document.getElementById(codeId);
    const text = codeElement ? codeElement.textContent : "";
    if (!text) return;

    navigator.clipboard.writeText(text).then(() => {
        const btn = event && event.target ? event.target : null;
        if (!btn) return;
        const originalText = btn.textContent;
        btn.textContent = 'Copied';
        btn.style.background = '#48bb78';

        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '#2d3748';
        }, 1500);
    });
}

function openTab(evt, tabId) {
    const btn = evt.currentTarget;
    const container = btn.closest('.example-block');
    if (!container) return;

    const tabContents = container.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove("active");
    }

    const tabBtns = container.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabBtns.length; i++) {
        tabBtns[i].classList.remove("active");
    }

    document.getElementById(tabId).classList.add("active");
    btn.classList.add("active");
}
</script>

## API Swagger Documentation

### Development Server
https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/docs

## Endpoint Index

The tables below enumerate all current non-admin endpoints exposed by the API.

### Root

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/` | API root |

### Search

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/search` | Search resources (query params) |
| POST | `/api/v1/search` | Search resources (JSON body) |
| GET | `/api/v1/search/facets/{facet_name}` | Paginated facet values |
| GET | `/api/v1/suggest` | Autosuggestions |

### Resources

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/resources/` | List resources |
| GET | `/api/v1/resources/{id}` | Get one resource |
| GET | `/api/v1/resources/{id}/citation` | Citation payload |
| GET | `/api/v1/resources/{id}/citation/json-ld` | Citation as JSON-LD |
| GET | `/api/v1/resources/{id}/citation/ris` | Citation in RIS format |
| GET | `/api/v1/resources/{id}/citation/bibtex` | Citation in BibTeX format |
| GET | `/api/v1/resources/{id}/data-dictionaries` | Resource data dictionary entries |
| GET | `/api/v1/resources/{id}/distributions` | Resource distributions |
| GET | `/api/v1/resources/{id}/downloads` | Download links and metadata |
| GET | `/api/v1/resources/{id}/downloads/generated/{download_type}` | Prepare generated download and return file URL |
| GET | `/api/v1/resources/{id}/downloads/generated/{download_type}/file` | Download generated file attachment |
| GET | `/api/v1/resources/{id}/links` | Resource links |
| GET | `/api/v1/resources/{id}/metadata` | Combined metadata |
| GET | `/api/v1/resources/{id}/metadata/ogm` | OGM-transformed metadata |
| GET | `/api/v1/resources/{id}/metadata/b1g` | B1G metadata format |
| GET | `/api/v1/resources/{id}/metadata/display` | HTML metadata display |
| GET | `/api/v1/resources/{id}/ogm-viewer` | OGM viewer payload |
| GET | `/api/v1/resources/{id}/relationships` | Related resources |
| GET | `/api/v1/resources/{id}/similar-items` | Similar resources |
| GET | `/api/v1/resources/{id}/spatial-facets` | Spatial facet values |
| GET | `/api/v1/resources/{id}/static-map` | Cached static map image |
| GET | `/api/v1/resources/{id}/static-map/no-cache` | Uncached static map image |
| GET | `/api/v1/resources/{id}/thumbnail` | Cached thumbnail image |
| GET | `/api/v1/resources/{id}/thumbnail/no-cache` | Uncached thumbnail image |
| GET | `/api/v1/resources/{id}/viewer` | Viewer configuration payload |

### Maps and Thumbnails

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/map/h3` | H3 map tile/geometry data |
| GET | `/api/v1/static-maps/institutions/{map_id}` | Institution static map |
| GET | `/api/v1/static-map-assets/{map_hash}` | Generated static-map asset by hash |
| GET | `/api/v1/static-maps/{resource_id}/geometry` | Resource geometry for static-map rendering |
| GET | `/api/v1/static-maps/{resource_id}/resource-class-icon` | Resource-class icon used by static-map rendering |
| GET | `/api/v1/static-maps/{resource_id}` | Resource static map |
| GET | `/api/v1/thumbnails/placeholder` | Placeholder thumbnail |
| GET | `/api/v1/thumbnails/{resource_id}` | Thumbnail by resource ID |

### OGM and Harvest Status

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/ogm/repos` | Enabled/known OGM repositories |
| GET | `/api/v1/ogm/harvest/failures` | OGM harvest failure summary |

### OGC API

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/ogc/` | OGC API landing page |
| GET | `/api/v1/ogc/conformance` | OGC conformance classes |
| GET | `/api/v1/ogc/collections` | Collections listing |
| GET | `/api/v1/ogc/collections/btaa-records` | BTAA records collection |
| GET | `/api/v1/ogc/collections/btaa-records/queryables` | Queryable fields |
| GET | `/api/v1/ogc/collections/btaa-records/sortables` | Sortable fields |
| GET | `/api/v1/ogc/collections/btaa-records/items` | Collection items |
| GET | `/api/v1/ogc/collections/btaa-records/items/{recordId}` | Single OGC record |

### Model Context Protocol (MCP)

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/mcp` | Model Context Protocol endpoint |
| POST | `/api/v1/mcp` | Streamable HTTP MCP transport |

## Root Endpoint

Provides a basic service-level entrypoint for API discovery.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/` | API root response |

#### Interactive Example: API Root

{% include "includes/examples/example-28-api-root.html" %}

**Response notes**

- Returns a lightweight JSON payload suitable for liveness and API entrypoint checks.
- Useful for quickly validating API availability before issuing search/resource requests.

## Search Endpoint

Supports both GET (simple) and POST (complex) forms.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET or POST | `/search` | Returns a JSON:API resultset of Resources |

#### Interactive Example: Simple Search

{% include "includes/examples/example-1-simple-search.html" %}

## Search Examples

<details id="example-field-directed" class="example-collapsible">
<summary><strong>Field-Directed Search</strong></summary>

{% include "includes/examples/example-4-field-directed-search.html" %}

</details>

<details id="example-boolean" class="example-collapsible">
<summary><strong>Boolean Search</strong></summary>

{% include "includes/examples/example-3-boolean-search.html" %}

</details>


<details id="example-faceted-includes" class="example-collapsible">
<summary><strong>Faceted Search — Includes</strong></summary>

{% include "includes/examples/example-6-faceted-search-includes.html" %}

</details>

<details id="example-faceted-excludes" class="example-collapsible">
<summary><strong>Faceted Search — Excludes</strong></summary>

{% include "includes/examples/example-7-faceted-search-excludes.html" %}

</details>

<details id="example-spatial-bbox" class="example-collapsible">
<summary><strong>Spatial Search — BBox</strong></summary>

{% include "includes/examples/example-8-spatial-bbox.html" %}

</details>

<details id="example-spatial-distance" class="example-collapsible">
<summary><strong>Spatial Search — Distance</strong></summary>

{% include "includes/examples/example-9-spatial-distance.html" %}

</details>

<details id="example-spatial-polygon" class="example-collapsible">
<summary><strong>Spatial Search — Polygon</strong></summary>

{% include "includes/examples/example-10-spatial-polygon.html" %}

</details>

<details id="example-advanced" class="example-collapsible">
<summary><strong>Advanced Search</strong></summary>

{% include "includes/examples/example-11-advanced-search.html" %}

</details>

<script>
(function() {
    // Map of example IDs to their details elements
    const exampleMap = {
        'field-directed': 'example-field-directed',
        'boolean': 'example-boolean',
        'faceted': 'example-faceted',
        'faceted-includes': 'example-faceted-includes',
        'faceted-excludes': 'example-faceted-excludes',
        'spatial-bbox': 'example-spatial-bbox',
        'spatial-distance': 'example-spatial-distance',
        'spatial-polygon': 'example-spatial-polygon',
        'advanced': 'example-advanced',
        'list-resources': 'example-list-resources',
        'resource-distributions': 'example-resource-distributions',
        'resource-links': 'example-resource-links',
        'resource-metadata': 'example-resource-metadata',
        'resource-relationships': 'example-resource-relationships',
        'resource-spatial-facets': 'example-resource-spatial-facets',
        'resource-ogm-viewer': 'example-resource-ogm-viewer',
        'resource-citation': 'example-resource-citation',
        'resource-downloads': 'example-resource-downloads',
        'resource-similar-items': 'example-resource-similar-items',
        'resource-static-map': 'example-resource-static-map',
        'resource-thumbnail': 'example-resource-thumbnail',
        'resource-viewer': 'example-resource-viewer'
    };
    
    // Open example from URL hash on page load
    function openExampleFromHash() {
        const hash = window.location.hash.substring(1); // Remove #
        if (hash && exampleMap[hash]) {
            const details = document.getElementById(exampleMap[hash]);
            if (details) {
                details.open = true;
                // Scroll to the element
                setTimeout(() => {
                    details.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            }
        }
    }
    
    // Update URL hash when details are toggled
    function setupHashUpdates() {
        const details = document.querySelectorAll('.example-collapsible');
        details.forEach(detail => {
            detail.addEventListener('toggle', function() {
                if (this.open) {
                    // Find the key for this element
                    const key = Object.keys(exampleMap).find(k => exampleMap[k] === this.id);
                    if (key) {
                        // Update URL without scrolling
                        history.replaceState(null, '', '#' + key);
                    }
                } else {
                    // Remove hash if closing and it's the current one
                    const hash = window.location.hash.substring(1);
                    const key = Object.keys(exampleMap).find(k => exampleMap[k] === this.id);
                    if (hash === key) {
                        history.replaceState(null, '', window.location.pathname + window.location.search);
                    }
                }
            });
        });
    }
    
    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            openExampleFromHash();
            setupHashUpdates();
        });
    } else {
        openExampleFromHash();
        setupHashUpdates();
    }
})();
</script>

**Search Parameters**

| Parameter | Type | Description |
| :---- | :---- | :---- |
| `q` | string | Full‑text query (default `*:*`). |
| `fq` | object | Active facet include filters (same as include_filters) |
| `search_field` | string (CSV) | Search field (all_fields [default], etc.) |
| `page` | integer | Current page of results |
| `per_page` | integer | Number of results to return |
| `sort` | string | Sort option (relevance, year\_desc, year\_asc, title\_asc, title\_desc) |
| `format` | string | Format option (JSON [default], JSONP) |
| `callback` | string | JSONP callback name |
| `fields` | string (CSV) | List of fields to return |
| `facets` | string (CSV) | List of facets to return |
| `include_filters` | object | Active facet include filters (same as fq) |
| `exclude_filters` | object | Active facet exclude filters |
| `meta` | boolean | Include META (default true) |
| `adv_q` | string | JSON array of advanced query clauses. Example: `{'op': 'AND|OR|NOT', 'f': 'dct_title_s', 'q': 'Iowa'}` | 

## Search Facet Pagination

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/search/facets/{facet_name}` | Get paginated, sortable facet values for a specific facet field within a search resultset. |

#### Interactive Example: Search Facet Pagination

{% include "includes/examples/example-26-facet-pagination.html" %}

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `facet_name` | string | ✔️ | Facet field name (e.g., `gbl_resourceClass_sm`) |
| `q` | string |  | Search query to filter resultset |
| `page` | integer |  | Page number (minimum: 1, default: 1) |
| `per_page` | integer |  | Facet values per page (1-100, default: 10) |
| `sort` | string |  | Sort option: `count_desc`, `count_asc`, `alpha_asc`, `alpha_desc` (default: `count_desc`) |
| `q_facet` | string |  | Search query to filter facet values |
| `adv_q` | string |  | JSON array of advanced query clauses. Each clause: `{'op': 'AND\|OR\|NOT', 'f': 'dct_title_s', 'q': 'Iowa'}` |

## Search Autosuggestions

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/suggest` | Get search suggestions. |

#### Interactive Example: Search Autosuggestions

{% include "includes/examples/example-27-suggest.html" %}

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `q` | string | ✔️ | Search query for suggestions |
| `callback` | string |  | JSONP callback name |

## Resource Endpoint

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}` | Returns a single Aardvark record, wrapped in JSON:API frontmatter. |

#### Interactive Example: Obtain a Resource

{% include "includes/examples/example-2-obtain-resource.html" %}

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |
| `fields` | string (CSV) |  | Subset of fields to include |

## Resource Helper Endpoints

<details id="example-list-resources" class="example-collapsible">
<summary><strong>List Resources</strong></summary>

{% include "includes/examples/example-12-list-resources.html" %}

</details>

<details id="example-resource-citation" class="example-collapsible">
<summary><strong>Resource — Citation</strong></summary>

{% include "includes/examples/example-19-resource-citation.html" %}

</details>

<details id="example-resource-distributions" class="example-collapsible">
<summary><strong>Resource — Distributions</strong></summary>

{% include "includes/examples/example-13-resource-distributions.html" %}

</details>

<details id="example-resource-downloads" class="example-collapsible">
<summary><strong>Resource — Downloads</strong></summary>

{% include "includes/examples/example-20-resource-downloads.html" %}

</details>

### Generated Download Workflow

The `downloads` payload may include generated exports with:

- `generated: true`
- `download_type` (for example: `shapefile`, `geojson`, `csv`, `kmz`, `geotiff`)
- `generation_path` (API path for preparing the file)

Generated downloads use a two-step flow:

1. Call `GET /api/v1/resources/{id}/downloads/generated/{download_type}` to prepare (or reuse) the generated artifact.
2. Use the returned `download_url` (or call `/file` directly) to download the attachment.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/resources/{id}/downloads/generated/{download_type}` | Prepares and returns JSON metadata for the generated artifact |
| GET | `/api/v1/resources/{id}/downloads/generated/{download_type}/file` | Returns file attachment bytes (`Content-Disposition: attachment`) |

**Supported `download_type` values**

- `shapefile` (EPSG:4326 Shapefile)
- `geojson`
- `csv`
- `kmz`
- `geotiff`

**Prepare example**

```bash
curl "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/resources/stanford-bs024ty5255/downloads/generated/geojson"
```

Example response:

```json
{
  "download_type": "geojson",
  "file_name": "stanford-bs024ty5255-geojson.geojson",
  "file_path": "/app/tmp/cache/downloads/stanford-bs024ty5255-geojson.geojson",
  "content_type": "application/json",
  "download_url": "/api/v1/resources/stanford-bs024ty5255/downloads/generated/geojson/file"
}
```

**File download example**

```bash
curl -L -OJ "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/resources/stanford-bs024ty5255/downloads/generated/geojson/file"
```

<details id="example-resource-links" class="example-collapsible">
<summary><strong>Resource — Links</strong></summary>

{% include "includes/examples/example-14-resource-links.html" %}

</details>

<details id="example-resource-metadata" class="example-collapsible">
<summary><strong>Resource — Metadata Retrieval</strong></summary>

{% include "includes/examples/example-15-resource-metadata.html" %}

</details>

<details id="example-resource-ogm-viewer" class="example-collapsible">
<summary><strong>Resource — OGM Viewer Retrieval</strong></summary>

{% include "includes/examples/example-18-resource-ogm-viewer.html" %}

</details>

<details id="example-resource-relationships" class="example-collapsible">
<summary><strong>Resource — Relationships</strong></summary>

{% include "includes/examples/example-16-resource-relationships.html" %}

</details>

<details id="example-resource-similar-items" class="example-collapsible">
<summary><strong>Resource — Similar Items</strong></summary>

{% include "includes/examples/example-21-resource-similar-items.html" %}

</details>

<details id="example-resource-spatial-facets" class="example-collapsible">
<summary><strong>Resource — Spatial Facets</strong></summary>

{% include "includes/examples/example-17-resource-spatial-facets.html" %}

</details>

<details id="example-resource-static-map" class="example-collapsible">
<summary><strong>Resource — Static Map</strong></summary>

{% include "includes/examples/example-23-resource-static-map.html" %}

</details>

<details id="example-resource-thumbnail" class="example-collapsible">
<summary><strong>Resource — Thumbnail</strong></summary>

{% include "includes/examples/example-24-resource-thumbnail.html" %}

</details>

<details id="example-resource-viewer" class="example-collapsible">
<summary><strong>Resource — Viewer Data</strong></summary>

{% include "includes/examples/example-25-resource-viewer.html" %}

</details>

## Maps and Thumbnails Endpoints

Supports map geometry helpers and image retrieval endpoints used by frontend map and card UIs.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/map/h3` | H3 map tile/geometry data |
| GET | `/api/v1/static-maps/institutions/{map_id}` | Institution static map |
| GET | `/api/v1/static-map-assets/{map_hash}` | Generated static-map asset by hash |
| GET | `/api/v1/static-maps/{resource_id}/geometry` | Resource geometry for static-map rendering |
| GET | `/api/v1/static-maps/{resource_id}/resource-class-icon` | Resource-class icon used by static-map rendering |
| GET | `/api/v1/static-maps/{resource_id}` | Resource static map |
| GET | `/api/v1/thumbnails/placeholder` | Placeholder thumbnail |
| GET | `/api/v1/thumbnails/{resource_id}` | Thumbnail by resource ID |

#### Interactive Example: Placeholder Thumbnail

{% include "includes/examples/example-29-placeholder-thumbnail.html" %}

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `map_id` | string | endpoint-specific | Institution map identifier for `/static-maps/institutions/{map_id}` |
| `resource_id` | string | endpoint-specific | Resource identifier for `/static-maps/{resource_id}` and `/thumbnails/{resource_id}` |
| `map_hash` | string | endpoint-specific | Cache key/hash for `/static-map-assets/{map_hash}` |

## OGM and Harvest Status Endpoints

Read-only endpoints for OpenGeoMetadata repository listing and harvest failure visibility.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/ogm/repos` | Enabled/known OGM repositories |
| GET | `/api/v1/ogm/harvest/failures` | OGM harvest failure summary |

#### Interactive Example: OGM Repositories

{% include "includes/examples/example-30-ogm-repos.html" %}

**Response notes**

- `/ogm/repos` returns repository-level records used to track OGM ingestion sources.
- `/ogm/harvest/failures` returns recent failures for monitoring and debugging harvest issues.

## OGC API Endpoints

The OGC API surface exposes standards-aligned discovery and records access endpoints.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/ogc/` | OGC API landing page |
| GET | `/api/v1/ogc/conformance` | OGC conformance classes |
| GET | `/api/v1/ogc/collections` | Collections listing |
| GET | `/api/v1/ogc/collections/btaa-records` | BTAA records collection |
| GET | `/api/v1/ogc/collections/btaa-records/queryables` | Queryable fields |
| GET | `/api/v1/ogc/collections/btaa-records/sortables` | Sortable fields |
| GET | `/api/v1/ogc/collections/btaa-records/items` | Collection items |
| GET | `/api/v1/ogc/collections/btaa-records/items/{recordId}` | Single OGC record |

#### Interactive Example: OGC Collections

{% include "includes/examples/example-31-ogc-collections.html" %}

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `recordId` | string | endpoint-specific | Resource ID for `/api/v1/ogc/collections/btaa-records/items/{recordId}` |

## Model Context Protocol (MCP) Endpoint

Provides an MCP-compatible response for clients integrating the API through MCP conventions.

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/api/v1/mcp` | Model Context Protocol endpoint |

#### Interactive Example: MCP Endpoint

{% include "includes/examples/example-32-mcp-endpoint.html" %}

**Response notes**

- Intended for machine clients and tooling that expect MCP-compatible endpoint behavior.
- Keep response handling tolerant to additive fields as MCP support evolves.
