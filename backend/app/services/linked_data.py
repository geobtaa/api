"""Conservative, standalone JSON-LD projection of public Aardvark metadata.

The JSON API envelope and UI hints are not RDF. Only this extracted document
is a JSON-LD graph; source metadata remains available in attributes.ogm/b1g.
"""

from __future__ import annotations

import json
import math
import os
import re
from copy import deepcopy
from datetime import date
from urllib.parse import quote, urlsplit

from app.services.ogm_field_mapper import OGMFieldMapper

SCHEMA = "https://schema.org/"
DCT = "http://purl.org/dc/terms/"
PCDM = "http://pcdm.org/models#"

# Inline context: consumers can expand the graph without fetching a remote context.
CONTEXT = {
    "@version": 1.1,
    "@vocab": SCHEMA,
    "url": {"@id": SCHEMA + "url", "@type": "@id"},
    "contentUrl": {"@id": SCHEMA + "contentUrl", "@type": "@id"},
    "datePublished": {
        "@id": SCHEMA + "datePublished",
        "@type": "http://www.w3.org/2001/XMLSchema#date",
    },
}


def values(value):
    """Return nonempty strings without converting objects into fake labels."""
    items = value if isinstance(value, list) else [value]
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def is_absolute_iri(value):
    """Check generic IRI syntax and HTTP authority before asserting a node identity."""
    if not isinstance(value, str) or re.search(r'[\s\x00-\x1f\x7f<>"{}|\\^`\ud800-\udfff]', value):
        return False
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return False
    if re.search(r"%(?![0-9A-Fa-f]{2})", value) or value.count("#") > 1:
        return False
    try:
        parts = urlsplit(value)
        if parts.scheme in {"http", "https"}:
            # urlsplit alone accepts missing hosts and invalid ports.
            return bool(parts.hostname) and (parts.port is None or 0 <= parts.port <= 65535)
    except ValueError:
        return False
    return bool(parts.netloc or parts.path)


def _relationship_uri(value, base):
    if is_absolute_iri(value):
        return value
    # Do not turn malformed URLs or relative URL references into catalogue identities.
    if ":" in value or value.startswith(("/", "#", "?", "./", "../")):
        return None
    return resource_uri(value, base)


def geoportal_base_url():
    base = os.getenv("GEOPORTAL_BASE_URL") or os.getenv("APPLICATION_URL", "http://localhost:8000")
    return base.rstrip("/").removesuffix("/api/v1")


def resource_uri(resource_id, base_url):
    return f"{base_url.rstrip('/')}/resources/{quote(str(resource_id), safe='')}"


def _type(document):
    # Aardvark class carries Dataset/Map; resourceType normally says e.g. Point data.
    classes = values(document.get("gbl_resourceClass_sm")) or values(
        document.get("gbl_resourceType_sm")
    )
    classes = {value.lower() for value in classes}
    if classes & {"dataset", "datasets"}:
        return "Dataset"
    if classes & {"map", "maps"}:
        return "Map"
    if classes & {"collection", "collections"}:
        return "Collection"
    # Web services and imagery alone do not establish a Dataset or Map type.
    return "CreativeWork"


def _box(value):
    """Aardvark ENVELOPE or W,S,E,N -> Schema.org south/west north/east."""
    if not isinstance(value, str):
        return None
    try:
        envelope = re.fullmatch(r"\s*ENVELOPE\s*\(([^()]+)\)\s*", value, re.IGNORECASE)
        if envelope:
            west, east, north, south = map(float, envelope[1].split(","))
        else:
            west, south, east, north = map(float, value.split(","))
        if not all(math.isfinite(v) for v in (west, south, east, north)):
            return None
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            return None
        return " ".join(format(v, ".15g") for v in (south, west, north, east))
    except (TypeError, ValueError):
        return None


def _references(document, distribution_context):
    if distribution_context is not None and distribution_context.by_uri:
        return {
            uri: [{"url": record.url, "label": record.label} for record in records]
            for uri, records in distribution_context.by_uri.items()
        }
    refs = document.get("dct_references_s", {})
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except (ValueError, TypeError):
            return {}
    return refs if isinstance(refs, dict) else {}


def _links(value):
    for item in value if isinstance(value, list) else [value]:
        item = {"url": item} if isinstance(item, str) else item
        if (
            isinstance(item, dict)
            and is_absolute_iri(item.get("url"))
            and urlsplit(item["url"]).scheme in {"http", "https"}
        ):
            yield item


def resource_jsonld(document, resource_id, *, base_url=None, distribution_context=None):
    """Project supported metadata without inventing agents, formats or identities."""
    document = OGMFieldMapper.map_resource_fields(document)
    base = (base_url or geoportal_base_url()).rstrip("/").removesuffix("/api/v1")
    uri = resource_uri(resource_id, base)
    kind = _type(document)
    result = {"@context": deepcopy(CONTEXT), "@id": uri, "@type": kind, "url": uri}
    literal_fields = {
        "dct_title_s": "name",
        "dct_alternative_sm": "alternateName",
        "dct_description_sm": "description",
        "dct_identifier_sm": "identifier",
        "dct_language_sm": "inLanguage",
        "dct_temporal_sm": "temporalCoverage",
        "dct_accessRights_s": "conditionsOfAccess",
    }
    for field, term in literal_fields.items():
        items = values(document.get(field))
        if items:
            result[term] = items[0] if len(items) == 1 else items
    issued = values(document.get("dct_issued_s"))
    if issued:
        try:
            result["datePublished"] = date.fromisoformat(issued[0]).isoformat()
        except ValueError:
            # Preserve imprecise/free-text publication dates without an invalid Date.
            result[DCT + "issued"] = issued[0]

    keywords = values(document.get("dcat_keyword_sm")) + values(document.get("dct_subject_sm"))
    if keywords:
        result["keywords"] = list(dict.fromkeys(keywords))
    for field, term in (("dct_creator_sm", "author"), ("dct_publisher_sm", "publisher")):
        names = values(document.get(field))
        if names:
            # Names alone cannot distinguish people from organizations.
            result[term] = [{"name": name} for name in names]
    providers = values(document.get("schema_provider_s"))
    if providers:
        result["provider"] = [{"name": name} for name in providers]
    licenses = values(document.get("dct_license_sm"))
    if licenses:
        result["license"] = [
            {"@id": item} if is_absolute_iri(item) else {"@type": "CreativeWork", "text": item}
            for item in licenses
        ]
    rights = values(document.get("dct_rights_sm"))
    if rights:
        result[DCT + "rights"] = [
            {"@id": item}
            if is_absolute_iri(item)
            else {"@type": DCT + "RightsStatement", "description": item}
            for item in rights
        ]

    places = [{"@type": "Place", "name": name} for name in values(document.get("dct_spatial_sm"))]
    box = _box(document.get("dcat_bbox")) or _box(document.get("locn_geometry"))
    if box:
        places.append({"@type": "Place", "geo": {"@type": "GeoShape", "box": box}})
    if places:
        result["spatialCoverage"] = places

    relationships = {
        "pcdm_memberOf_sm": PCDM + "memberOf",
        "dct_isPartOf_sm": DCT + "isPartOf",
        "dct_ispartof_sm": DCT + "isPartOf",
        "dct_relation_sm": DCT + "relation",
        "dct_replaces_sm": DCT + "replaces",
        "dct_isReplacedBy_sm": DCT + "isReplacedBy",
        "dct_isVersionOf_sm": DCT + "isVersionOf",
        "dct_source_sm": DCT + "source",
    }
    for field, predicate in relationships.items():
        targets = values(document.get(field))
        for target in targets:
            target_uri = _relationship_uri(target, base)
            if target_uri:
                nodes = result.setdefault(predicate, [])
                node = {"@id": target_uri}
                if node not in nodes:
                    nodes.append(node)
    for field, predicate in (
        ("b1g_dct_conformsTo_sm", DCT + "conformsTo"),
        ("b1g_dct_provenance_sm", DCT + "provenance"),
        ("b1g_dct_provenanceStatement_sm", DCT + "provenance"),
    ):
        items = values(document.get(field))
        for item in items:
            nodes = result.setdefault(predicate, [])
            node = {"@id": item} if is_absolute_iri(item) else {"description": item}
            if node not in nodes:
                nodes.append(node)

    refs = _references(document, distribution_context)
    landing_pages = list(_links(refs.get("http://schema.org/url")))
    if landing_pages:
        result["url"] = list(dict.fromkeys([uri] + [item["url"] for item in landing_pages]))
    downloads = []
    seen = set()
    for item in _links(refs.get("http://schema.org/downloadUrl")):
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        download = {"@type": "DataDownload" if kind == "Dataset" else "MediaObject"}
        download["contentUrl"] = item["url"]
        if isinstance(item.get("label"), str) and item["label"].strip():
            download["name"] = item["label"].strip()
        # A resource-level format does not establish the format of each file (e.g. ZIP).
        downloads.append(download)
    if downloads:
        result["distribution" if kind == "Dataset" else "encoding"] = downloads
    if kind == "Dataset":
        result["includedInDataCatalog"] = {
            "@type": "DataCatalog",
            "@id": base,
            "name": "Big Ten Academic Alliance Geoportal",
            "url": base,
        }
    return result
