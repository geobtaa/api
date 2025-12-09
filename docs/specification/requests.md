# Requests (Endpoints)

<link rel="stylesheet" href="https://pyscript.net/releases/2024.1.1/core.css">
<script type="module" src="https://pyscript.net/releases/2024.1.1/core.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>

<py-config>
packages = ["requests", "pyodide-http"]
</py-config>

{% include-markdown "includes/wip.md" %}

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
        'resource-location': 'example-resource-location',
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

<details id="example-resource-links" class="example-collapsible">
<summary><strong>Resource — Links</strong></summary>

{% include "includes/examples/example-14-resource-links.html" %}

</details>

<details id="example-resource-location" class="example-collapsible">
<summary><strong>Resource — Location</strong></summary>

{% include "includes/examples/example-22-resource-location.html" %}

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