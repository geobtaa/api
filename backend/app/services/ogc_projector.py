import math
import os
from datetime import date, datetime, timezone
from typing import Any, Dict
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

# The facade is a partial implementation. Do not claim complete conformance
# classes while required temporal/id filters and record properties are missing.
OGC_CONFORMS_TO: list[str] = []


def _public_url(request_url: str) -> str:
    """Use the configured public origin, never untrusted forwarded headers."""
    parsed = urlparse(request_url)
    configured = urlparse(os.getenv("APPLICATION_URL", ""))
    if configured.scheme in ("http", "https") and configured.netloc:
        parsed = parsed._replace(scheme=configured.scheme, netloc=configured.netloc)
    return urlunparse(parsed._replace(fragment=""))


def _base_url(request_url: str, separator: str) -> str:
    parsed = urlparse(_public_url(request_url))
    return urlunparse(parsed._replace(path=parsed.path.split(separator)[0], query=""))


def _string(value: Any) -> str | None:
    if isinstance(value, (list, tuple)):
        return next((text for item in value if (text := _string(item)) is not None), None)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value if isinstance(value, str) else None


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    return [item for item in values if isinstance(item, str)]


def _geometry(resource: Dict[str, Any], attributes: Dict[str, Any]) -> Dict[str, Any] | None:
    """Reuse geometry already parsed by SearchService, without more I/O."""
    geometry = attributes.get("ui_viewer_geometry")
    if geometry is None:
        geometry = resource.get("meta", {}).get("ui", {}).get("viewer", {}).get("geometry")
    if not isinstance(geometry, dict):
        return None
    types = {
        name.lower(): name
        for name in (
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
        )
    }
    geometry_type = types.get(str(geometry.get("type", "")).lower())
    coordinates = geometry.get("coordinates")

    def finite_coordinates(value: Any) -> bool:
        if isinstance(value, (list, tuple)):
            return bool(value) and all(finite_coordinates(item) for item in value)
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )

    if geometry_type is None or not isinstance(coordinates, (list, tuple)):
        return None
    if not finite_coordinates(coordinates):
        return None

    def position(value: Any) -> bool:
        return (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and all(isinstance(number, (int, float)) for number in value)
            and -180 <= value[0] <= 180
            and -90 <= value[1] <= 90
        )

    def line(value: Any) -> bool:
        return isinstance(value, (list, tuple)) and len(value) >= 2 and all(map(position, value))

    def ring(value: Any) -> bool:
        return line(value) and len(value) >= 4 and value[0] == value[-1]

    def polygon(value: Any) -> bool:
        return isinstance(value, (list, tuple)) and bool(value) and all(map(ring, value))

    validators = {
        "Point": position,
        "MultiPoint": lambda value: all(map(position, value)),
        "LineString": line,
        "MultiLineString": lambda value: all(map(line, value)),
        "Polygon": polygon,
        "MultiPolygon": lambda value: all(map(polygon, value)),
    }
    if not validators[geometry_type](coordinates):
        return None
    return {"type": geometry_type, "coordinates": coordinates}


class OGCResponseProjector:
    @staticmethod
    def map_record_to_properties(attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Maps internal BTAA/Aardvark fields to public OGC properties."""

        return {
            "id": _string(attributes.get("id") or attributes.get("layer_slug_s")),
            "title": _string(attributes.get("dct_title_s")),
            "description": _string(attributes.get("dct_description_sm")),
            "resourceClass": _strings(attributes.get("gbl_resourceClass_sm")),
            "resourceType": _strings(attributes.get("gbl_resourceType_sm")),
            "provider": _string(attributes.get("schema_provider_s")),
            "spatial": _strings(attributes.get("dct_spatial_sm")),
            "subject": _strings(attributes.get("dct_subject_sm")),
            "accessRights": _string(attributes.get("dct_accessRights_s")),
            "modified": _string(attributes.get("gbl_mdModified_dt")),
            "dateAccessioned": _string(attributes.get("b1g_dateAccessioned_s")),
            "publicationState": _string(attributes.get("b1g_publication_state_s")),
            "accrualMethod": _string(attributes.get("b1g_dct_accrualMethod_s")),
        }

    @staticmethod
    def build_item(
        request_url: str, resource: Dict[str, Any], collection_id: str = "btaa-records"
    ) -> Dict[str, Any]:
        """Builds a GeoJSON Feature representing a single record item."""

        raw_attributes = resource.get("attributes") or {}
        # Search returns flat hydrated rows; get_resource returns the native
        # JSON:API representation with ogm/b1g namespaces and UI metadata.
        attributes = {
            **raw_attributes,
            **(raw_attributes.get("b1g") or {}),
            **(raw_attributes.get("ogm") or {}),
        }
        item_id = _string(
            attributes.get("id") or resource.get("id") or attributes.get("layer_slug_s")
        )
        attributes["id"] = item_id
        item_path = quote(item_id or "", safe="")
        collection_path = quote(collection_id, safe="")
        base_url = _base_url(request_url, "/ogc")

        # OGC Item format is a GeoJSON Feature
        return {
            "type": "Feature",
            "id": item_id,
            "geometry": _geometry(resource, attributes),
            "properties": OGCResponseProjector.map_record_to_properties(attributes),
            "links": [
                {
                    "href": f"{base_url}/ogc/collections/{collection_path}/items/{item_path}",
                    "rel": "self",
                    "type": "application/geo+json",
                    "title": "This document",
                },
                {
                    "href": f"{base_url}/ogc/collections/{collection_path}",
                    "rel": "collection",
                    "type": "application/json",
                    "title": f"{collection_id} collection",
                },
                {
                    "href": f"{base_url}/resources/{item_path}",
                    "rel": "alternate",
                    "type": "application/json",
                    "title": "BTAA Native API Response",
                },
            ],
        }

    @staticmethod
    def build_landing_page(request_url: str) -> Dict[str, Any]:
        """Builds the OGC API landing page."""
        base_url = _public_url(request_url).split("?")[0].rstrip("/")
        api_root = base_url.removesuffix("/v1/ogc")

        return {
            "title": "BTAA Geospatial API - OGC API Records",
            "description": "OGC API Records facade for the BTAA Geospatial API",
            "links": [
                {
                    "href": f"{base_url}/",
                    "rel": "self",
                    "type": "application/json",
                    "title": "This document",
                },
                {
                    "href": f"{api_root}/openapi.json",
                    "rel": "service-desc",
                    "type": "application/vnd.oai.openapi+json;version=3.1",
                    "title": "API definition",
                },
                {
                    "href": f"{api_root}/docs",
                    "rel": "service-doc",
                    "type": "text/html",
                    "title": "API documentation",
                },
                {
                    "href": f"{base_url}/conformance",
                    "rel": "conformance",
                    "type": "application/json",
                    "title": "OGC API conformance classes implemented by this server",
                },
                {
                    "href": f"{base_url}/collections",
                    "rel": "data",
                    "type": "application/json",
                    "title": "Metadata about the feature collections",
                },
            ],
        }

    @staticmethod
    def build_conformance() -> Dict[str, Any]:
        """Builds the OGC API conformance declaration."""
        return {"conformsTo": OGC_CONFORMS_TO}

    @staticmethod
    def build_collections(request_url: str) -> Dict[str, Any]:
        """Builds the collections response."""
        base_url = _base_url(request_url, "/collections")
        collection = OGCResponseProjector.build_collection(request_url, "btaa-records")

        return {
            "collections": [collection],
            "links": [
                {
                    "href": f"{base_url}/collections",
                    "rel": "self",
                    "type": "application/json",
                    "title": "This document",
                }
            ],
        }

    @staticmethod
    def build_collection(request_url: str, collection_id: str) -> Dict[str, Any]:
        """Builds a single collection description."""
        base_url = _base_url(request_url, "/collections")

        return {
            "id": collection_id,
            "type": "Catalog",
            "title": "BTAA Geospatial Records",
            "description": "Records aggregated from BTAA institutions.",
            "itemType": "record",
            "links": [
                {
                    "href": f"{base_url}/collections/{collection_id}",
                    "rel": "self",
                    "type": "application/json",
                    "title": "This document",
                },
                {
                    "href": f"{base_url}/collections/{collection_id}/items",
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": "Items in this collection",
                },
                {
                    "href": f"{base_url}/collections/{collection_id}/queryables",
                    "rel": "queryables",
                    "type": "application/schema+json",
                    "title": "Queryables for this collection",
                },
                {
                    "href": f"{base_url}/collections/{collection_id}/sortables",
                    "rel": "sortables",
                    "type": "application/schema+json",
                    "title": "Sortables for this collection",
                },
            ],
        }

    @staticmethod
    def build_items_response(
        request_url: str,
        search_results: Dict[str, Any],
        page: int,
        limit: int,
        collection_id: str = "btaa-records",
    ) -> Dict[str, Any]:
        """Builds an Item Collection (Feature Collection) response from search results."""
        features = []
        data = search_results.get("data", [])

        for resource in data:
            features.append(OGCResponseProjector.build_item(request_url, resource, collection_id))

        request_url = _public_url(request_url)
        base_url = request_url.split("?")[0]
        parsed_url = urlparse(request_url)
        query_params = [
            (key, value)
            for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
            if key != "page"
        ]

        links = [
            {
                "href": request_url,
                "rel": "self",
                "type": "application/geo+json",
                "title": "This document",
            }
        ]

        meta = search_results.get("meta", {})
        pages = meta.get("pages", {})
        total_pages = pages.get("total_pages", 0)

        if page < total_pages:
            next_params = [*query_params, ("page", str(page + 1))]
            links.append(
                {
                    "href": f"{base_url}?{urlencode(next_params)}",
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        if page > 1:
            prev_params = [*query_params, ("page", str(page - 1))]
            links.append(
                {
                    "href": f"{base_url}?{urlencode(prev_params)}",
                    "rel": "prev",
                    "type": "application/geo+json",
                    "title": "Previous page",
                }
            )

        return {
            "type": "FeatureCollection",
            "timeStamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "numberMatched": pages.get("total_count", 0),
            "numberReturned": len(features),
            "features": features,
            "links": links,
        }

    @staticmethod
    def build_queryables(request_url: str) -> Dict[str, Any]:
        """Builds the queryables JSON schema document."""
        return {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "$id": _public_url(request_url),
            "type": "object",
            "title": "Queryables for BTAA Geospatial Records",
            "description": "Property filters are not supported by this facade.",
            "properties": {},
            "additionalProperties": False,
        }

    @staticmethod
    def build_sortables(request_url: str) -> Dict[str, Any]:
        """Builds the sortables JSON schema document."""
        return {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "$id": _public_url(request_url),
            "type": "object",
            "title": "Sortables for BTAA Geospatial Records",
            "properties": {
                "title": {"type": "string"},
                "relevance": {"type": "string"},
            },
        }
