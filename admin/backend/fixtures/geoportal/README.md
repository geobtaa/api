# Geoportal Resource fixtures

This snapshot preserves 111 JSON fixtures from the companion Geoportal repository.
All remain byte-for-byte copies except `btaa_documents/b1g_licensed_data.json`,
whose inherited URL session identifier was removed during the PR privacy audit.
The sanitized URL retains its resolver path and non-authentication query parameters.
`manifest.json` records the source commit, paths, SHA-256
checksums, original Resource IDs, and 14 selected starter records.

The source fixture tree was clean at capture. `btaa_documents` contains 58
BTAA examples; `gbl_documents` contains 53 GeoBlacklight examples. Their filenames
identify many intentional regression cases. Duplicate Resource IDs are retained
as separate scenarios, never silently merged. The starter collection chooses
unique IDs and covers maps, datasets, imagery, IIIF, ArcGIS, COG, PMTiles,
Unicode, licensed access, suppression, and parent/child relationships.

These are descriptive metadata snapshots, not canonical database seed rows or
frozen public JSON:API responses. Original IDs, references, legacy fields,
publication states, and incomplete metadata remain unchanged. Do not infer
Lifecycle membership from a provider or legacy code. External relationships may
point outside this sample. Linked services are not downloaded or assumed live.

The app's development fixture catalog previews the starter collection without
writing Resource, Distribution, or Lifecycle records. It does not publish data,
render embedded HTML, or call referenced remote services. Resource imports validate against the adopted contract, preserve field presence and unknown
references, and obtain an explicit Lifecycle association. The current create-only import
saves valid drafts after preview confirmation; 13 starter rows pass, while
`actual-papermap1.json` reports its string-valued year without coercion.

Run `make fixtures-check` to verify snapshot integrity and starter invariants.
Use the complete corpus in regression tests; use only manifest entries marked
`starter` for a default demo collection.
