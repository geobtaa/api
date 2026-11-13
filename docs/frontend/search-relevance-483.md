# Search relevance regression: issue #483

Public catalog observations captured on 2026-11-13:

- `Minneapolis streetcar` returned 14 records, all classified as Maps.
- Adding `Maps` returned zero; singular `Map` returned ten.
- `Bituminous coal mine maps of Pennsylvania` returned 236 records with collection
  `08d-03` first. The historical report of seven results is not today's baseline.
- The collection relationships endpoint listed 1,162 `dct:hasPart` records.
  Twenty-five have titles beginning `Pittsburgh-`, covering quadrangles 1–9 and
  multiple base/seam variants. These are catalog records, not merely external
  index-map features. The complete Pittsburgh ID/title inventory is checked into
  `backend/tests/fixtures/collection_search_483.json`.
- Representative Pittsburgh-08 and Pittsburgh-09 records have stored bounding
  boxes and point to `08d-03` through `dct_isPartOf_sm`. Tests use their real extents
  for Within and Overlap behavior. Metadata retrieval for other representatives
  was unavailable during this snapshot; their extents have not been inferred.

V2 indexes direct collection titles onto member records. The original collection
has a broad Pennsylvania extent; a small Within filter can legitimately exclude
it while admitting individual sheets. Keyword search and external index-map
browsing are distinct entry points.

Full-catalog validation on 2026-11-13 also found a strict match for
`Maps of Minneapolis that show streetcar routes`: `msn-id-2250`, the 1940
Aquatennial map. Its description explicitly mentions streetcar and bus routes.
The zero-only fallback rule therefore keeps this query in `all_terms` mode;
it does not broaden a successful strict search just to increase its result count.
The isolated fixture tests both situations: the original 14 records with no
strict hit, and this additional real record preventing fallback. Excluding the
strict hit through a logical filter exercises partial matching on the full
catalog. Spatial validation must inspect all pages: a sheet beyond the first
page of Overlap results is still a match.

The popup formatting reported in #483 remains a separate UI issue. This work does
not assert that every external index-map feature has a corresponding catalog
record, or that Heather's original viewport and filters have been reproduced.
See [backend search documentation](../backend/search.md#catalog-relevance-v2).
