# Shared preview assets (experimental)

The preview pipeline prepares content once for an interactive OGM Viewer layer and a
512-pixel thumbnail. Location maps are separate products with explicit coverage
provenance. The feature is disabled by default and is not a replacement download
service. Harvested records, curated images, and original downloads remain authoritative.

## Local workflow

Start from the OGM Viewer integration branch. Install the backend dependencies and
GDAL **3.11.0** and Tippecanoe **2.79.0**, or build `Dockerfile.preview`. Tool versions
are checked before conversion. Initialize the local database with
`make preview-assets-init`. Set `PREVIEW_ASSETS_ENABLED=true` in the local environment,
then run `make preview-assets-prepare IDS="record-id"`. Jobs use the `previews` queue;
resource requests only read completed manifests. A worker consuming that queue is
required. The existing API worker must not perform conversions inline.

For an isolated audit without writing catalog manifests:

```sh
cd backend
uv run python scripts/prepare_preview_assets.py \
  --records tests/fixtures/preview_pilot.json --output data/preview-audit
```

This intentionally selected 40-record fixture includes 10 indexes, 10 services,
14 download-only datasets, and 6 controls. It is not a random sample or a basis for
estimating collection-wide success. The original screenshot-only USGS DEM index is
not included because its actual record metadata has not been available.

Run `make preview-assets-test` for isolated conversion and contract tests. These
exercise actual GDAL/Tippecanoe conversions without clearing application caches.
The dedicated CI worker builds with `INSTALL_TEST_DEPS=true` and requires the pinned
tools; general API tests skip conversion cases when that toolchain is absent.
`--recipe recipe.json` supplies an explicit rendering recipe; `--layer name` selects
a named spatial layer. An audit entry can override these with `recipe` and `layer`.
Without a selected layer, every supported spatial layer is exposed up to the limit.

Local file storage defaults to `data/preview-assets`; `PREVIEW_ASSET_ROOT` selects a
shared local directory. API and conversion workers must see the same files.
`APPLICATION_URL` determines public API asset URLs. Coverage rendering uses the
existing local native static-map renderer. A missing renderer produces an explicit
coverage-rendering failure rather than an unrelated map.

## Source and rendering behavior

Assigned assets and normalized distributions take precedence over legacy references
of the same type. Existing COG, PMTiles, IIIF, and live service references are preferred
before download conversion. The runtime adapter adds prepared layers without changing
harvested OGM references. Original working previews remain available.

TIFF conversion uses lossless LZW compression, 512-pixel blocks, and internal overviews.
Numeric values and masks are checked against the input. Classified rasters require a
known palette and use nearest-neighbor overviews. RGB band meaning must be explicit in
the source or recipe. Ambiguous unsigned single-band data requires review. Scalar
ranges and palette entries are recorded and shared with the viewer. Downsampling only
occurs with an explicit `max_dimension` recipe; the default preserves source resolution.

Vectors use a WGS84 FlatGeobuf intermediate and one vector PMTiles file per spatial
layer. Original attributes are retained; tile geometry can be repaired, generalized,
and omitted in dense tiles. Generated IDs are stable within the derivative version.
The manifest records these limitations. Null geometry and unsupported layers can result
in a reviewable failure; no alternative full-fidelity download is implied.

The approach is informed by the public
[geobtaa/curation recipes](https://github.com/geobtaa/curation), particularly
[build_pmtiles_from_gpkg.py](https://github.com/geobtaa/curation/blob/main/build_pmtiles_from_gpkg.py)
and [create_geotiff_cogs.py](https://github.com/geobtaa/curation/blob/main/scripts/create_geotiff_cogs.py).
Their generalization workflow and compatible lossless profile are useful defaults;
JPEG conversion and automatic RGB interpretation are not appropriate universal defaults
for scientific data. The inspected recipe revision is recorded in output provenance.

Index previews identify a representative member and keep collection coverage separate.
Selection is deterministic, with at most three candidates and one child-record hop.
In the database-free audit, child records must be available in the audit context;
otherwise a child-only reference cannot be resolved. WMS respects the referenced layer
and axis ordering. ArcGIS uses map/image export endpoints. Uniform images are flagged
for review independently of whether the live layer remains usable.

## API additions

`meta.ui.preview` and `meta.ui.coverage` are optional. Existing viewer fields and download
links are retained. A version-1 preview includes `status`, `layers`, `scope`, source
fingerprint, generation time, processing version, transformations, thumbnail status,
and metrics. Each layer includes its name, URL, format, geographic bounds, and recipe.
A scope of `sample` means the content does not represent the complete collection.

Coverage includes GeoJSON geometry, `kind`, `label`, and provenance. Kinds are
`data-footprint`, `indexed-coverage`, `metadata-extent`, `geographic-focus`, and
`unavailable`. Raster grid bounds may contain NoData areas; vector extents may contain
gaps. These qualifications are recorded rather than implying an exact occupied area.
Unknown geography is represented by null geometry. Search indexing is unchanged.

Asset routes support GET, HEAD, OPTIONS, HTTP Range, and browser CORS. Immutable keys
identify bytes, but every resource-scoped request checks current publication, access,
and source assignment. S3 storage is private and uses the same access-checked API
route. Removing or restricting a source invalidates the previously published assets.
Disabling the feature restores the original presentation paths.

The database stores the last attempt separately from the last valid manifest. A failed
refresh retains the previous valid preview when its source assignment is unchanged.
Curated and known successful thumbnail assets keep priority. Missing/failed thumbnails
can use a validated prepared image. Failed or low-variation thumbnails do not prevent a
valid interactive layer from being recorded as ready.

## Limits and outcomes

Initial per-job limits are 1 GiB downloaded, 4 GiB extracted, 10,000 archive entries,
eight layers, 15 minutes, 4 GiB memory, 10 GiB temporary storage, and 2 GiB derivative
output. `PREVIEW_<FIELD>` overrides the matching `Limits` field, for example
`PREVIEW_DOWNLOAD_BYTES` or `PREVIEW_SECONDS`. The production conversion runtime is
Linux; address-space limits are not asserted on macOS. Resource and provider leases
prevent duplicate resource jobs and simultaneous downloads from the same provider;
two conversion leases are available. Downloads are bounded and public-address checked,
including redirects. Archives reject traversal, links, duplicates, and nested archives.

Outcomes are `queued`, `processing`, `ready`, `unsupported`, `unavailable`, `invalid`,
`over-limit`, and `needs-review`. Inspect `detail` and `metrics.source_attempts` for
failure causes. Point clouds, nested archives, multidimensional scientific formats,
and unlocated images remain outside the first-release conversion scope.

## Release validation

Do not enable collection-wide processing from metadata counts or historical cache
status. Retain the fixed pilot inputs, per-record source/outcome/timing/byte metrics,
actual thumbnail and coverage images, and independent browser and visual reviews.
Browser acceptance must verify partial reads, pan/zoom, placement, feature inspection
where available, and default styling. A ready conversion is not itself browser acceptance.

The companion `feature/shared-preview-recipes` viewer changes are published as
`v1.7.0-btaa.3`; the frontend pins that release archive and integrity hash. Future
updates must publish and validate a versioned viewer artifact before updating the
application pin. Package publication does not enable collection-wide preparation.

Deployment-specific storage configuration, credentials, serving policies, and worker
operations belong in restricted operations documentation. This page deliberately
contains only the local workflow and public API contract.

While the pilot flag is enabled, resource/search presentation caches are bypassed and
prepared resource responses use `Cache-Control: no-store`. This avoids stale manifests
and ensures switching the feature off restores legacy cached presentation. It costs
additional database reads; a version-aware bulk cache strategy is an expansion gate.

For the optional local database test, set `PREVIEW_TEST_DATABASE_URL` to a localhost
PostgreSQL URL and run the isolated test target. The test creates a uniquely named
schema in a transaction and rolls back all test tables and rows.

TIFF companion files (world files and PAM `.aux.xml` metadata) are inspected inside
the validated extraction directory. Their CRS and band metadata are preserved in
the COG; missing sidecars are not replaced with guessed coordinates. Output CRS,
bounds, units, descriptions, and NoData are checked against the interpreted source.

`report_preview_assets.py` builds a self-contained HTML comparison and optional PDF
from an audit report, its asset directory, and captured current-asset evidence. PDF
output additionally requires ReportLab. Failed captures are visible state cards;
review-only thumbnail candidates are labeled and never served by the public asset
route. Verify the resulting images and rendered PDF pages before sharing the report.

To inspect actual audit derivatives through the application's `ResourceViewer`, run
`PYTHONPATH=backend python backend/scripts/serve_preview_audit.py data/preview-audit`
from the repository root (use the directory written by the audit). In `frontend/`, run
`PREVIEW_PILOT_SERVER=http://127.0.0.1:8878 npx vite --config browser-tests/vite.config.ts`
and open `http://127.0.0.1:4180/prepared.html`. This local-only harness uses the pinned
viewer package and runtime adapter. It does not enable catalog publication.

## Initial limitations

The experimental adapters do not yet establish every release gate. Native COG and
PMTiles inspection currently stages a bounded source download; large existing tiled
sources need a controlled partial-read inspection adapter before broader use. Existing
IIIF manifest previews are preserved, but the new preparation path does not yet resolve
all IIIF presentation manifests. Numeric pixel inspection is not supplied by this viewer
integration.

Very broad vector extents can produce an unhelpful default view. Review these thumbnails
and retain working curated images until a documented framing recipe is available.
Raster grid bounds and vector layer extents are qualified coverage, not automatically
computed occupied-pixel or feature-union footprints. Invalid index polygons are omitted
with an explicit incomplete-coverage label and review note.

Public access is checked automatically. It does not establish permission to create or
redistribute derivatives: apply the collection's reuse policy when approving the records
to queue. This release does not infer licenses or grant reuse rights from public access.
