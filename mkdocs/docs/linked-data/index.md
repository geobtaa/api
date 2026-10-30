# BTAA Geospatial Linked Data

The JSON API provides an independently extractable JSON-LD document in each
resource's `meta.jsonld`. For a single resource, the dedicated
`/api/v1/resources/{id}/citation/json-ld` endpoint serves that projection with
`application/ld+json`. The surrounding search envelope remains ordinary JSON.

Start with [JSON-LD extraction](contexts.md) for processor examples and
[response profiles](profiles.md) for field semantics and migration details.

## Available documentation

- [Contexts and extraction](contexts.md): inline context, graph boundaries and
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
