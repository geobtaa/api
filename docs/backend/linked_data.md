# Consuming linked data

Search and resource responses use an `application/json` envelope with
JSON:API-style `data`, `attributes`, `meta`, and `included` members. The envelope
is **not** a JSON-LD document. Each resource's `meta.jsonld` is a standalone
JSON-LD 1.1 document. Extract that object before expansion or RDF conversion.
UI hints, scores, facets, timelines and pagination are outside the RDF graph.
`meta=false` omits resource metadata, including JSON-LD.

```python
import requests
from pyld import jsonld

response = requests.get("http://localhost:8000/api/v1/search", timeout=30)
response.raise_for_status()
for resource in response.json()["data"]:
    graph = resource.get("meta", {}).get("jsonld")
    if graph:
        expanded = jsonld.expand(graph)
        nquads = jsonld.to_rdf(graph, {"format": "application/n-quads"})
```

For one resource, `GET /api/v1/resources/{id}/citation/json-ld` returns the same
projection as an independent `application/ld+json` document. The two paths share
one builder. Differences in source metadata available to lightweight response
profiles may produce fewer properties. Sending `Accept: application/ld+json`
to `/search` does not transform its envelope into a graph.

## Identity and context

The inline context uses Schema.org IRIs (`https://schema.org/`) and JSON-LD 1.1.
It requires no remote context fetch. Dublin Core and PCDM predicates appear as
absolute IRIs. Resource `@id` is its canonical resource-page URL, with the local
identifier encoded as one path segment. The ordinary `data.id` and
`attributes.ogm.id` remain local identifiers.

Local development uses `GEOPORTAL_BASE_URL` when set, otherwise
`APPLICATION_URL` with a trailing `/api/v1` removed. The embedded and standalone
projections use the same base. Configure these local settings consistently;
changing the base changes graph identities.

## Projection rules

| Source | RDF representation |
| --- | --- |
| `gbl_resourceClass_sm` | `schema:Dataset`, `schema:Map`, `schema:Collection`, or conservative `schema:CreativeWork`; legacy resource-type classification is used only when the class is absent |
| Titles, alternatives, descriptions, identifiers | Schema.org text properties; multiple values are preserved |
| Creators, publishers, provider | Separate named nodes; names do not establish whether an agent is a person or organization; a provider is not substituted for a publisher |
| Subjects and keywords | Separate keyword values, without truncation |
| Language and temporal coverage | Original text values, without invented language tags or dates |
| Issued date | ISO calendar dates use `schema:datePublished`; imprecise/free-text dates use `dct:issued` |
| License | Absolute IRIs become node references; textual licenses become creative-work nodes with `text` |
| Access rights | `schema:conditionsOfAccess`; never sensory-accessibility `schema:accessMode` |
| Spatial labels | `schema:Place` nodes |
| Valid `dcat_bbox`, or envelope fallback | `schema:GeoShape` box, ordered south/west north/east; invalid and antimeridian-crossing boxes are omitted |
| Collection/version/source relationships | Dublin Core or PCDM node references; local IDs resolve to resource-page IRIs and absolute IRIs are preserved |
| `dct_references_s` download entries | Only explicit `http://schema.org/downloadUrl` entries become downloads; strings, objects and arrays are supported |
| Other reference protocols | Preserved in source attributes; not mislabeled as downloadable files |

Downloads on datasets use `schema:distribution` / `schema:DataDownload`.
Other creative works use `schema:encoding` / `schema:MediaObject`. Catalog
membership is asserted only for datasets. The dataset-level format does not
prove the format of each individual file, so the projection does not assign
GeoPackage to ZIP archives, PMTiles, services, landing pages or IIIF manifests.
All explicit downloads are retained; there is no five-file limit.

This is a curated discovery projection, not a lossless RDF serialization of
every database or Aardvark field. Source metadata remains in `attributes.ogm`
and `attributes.b1g`, including raw geometries, reference protocols, local
administrative extensions and data dictionaries. The projection does not claim
DCAT application-profile or SHACL conformance.

## Migration from the earlier response

The former sibling `meta.@context` and `meta.@type` have been removed. They did
not apply a context to `attributes.ogm` or `attributes.b1g`; the context URL also
used an unavailable path, and `BtaaAardvarkRecord` lacked a term definition.
Read `meta.jsonld` instead. Its context and properties are in the same object.
The old raw-field contexts remain legacy draft artifacts, not the context of
the normalized graph. Do not apply those drafts to the entire API envelope.

Citation JSON-LD now uses the inline context and preserves arrays of authors,
publishers, languages, descriptions and licenses. Clients that assumed scalar
values must handle the documented arrays. This is a semantic contract change;
coordinate consumer migration as part of a release.

The profile URLs in `jsonapi.profile` identify descriptive JSON:API profiles.
Their JSON-LD descriptions use the W3C Profiles Vocabulary. A profile is not a
context or JSON Schema, and does not guarantee complete ingest-schema fields
in every search result. See the published linked-data profile documentation.

## Local verification

Install backend development dependencies, then run:

```bash
BTAA_SKIP_TEST_DB=1 backend/.venv/bin/python -m pytest \
  backend/tests/services/test_linked_data.py \
  backend/tests/services/test_citation_formats_service.py \
  backend/tests/api/v1/test_resource_presenter.py
make lint-check
```

Tests expand real serializer output with PyLD and assert RDF subjects,
predicates, object IRIs, geometry ordering and download semantics. The document
loader rejects remote fetches, keeping this check deterministic and offline.
