# JSON-LD contexts and discovery

The public JSON API keeps source metadata in `attributes` without embedding a
second representation. Follow a resource's `links.alternate.href` to retrieve
its JSON-LD 1.1 document. The link advertises `type: application/ld+json` and its
origin-relative URL resolves against the API response URL. The dedicated
`/api/v1/resources/{id}/citation/json-ld` endpoint supplies an inline context
and absolute `@id`, so RDF processing needs no remote context files.

```python
from urllib.parse import urljoin

import requests
from pyld import jsonld

response = requests.get("http://localhost:8000/api/v1/search?per_page=2", timeout=30)
response.raise_for_status()
graphs = []
for resource in response.json()["data"]:
    url = urljoin(response.url, resource["links"]["alternate"]["href"])
    document = requests.get(url, headers={"Accept": "application/ld+json"}, timeout=30)
    document.raise_for_status()
    graphs.append(document.json())
triples = jsonld.to_rdf(graphs, {"format": "application/n-quads"})
```

The extra request per resource is needed only by linked-data consumers.
Ordinary clients use the source attributes without receiving duplicate values.

The inline context defaults to `https://schema.org/`. `url` and `contentUrl`
are IRI-valued properties. Licenses and resource relationships use explicit
`@id` objects. Dublin Core and PCDM predicates use full IRIs. No arbitrary
resource label is interpreted as an external vocabulary term.

Nodes without `@id` are RDF blank nodes. Agent names are labels, not stable
identities, and matching names do not establish that two agents are the same.
The batch example lets the processor allocate distinct blank-node labels.
For separately converted responses, use an RDF merge that standardizes blank
nodes apart; concatenating N-Quads may accidentally merge unrelated nodes whose
generated labels overlap. See [RDF blank nodes](https://www.w3.org/TR/rdf11-concepts/#section-blank-nodes).

Arrays represent unordered RDF values, not ordered RDF lists. They do not assert
author order or download preference. Missing properties are unasserted, not
negative statements about a resource.

`attributes.ogm` and `attributes.b1g` preserve source metadata. `meta.ui`, scores,
facets and timelines are ordinary JSON and are not members of the graph.
`meta=false` removes the resource's UI metadata but retains the alternate link.

## Legacy draft contexts

The files under `v1/ld/contexts/` are retained as legacy draft artifacts for
existing integrations. They are **not** used by the standalone graph and
must not be applied to the whole JSON API response. They do not transform the
nested envelope, resolve local relationship identifiers, normalize ENVELOPE or
comma-separated bounds to WKT, or parse JSON-encoded reference strings.
Consumers needing RDF should use the dedicated JSON-LD endpoint.

The previous `meta.@context` URL returned 404, and a context inside `meta`
could not describe sibling `attributes` even with the URL corrected. Both that
marker and the undefined `meta.@type` marker have been removed. A typed
alternate link now makes the separate JSON-LD representation discoverable.

See [Profiles](profiles.md) for the response contract and migration details.
