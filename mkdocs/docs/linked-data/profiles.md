# Response profiles

The URIs in `jsonapi.profile` describe how this API uses its JSON:API-style
resource envelope. They are neither JSON-LD contexts nor JSON Schemas. Their
machine-readable descriptions are JSON-LD documents using the W3C Profiles
Vocabulary, with identities matching their published URLs.

- [Resource metadata profile](https://gin.btaa.org/api/v1/ld/profiles/ogm-b1g.profile.jsonld)
- [UI hints profile](https://gin.btaa.org/api/v1/ld/profiles/ogm-ui.profile.jsonld)

## Resource metadata profile, version 2

Each resource has a local `id` and `type: resource`. `attributes.ogm` holds raw
Aardvark metadata and `attributes.b1g` holds local extensions. Fields can be
absent in sparse or lightweight results. This profile does not assert that all
search results meet the full ingest JSON Schema.

`meta.jsonld` is the normalized, standalone linked-data document. Extract it
before processing. It is also available from
`/api/v1/resources/{id}/citation/json-ld` with `application/ld+json`. Search
responses remain `application/json`, including when a JSON-LD Accept header is
sent. The envelope itself is not RDF.

The projection provides:

- Absolute resource identities, URL and license references, and collection and
  version relationships. Local relationship IDs resolve to canonical resource
  pages; existing absolute IRIs are retained. Malformed URL-like values are omitted from the graph
  instead of being turned into invented local identifiers.
- Schema.org `Dataset`, `Map`, `Collection` or `CreativeWork`, based on the
  Aardvark resource class. A `Point data` resource type does not hide its dataset
  class. Web services alone do not establish a Dataset type.
- Multiple names, descriptions, keywords, creators, publishers, languages and
  licenses without presentation-driven truncation. Creator and publisher names
  do not imply a person or organization type. Providers remain separate.
- Geographic labels as Places and valid bounding boxes as GeoShapes in
  south/west north/east order. It does not label raw ENVELOPE strings as WKT.
- Explicit download references as `DataDownload` distributions for datasets or
  `MediaObject` encodings for other creative works. Thumbnails, landing pages,
  PMTiles and IIIF or OGC service references are not inferred to be downloads.
  Resource-level format strings are not assigned to individual files.
- Access conditions as `conditionsOfAccess`, not the accessibility property
  `accessMode`. Valid full publication dates use `datePublished`; free-text or
  imprecise values use Dublin Core `issued`. Calendar dates are normalized and
  exported as `xsd:date` literals. Both source provenance fields are preserved.

The inline context requires no remote document retrieval. The projection is
curated discovery metadata, not a lossless RDF conversion of every source field
or a claim of DCAT application-profile conformance. Full source geometry,
reference maps and local extensions remain available in the source attributes.

## UI hints profile, version 2

`meta.ui` contains optional presentation hints, including thumbnail URLs,
formatted citations, downloads, links and viewer configuration. It is ordinary
JSON. A viewer endpoint does not by itself establish a downloadable dataset.
Scores, facets, pagination and other UI data are also outside `meta.jsonld`.

## Migration

The former `meta.@context` and `meta.@type` markers have been removed. Use
`meta.jsonld`. The earlier context had the wrong URL and scope, and its record
type was undefined. Profiles are no longer presented as context files or
linked to nonexistent external validation artifacts.

Citation exports now use the same inline context and graph builder. Publishers
and licenses are arrays of nodes; keywords are separate values; multilingual
and multi-description records can have arrays. Clients must not assume that
all values are scalar. `meta=false` intentionally omits JSON-LD with the other
resource metadata. Version 2 describes this changed semantic contract; releases
must coordinate migration for consumers of the previous markers and shapes.

## Standards

- [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/)
- [JSON:API profiles](https://jsonapi.org/format/1.1/#profiles)
- [Profiles Vocabulary](https://www.w3.org/TR/dx-prof/)
- [Schema.org](https://schema.org/)
