# OGC API - Records Compatibility Facade

The read-only facade at `/api/v1/ogc/*` adapts the existing `SearchService` to
GeoJSON. It is a **partial implementation**, not a declaration of full OGC API
Records conformance. `/conformance` returns an empty `conformsTo` array until the
remaining requirements have been implemented and verified.

## Endpoints

- `/` provides discovery links, including the API definition and documentation.
- `/conformance` declares verified conformance classes (currently none).
- `/collections` and `/collections/btaa-records` describe the catalog.
- `/collections/btaa-records/items` searches records.
- `/collections/btaa-records/items/{recordId}` retrieves one record.
- `/collections/btaa-records/queryables` returns an empty property schema because
  property filtering is not supported.
- `/collections/btaa-records/sortables` lists the supported sort properties.

Item responses use `application/geo+json`; queryables and sortables use
`application/schema+json`. Other discovery responses use `application/json`.

## Supported search parameters

- `q`: keyword search through the existing native search engine.
- `limit`: number of results per page, from 1 to 100 (default 10).
- `page`: page number, starting at 1.
- `sortby`: one of `title`, `+title`, `-title`, `relevance`, or `-relevance`.
  Missing sorting uses the native default. Relevance is always descending.
  Encode a literal plus sign as `%2B` in a URL.
- `bbox`: four finite CRS84 coordinates, `west,south,east,north`, within
  longitude `[-180,180]` and latitude `[-90,90]`. It selects intersecting indexed
  `dcat_bbox` extents, not only records whose centroids lie inside the box.
  West greater than east crosses the antimeridian. Zero-area boxes, reversed
  latitude bounds, and 3D boxes are unsupported and return HTTP 400.

Spatial intersection does not apply the native map search's minimum-overlap
threshold. Records without an indexed extent do not match a bbox query. This
limitation is one reason the facade does not claim searchable-catalog
conformance.

Unsupported and repeated query parameters return HTTP 400 instead of silently
changing or ignoring the query. In particular, `datetime`, `ids`, CQL filters,
CRS selection, multiple sort keys, `modified` sorting, and `dateAccessioned`
sorting are not implemented. Invalid `limit` or `page` values use FastAPI's
normal validation response (HTTP 422).

## Response projection

The projector supports both forms returned by `SearchService`: flat hydrated
search attributes and native resource attributes nested under `ogm` and `b1g`.
Optional null arrays and empty descriptions are normalized so sparse metadata
does not fail response validation.

- `numberMatched` comes from `meta.pages.total_count`.
- `numberReturned` is the number of emitted features.
- `timeStamp` is an RFC 3339 UTC response-generation timestamp, not query duration.
- Next and previous links preserve decoded query values without double encoding.
- Geometry reuses the parsed viewer geometry already provided by the service,
  including its bounding-box fallback. Missing or unusable geometry remains
  `null`; the projector performs no additional lookup or geometry parsing.
- Record links encode identifiers as path segments and use a single `/api/v1`
  prefix. The configured `APPLICATION_URL` supplies the public scheme and host,
  avoiding internal HTTP origins behind a reverse proxy. If it is unset, the
  request origin is used; deployments must configure their public URL correctly.

## Property mappings

- `id`: resource ID, with `layer_slug_s` fallback where available.
- `title`: `dct_title_s`.
- `description`: first available `dct_description_sm` value.
- `resourceClass` / `resourceType`: `gbl_resourceClass_sm` / `gbl_resourceType_sm`.
- `provider`: `schema_provider_s`.
- `spatial` / `subject`: `dct_spatial_sm` / `dct_subject_sm`.
- `accessRights`: `dct_accessRights_s`.
- `modified`: `gbl_mdModified_dt`.
- `dateAccessioned`: `b1g_dateAccessioned_s`.
- `publicationState`: `b1g_publication_state_s`.
- `accrualMethod`: `b1g_dct_accrualMethod_s`.

These exposed properties do not imply that they are supported search or sort
parameters. Additional Records core properties, temporal and identifier filters,
full sorting semantics, and standards conformance testing remain future work.

## Regression checks

The OGC tests cover realistic SearchService pagination, the actual native
resource presenter shape, sparse metadata, geometry, URL encoding, public
origins, media types, parameter rejection, and generated Elasticsearch spatial
queries (including antimeridian crossings and overlap-threshold avoidance).
Run the repository's normal backend checks with local services available.
For an isolated focused run that does not start database fixtures:

```bash
cd backend
python -m pytest --noconftest -o addopts='' \
  tests/services/test_ogc_projector.py tests/api/test_ogc_query_validation.py
```

The focused run does not replace the full application suite or live
Elasticsearch/PostgreSQL integration tests.
