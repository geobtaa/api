# Shared preview assets (experimental)

The preview pipeline prepares content once for an interactive OGM Viewer layer and a
512-pixel thumbnail. Location maps are separate products with explicit coverage
provenance. The feature is disabled by default and is not a replacement download
service. Harvested records, curated images, and original downloads remain authoritative.

Tabular CSV, TSV, and Parquet sources also support a searchable table through
[Parquet derivatives and DuckDB WASM](shared_preview_tables.md). Table rows are
searched within the opened dataset; collection-wide search remains unchanged.

## Local workflow

Start from the OGM Viewer integration branch. Install the backend dependencies and
GDAL **3.11.0** and Tippecanoe **2.79.0**, or build `Dockerfile.preview`. Tool versions
are checked before conversion. Initialize the local database with
`make preview-assets-init`. Set `PREVIEW_ASSETS_ENABLED=true` in the local environment,
and set `PREVIEW_APPROVED_RESOURCE_IDS=record-id` for records that have passed
technical and visual review. Then run `make preview-assets-prepare IDS="record-id"`.
The comma-separated allowlist defaults to empty and does not support wildcards.
Removing a record immediately disables its prepared presentation and asset routes.
The collection maintainer confirms that inclusion in the BTAA Geoportal establishes
reuse eligibility for preview derivatives. Preparation and delivery still require
an explicitly public, published, unsuppressed record. The allowlist stages technical
rollout; it does not require a separate license approval for each catalog record.
Jobs use the `previews` queue;
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
`--child-records children.json` supplies public child-record snapshots for a database-free
index audit. The resolver still follows only one child-record hop and detects cycles.

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

Native COG and vector PMTiles inspection uses bounded HTTP Range reads with a small
block cache. Every redirect is checked, connections are pinned to public addresses,
and a strong ETag must remain stable across reads. Sources without usable ranges or
validators fall back to the normal bounded download path. COG thumbnails use source
overviews; PMTiles thumbnails decode a bounded complete overview level. Native PMTiles
layers retain their names through the optional `source_layer` field. No source archive
is re-encoded merely to make its thumbnail.

TIFF conversion uses lossless LZW compression, 512-pixel blocks, and internal overviews.
Numeric values and masks are checked against the input. Classified rasters require a
known palette and use nearest-neighbor overviews. RGB band meaning must be explicit in
the source or recipe. Ambiguous unsigned single-band data requires review. Scalar
ranges and palette entries are recorded and shared with the viewer. Downsampling only
occurs with an explicit `max_dimension` recipe; the default preserves source resolution.

Vectors use a WGS84 FlatGeobuf intermediate and one vector PMTiles file per spatial
layer. Original attributes are retained; tile geometry can be repaired, generalized,
and omitted in dense tiles. Generated IDs are stable within the derivative version.
Source driver feature IDs are retained as text in `__preview_source_fid` before
intermediate sorting; underscores are appended if that attribute name already exists.
This also preserves large integer identifiers exactly in browser inspection. The
manifest records the actual attribute name per layer and distinguishes source IDs
from generated tile IDs. Null geometry and unsupported layers can result
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
Embedded IIIF v2/v3 painting images can supply thumbnails. A multi-canvas manifest is
labeled as a sample; image choices, composite canvases, or externally referenced page
graphs require review instead of guessing the painting image.

Coverage includes GeoJSON geometry, `kind`, `label`, and provenance. Kinds are
`data-footprint`, `indexed-coverage`, `metadata-extent`, `geographic-focus`, and
`unavailable`. Raster grid bounds may contain NoData areas; vector extents may contain
gaps. These qualifications are recorded rather than implying an exact occupied area.
Unknown geography is represented by null geometry. Search indexing is unchanged.
Display simplification is performed once before publication, with its tolerance and
source geometry fingerprint recorded. Static maps and UI overlays use that same
published geometry.

Point datasets use regional envelopes of actual point groups, preserving disconnected
and antimeridian groups. The coverage label explicitly identifies extents that can
contain gaps. An explicit vector `thumbnail_bounds` recipe supplies representative
detail framing for both the thumbnail and initial viewer camera without changing
published layer bounds or coverage. `thumbnail_scope=sample` and an embedded caption
identify that detail even for clients using only the legacy thumbnail URL.

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
Transient download failures use bounded exponential retries; missing sources and
access restrictions are not retried automatically. Failed refreshes retain the last
valid version only while its source assignment and access remain valid.

## Release validation

Do not enable collection-wide processing from metadata counts or historical cache
status. Retain the fixed pilot inputs, per-record source/outcome/timing/byte metrics,
actual thumbnail and coverage images, and independent browser and visual reviews.
Browser acceptance must verify partial reads, pan/zoom, placement, feature inspection
where available, and default styling. A ready conversion is not itself browser acceptance.

The companion `feature/shared-preview-recipes` viewer changes are published as
`v1.7.0-btaa.5`; the frontend pins that release archive and integrity hash. Future
updates must publish and validate a versioned viewer artifact before updating the
application pin. Package publication does not enable collection-wide preparation.

`make preview-assets-status` summarizes the latest stored outcomes by provider and
format, processing time, bytes read, derivative size, and active manifests older than
30 days. `scripts/preview_assets_status.py --report path/to/report.json` summarizes an
isolated audit instead. These are latest-attempt snapshots, not historical totals.
Asset delivery emits `preview_asset_delivery` JSON log events with resource ID, format,
HTTP status, emitted bytes, elapsed time, and completion state. They contain no source
URL queries or dataset attributes. Use these events to measure serving volume and
interrupted responses; provider failures remain in manifest source-attempt metrics.

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

Release gates must be checked against actual rendered outputs and browser acceptance,
including when an adapter or rendering recipe changes. Native PMTiles
inspection currently supports MVT archives with gzip directories and gzip or
uncompressed tiles. Other native encodings keep their existing viewer behavior but
require an additional preparation adapter. Complex IIIF presentation structures
require review. Numeric pixel inspection is not supplied by this viewer integration.

Very broad vector extents can produce an unhelpful default view. Review these thumbnails
and retain working curated images until a documented framing recipe is available.
Raster grid bounds and vector layer extents are qualified coverage, not automatically
computed occupied-pixel or feature-union footprints. Invalid index polygons are omitted
with an explicit incomplete-coverage label and review note.

The BTAA collection reuse policy above governs these derivatives. Catalog publication,
access restrictions, suppression, source changes, and removal from the rollout allowlist
are checked independently; a stale prepared asset does not override those checks.

Custom GeoTIFF projections measured in feet use their recorded linear units for
projection offsets in the viewer. This preserves source georeferencing; it does
not stretch a raster to a catalog extent. Raster units remain unspecified when
neither the source nor an explicit recipe provides them.

## Hosted IIIF level 0 derivatives

IIIF image services and Presentation 2/3 manifests can now be prepared as owned,
static Image API 2 level 0 derivatives. Ready previews override IIIF references
only in the runtime OGM Viewer record; harvested metadata and original downloads
remain unchanged. No viewer package update is required for ImageService2.

The worker downloads the full public painting image, verifies the declared pixel
dimensions, and produces optimized progressive JPEG quality-82 tiles (512 pixels, power-of-two scale
factors), advertised whole-image sizes, a full-image JPEG and `info.json`.
Full images reuse a smaller source JPEG when available. Chroma remains 4:4:4 to
protect fine colored map labels. Dimensions and ICC profiles are retained; JPEG is a lossy preview representation,
not a preservation master. Temporary provider downloads are not archived.

For manifests, every supported embedded canvas is prepared in order. Labels,
canvas identifiers, ranges, rights and attribution remain in the manifest snapshot;
painting image/service URLs are replaced, and upstream thumbnail references on
images/canvases/the manifest are removed. Other descriptive links and external
annotation/search services are not mirrored. Manifests with composition, choices,
selectors, authentication or nonembedded painting pages require review. A failed
manifest does not silently fall back to its first image reference.

Limits extend the existing byte, memory and execution budgets:

| Environment setting | Default |
| --- | --- |
| `PREVIEW_IIIF_JPEG_QUALITY` | 82 (configurable 60–95) |
| `PREVIEW_IIIF_CANVASES` | 32 per manifest |
| `PREVIEW_IIIF_PIXELS` | 80,000,000 per image |
| `PREVIEW_IIIF_FILES` | 10,000 output paths per resource |

Oversized sources receive `over-limit`; inconsistent dimensions, unknown color
conversion, nonstandard orientation or unsupported painting structure receive a
reviewable outcome. Providers that cannot supply the full image may be unavailable;
this implementation does not reconstruct originals by scraping provider tiles.

All files are generated and decoded for validation before upload; the published
manifest becomes active only after the job succeeds. Failed refreshes retain the
last valid manifest. Publication/access checks apply to every nested image request,
including `info.json`, JSON manifests, full images, sizes and tiles; unknown paths
return 404 and no dynamic transforms are generated. CORS and HEAD/Range behavior
use the existing asset route. Source withdrawal disables the bundle through the
same resource gate. An interrupted upload can leave unreferenced immutable objects;
retention/garbage collection must respect active manifests and `iiif_assets` values.

`meta.ui.preview.iiif_assets` maps exact bundle-relative request paths to immutable
content-addressed object keys; the new `iiif-manifest` layer format points to the
hosted manifest. Static paths currently resolve through the API, including with
S3-compatible storage. Direct CDN/object serving requires exporting this mapping
or an equivalent edge resolver, plus withdrawal/purge enforcement; uploading hashed
objects alone does not create an independently routable static directory tree.

Metrics include canvas count, logical output-file count and IIIF bytes. Physical
storage can be smaller through identical-file deduplication. Budget by unique
images/canvases, measured pyramid bytes and retained versions, not catalog rows
alone. Include per-tile PUT/GET operations; one manifest is not one stored object.


Display PNGs (thumbnails and coverage maps) are compressed and tested with 64,
128 and 256-color palettes. The smallest candidate is retained only if alpha is
unchanged and RGB error stays within 3/255 RMS and 48/255 maximum. Otherwise the
optimized truecolor PNG is retained. This is not applied to COG pixel values,
class identifiers or PMTiles attributes. IIIF JPEG quantization uses the versioned
quality setting above; dimensions are not reduced. Full images and tile aliases
share content-addressed storage when their bytes match. This optimizes storage
subject to readable content, rather than claiming a universally smallest encoding.

High-entropy thumbnails that still exceed 512 KB are reduced in display dimensions
(within the existing 512-pixel maximum), rather than accepting arbitrary color error.
