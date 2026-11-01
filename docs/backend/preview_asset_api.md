# Preview assets for API clients

Resource detail, search-result, and homepage resource objects expose prepared
assets in `meta.assets` when preview publication is enabled and the resource is
approved and public. This is an additive JSON:API resource-level `meta` field;
original download references and `meta.ui` fields remain unchanged.

The catalog describes published outputs, not the processing queue. An absent
catalog means no prepared-asset contract is available; an empty `items` array
means no published assets are currently available. Neither proves that original
data is missing. Clients need not interpret UI state or storage paths.

## Example catalog

```json
{
  "version": "1",
  "items": [
    {
      "id": "layer:terrain",
      "layer_id": "terrain",
      "name": "Elevation",
      "roles": ["visualization"],
      "format": "cog",
      "media_type": "image/tiff",
      "url": "https://api.example.org/api/v1/resources/example/preview-assets/derivative.tif",
      "scope": "resource",
      "bounds": [-94, 44, -93, 45],
      "byte_size": 10485760,
      "recipe": {
        "kind": "scalar",
        "bands": [1],
        "value_range": [200, 450],
        "ramp": "viridis",
        "nodata": -9999,
        "units": "meters"
      }
    }
  ],
  "coverage": {
    "geometry": null,
    "kind": "unavailable",
    "label": "Location unavailable",
    "provenance": "No verified collection coverage"
  },
  "provenance": {
    "processing_version": "4",
    "transformations": []
  }
}
```

The URL above is a placeholder. Always use returned URLs verbatim. Hosted files
use immutable content-addressed keys; IIIF URLs resolve a published bundle.
Re-fetch the resource to discover refreshed versions. Withdrawal can make a
previously returned URL return 404; these URLs do not bypass access checks.

## Rendering contract

| `format` | How to use `url` | Additional fields |
| --- | --- | --- |
| `cog` | Open with a Range-capable GeoTIFF renderer | One-based `recipe.bands`, value range, NoData, palette/ramp, units |
| `pmtiles` | Open with a PMTiles-compatible vector renderer | `source_layer` and vector styling in `recipe` |
| `geojson` | Fetch GeoJSON and render features | `recipe`, when supplied |
| `iiif` | Load the Image API description with a IIIF client | Follow advertised tiles/sizes; hosted derivatives are level 0 |
| `iiif-manifest` | Load the Presentation manifest with a IIIF viewer | Follow canvases and their image services |
| `parquet` | Register the URL with DuckDB WASM or another Parquet reader | `columns` contains names/types; `row_count` is the prepared table count |
| `wms` | Configure a WMS client with the service URL | Use `source_layer`; respect negotiated version/CRS axis ordering |
| `arcgis` | Configure an ArcGIS service client | Source renderer applies unless a recipe is supplied |
| `image` | Display as an image | Thumbnail/sample scope applies |

`bounds` are `[west, south, east, north]` in longitude/latitude. Honor the file's
georeferencing rather than assuming that raster pixels use that CRS. A crossing
extent can have west greater than east. `recipe.thumbnail_bounds` is representative
framing, not collection coverage. Missing/null fields are unknown or inapplicable.
`byte_size` is omitted when unknown. `media_type` is omitted for service endpoints
and external images whose response type is unknown. Choose renderers by `format`,
not URL suffixes.

`roles` identifies `visualization`, `table`, `thumbnail`, or `coverage-map`.
Layer identifiers are namespaced as `layer:<id>`; `layer_id` retains the original
identifier. Multi-layer datasets expose separate items. `scope: "sample"` means
representative content. Never substitute a sample's bounds for resource coverage.

`coverage` contains GeoJSON display geometry, provenance, and a label distinguishing
`data-footprint`, `indexed-coverage`, `metadata-extent`, `geographic-focus`, or
`unavailable`. A `coverage-map` image, when present, uses this geometry. Unknown
coverage has no geographic image. Preserve disconnected regions and holes.

`provenance` includes available source URL/fingerprint, processing version,
generation time, and documented transformations. Internal keys, tile registries,
job logs, and review images are excluded. A `thumbnail` item describes a generated
PNG derivative; `meta.ui.thumbnail_url` remains the preferred presentation image
and can retain a curated image instead. A `coverage-map` item is also a PNG.

## Minimal client discovery

```javascript
const response = await fetch(resourceUrl);
if (!response.ok) throw new Error(`Resource unavailable: ${response.status}`);
const { data: resource } = await response.json();
const catalog = resource.meta?.assets;
if (catalog?.version === '1') {
  const thumbnail = catalog.items.find(a => a.roles.includes('thumbnail'));
  if (thumbnail) document.querySelector('img').src = thumbnail.url;
  const tables = catalog.items.filter(a => a.format === 'parquet');
  // Register tables[i].url with your Parquet reader. Use columns for the UI.
  // Dispatch other items to your renderer by format and apply their recipe.
}
```

Search results have the same catalog on each `data[]` resource. Ignore unknown
additive fields and unsupported formats, and check `version`.

Hosted assets support GET, HEAD, byte Range requests, and browser CORS. Read large
COG, PMTiles, and Parquet files partially. External live-service endpoints retain
their provider's transport/CORS behavior. IIIF level 0 supports advertised static
requests, not arbitrary transformations. Row search is within the opened Parquet
dataset; it does not add rows to collection-wide search.
