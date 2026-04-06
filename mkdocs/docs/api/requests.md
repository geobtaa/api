# Requests (Endpoints)

{% include-markdown "includes/wip.md" %}

JSON-LD context for search requests:

* Future: https://opengeometadata/api/search/1.0/context/request.json  
* Draft PR: [Online here](https://raw.githubusercontent.com/OpenGeoMetadata/opengeometadata.github.io/18896025536dae80b632aa5b059fb001d3d42c56/docs/api/search/1.0/context/request.json)

## Service Document

| Method | Path | Description |
| :---- | :---- | :---- |
| GET | `/service` | Returns API metadata, conformance, contact, and example URLs. |

## List Resources

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/` | Returns a list of Aardvark records. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |
| `page` | integer | Current page of results |
| `per_page` | integer | Number of results to return |
| `fields` | string (CSV) |  | Subset of fields to include |

## Resource Retrieval

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}` | Returns a single Aardvark record, wrapped in JSON:API frontmatter. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |
| `fields` | string (CSV) |  | Subset of fields to include |

## Resource Distributions

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/distributions` | Returns distribution information for a resource. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |

## Resource Links

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/links` | Returns link information for a resource. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |

## Resource OGM Aardvark Retrieval

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/ogm` | Returns a single raw Aardvark record. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |
| `fields` | string (CSV) |  | Subset of fields to include |

## Resource Relationships

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/relationships` | Returns relationship information for a resource. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |

## Resource Spatial Facets

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/spatial_facets` | Returns spatial facet information for a resource. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |

## Resource Summaries

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/summaries` | Returns summary information for a resource. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |

## Resource OGM Viewer Retrieval

| Method | Path | Notes |
| :---- | :---- | :---- |
| GET | `/resources/{id}/viewer` | Returns the Aardvark record presented in the OGM Viewer. |

**Parameters**

| Name | Type | Req? | Description |
| :---- | :---- | :---- | :---- |
| `id` | string | ✔️ | Canonical record ID |

## Search

Supports both GET (simple) and POST (complex) forms.

### GET `/search`

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



Example requests:

* GET /api/v1/search?q=soil+survey\&per\_page=20
* GET /api/v1/search??q=seattle&include_filters%5Bgbl_resourceClass_sm%5D%5B%5D=Maps
* GET /api/v1/search?q=seattle&exclude_filters%5Bdct_spatial_sm%5D%5B%5D=Iowa
* GET /api/v1/search?q=transportation&search_field=dct_subject_sm

### POST `/search`

Accepts a JSON body with the same parameters plus structured filters.

```json
{
  "q": "land cover",
  "include_filters": {
    "dct_provenance_s": ["Minnesota"],
    "gbl_resourceClass_sm": ["Datasets"]
  },
  "page": 1,
  "per_page": 50,
  "sort": "year_desc"
}
```

## Geospatial Search

Support for geospatial queries:

* Bounding Box  
* Distance-Radius  
* Polygon  
* Shape \+ Relation

### Bounding Box (bbox)

GET /search?q=land+cover\\  
\&include_filters\[geo\]\[type\]=bbox\\  
\&include_filters\[geo\]\[field\]=dcat_centroid\\  
\&include_filters\[geo\]\[top\_left\]\[lat\]=45.1\\  
\&include_filters\[geo\]\[top\_left\]\[lon\]=-94.0\\  
\&include_filters\[geo\]\[bottom\_right\]\[lat\]=44.7\\  
\&include_filters\[geo\]\[bottom\_right\]\[lon\]=-92.9\\  
\&limit=50\\  
\&sort=dct\_temporal\_sm%20desc

POST (`application/json`)

```json
{
  "q": "land cover",
  "filters": {
    "geo": {
      "type": "bbox",
      "field": "dcat_centroid",
      "top_left":     { "lat": 45.1, "lon": -94.0 },
      "bottom_right": { "lat": 44.7, "lon": -92.9 }
    }
  },
  "limit": 50,
  "sort": "dct_temporal_sm desc"
}
```

### Distance-Radius (`distance`)

GET /search?q=land+cover\\  
\&include_filters\[geo\]\[type\]=distance\\  
\&include_filters\[geo\]\[field\]=dcat_centroid\\  
\&include_filters\[geo\]\[center\]\[lat\]=44.98\\  
\&include_filters\[geo\]\[center\]\[lon\]=-93.27\\  
\&include_filters\[geo\]\[distance\]=25km\\  
\&limit=50

POST

```json
{
  "q": "land cover",
  "filters": {
    "geo": {
      "type": "distance",
      "field": "dcat_centroid",
      "center":   { "lat": 44.98, "lon": -93.27 },
      "distance": "25km"
    }
  },
  "limit": 50
}
```

### Polygon (`polygon`)

GET /search?q=land+cover\\  
\&include_filters\[geo\]\[type\]=polygon\\  
\&include_filters\[geo\]\[field\]=locn_geometry\\  
\&include_filters\[geo\]\[points\]\[0\]\[lat\]=44.9\\  
\&include_filters\[geo\]\[points\]\[0\]\[lon\]=-93.4\\  
\&include_filters\[geo\]\[points\]\[1\]\[lat\]=45.2\\  
\&include_filters\[geo\]\[points\]\[1\]\[lon\]=-93.2\\  
\&include_filters\[geo\]\[points\]\[2\]\[lat\]=45.0\\  
\&include_filters\[geo\]\[points\]\[2\]\[lon\]=-92.8

(Add more `points[n]` pairs for polygons with \>3 vertices.)

POST

```json
{
  "q": "land cover",
  "filters": {
    "geo": {
      "type": "polygon",
      "field": "locn_geometry",
      "points": [
        { "lat": 44.9, "lon": -93.4 },
        { "lat": 45.2, "lon": -93.2 },
        { "lat": 45.0, "lon": -92.8 }
      ]
    }
  }
}
```

### Shape (`shape` \+ relation)

Relation options:

* intersects  
* disjoint  
* within  
* contains

GET /search?q=land+cover\\  
\&include_filters\[geo\]\[type\]=shape\\  
\&include_filters\[geo\]\[field\]=locn_geometry\\  
\&include_filters\[geo\]\[relation\]=within\\  
\&include_filters\[geo\]\[shape\]\[type\]=envelope\\  
\&include_filters\[geo\]\[shape\]\[coordinates\]\[0\]\[0\]=-94\\  
\&include_filters\[geo\]\[shape\]\[coordinates\]\[0\]\[1\]=46\\  
\&include_filters\[geo\]\[shape\]\[coordinates\]\[1\]\[0\]=-92\\  
\&include_filters\[geo\]\[shape\]\[coordinates\]\[1\]\[1\]=44

(Here the shape is a GeoJSON-style envelope; any GeoJSON geometry works.)

POST

```json
{
  "q": "land cover",
  "filters": {
    "geo": {
      "type": "shape",
      "field": "locn_geometry",
      "relation": "within",
      "shape": {
        "type": "envelope",
        "coordinates": [[-94, 46], [-92, 44]]
      }
    }
  }
}
```

## Model Context Protocol

Endpoint for MCP service information and connection details.

### GET /mcp

| Method | Path | Description |
| :---- | :---- | :---- |
| GET | `/mcp` | MCP service information and connection details. |

## Validation Endpoint

**TODO** — How can this validate CSVs via Table Schema

This endpoint allows clients to POST a single metadata record (as a JSON object) and receive a validation report indicating whether it conforms to the OpenGeoMetadata Aardvark schema.

| Method | Path | Description |
| :---- | ----- | ----- |
| POST | /validate | Validate a single Aardvark JSON record |

### Request Body

```json
{
  "data": {
    "type": "resource",
    "attributes": {
      "id": "stanford-abc123",
      "dct_title_s": "Sample Map",
      "gbl_resourceClass_sm": ["Maps"],
      "dct_accessRights_s": "Public",
      "gbl_mdVersion_s": "Aardvark",
      "gbl_mdModified_dt": "2025-07-20T18:43:00Z"
      // ... other fields ...
    }
  }
}
```

* The body MUST be a single JSON object using type: "resource" and an attributes map.  
* The record MUST be structured according to the Aardvark profile defined at: [https://opengeometadata.org/schema/geoblacklight-schema-aardvark.json](https://opengeometadata.org/schema/geoblacklight-schema-aardvark.json)

### Response

If the record is valid:

```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "profile": [
    "https://opengeometadata.org/profile/aardvark",
    "https://opengeometadata.org/profile/mcp/validate"
  ]
}
```

}

If the record is invalid:

```json
{
  "valid": false,
  "errors": [
    {
      "field": "dct_title_s",
      "message": "This field is required and must be a string."
    },
    {
      "field": "gbl_mdVersion_s",
      "message": "Value must be 'Aardvark'."
    }
  ],
  "warnings": [],
  "profile": [
    "https://opengeometadata.org/profile/aardvark",
    "https://opengeometadata.org/profile/mcp/validate"
  ]
}
```

### Notes

* This endpoint is non-mutating — it does not store or alter the record.  
* It is useful for QA tools, CI pipelines, and metadata editors.  
* The server SHOULD use a strict JSON Schema validator and MAY support additional lint rules or MCP profiles.

## TODOs

* Support JSON POSTS in API