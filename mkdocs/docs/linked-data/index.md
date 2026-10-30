# BTAA Geospatial Linked Data

The JSON API keeps source metadata in resource attributes and provides a typed
`links.alternate` link to `/api/v1/resources/{id}/citation/json-ld`. This dedicated
endpoint serves JSON-LD with `application/ld+json` when requested. Search and
resource envelopes remain ordinary JSON without an embedded duplicate graph.

Start with [JSON-LD discovery](contexts.md) for processor examples and
[response profiles](profiles.md) for field semantics and migration details.

## Available documentation

- [Contexts and discovery](contexts.md): inline context, graph boundaries and
  the status of the legacy raw-field context drafts.
- [Response profiles](profiles.md): source metadata, normalized graph and UI
  hints; these profiles do not guarantee full ingest-schema conformance.
- [Schemas](schemas.md): validation of source metadata. A JSON Schema is not a
  JSON-LD context or an RDF vocabulary.
- [Ontologies](ontologies.md) and [vocabularies](vocabularies.md): separate draft
  vocabulary artifacts. They are not imported by the API's normalized graph.

The graph uses Schema.org, Dublin Core and PCDM terms. It preserves source
values where their meaning is supported and avoids inferring agent types,
download formats or vocabulary identifiers from labels. Full Aardvark metadata
remains available in `attributes.ogm`, with local extensions in `attributes.b1g`.
