from typing import Any, Dict
from urllib.parse import urlencode, urlparse

OGC_CONFORMS_TO = [
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/record-core",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/record-collection",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/records-api",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/searchable-catalog",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/sorting",
]


class OGCResponseProjector:
    @staticmethod
    def map_record_to_properties(attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Maps internal BTAA/Aardvark fields to public OGC properties."""

        # Ensure lists are unwrapped where we expect single values, if they are stored as lists
        description = attributes.get("dct_description_sm")
        if isinstance(description, list) and len(description) > 0:
            description = description[0]

        return {
            "id": attributes.get("id") or attributes.get("layer_slug_s"),
            "title": attributes.get("dct_title_s"),
            "description": description,
            "resourceClass": attributes.get("gbl_resourceClass_sm", []),
            "resourceType": attributes.get("gbl_resourceType_sm", []),
            "provider": attributes.get("schema_provider_s"),
            "spatial": attributes.get("dct_spatial_sm", []),
            "subject": attributes.get("dct_subject_sm", []),
            "accessRights": attributes.get("dct_accessRights_s"),
            "modified": attributes.get("gbl_mdModified_dt"),
            "dateAccessioned": attributes.get("b1g_dateAccessioned_s"),
            "publicationState": attributes.get("b1g_publication_state_s"),
            "accrualMethod": attributes.get("b1g_dct_accrualMethod_s"),
        }

    @staticmethod
    def build_item(
        request_url: str, resource: Dict[str, Any], collection_id: str = "btaa-records"
    ) -> Dict[str, Any]:
        """Builds a GeoJSON Feature representing a single record item."""

        attributes = resource.get("attributes", {})
        item_id = attributes.get("id") or resource.get("id")

        base_url = request_url.split("/ogc")[0]

        # OGC Item format is a GeoJSON Feature
        return {
            "type": "Feature",
            "id": item_id,
            "geometry": None,  # Excluded in v1 to keep things simple
            "properties": OGCResponseProjector.map_record_to_properties(attributes),
            "links": [
                {
                    "href": f"{base_url}/ogc/collections/{collection_id}/items/{item_id}",
                    "rel": "self",
                    "type": "application/geo+json",
                    "title": "This document",
                },
                {
                    "href": f"{base_url}/ogc/collections/{collection_id}",
                    "rel": "collection",
                    "type": "application/json",
                    "title": f"{collection_id} collection",
                },
                {
                    "href": f"{base_url}/api/v1/resources/{item_id}",
                    "rel": "alternate",
                    "type": "application/json",
                    "title": "BTAA Native API Response",
                },
            ],
        }

    @staticmethod
    def build_landing_page(request_url: str) -> Dict[str, Any]:
        """Builds the OGC API landing page."""
        base_url = request_url.rstrip("/")

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
        base_url = request_url.split("/collections")[0]
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
        base_url = request_url.split("/collections")[0]

        return {
            "id": collection_id,
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

        base_url = request_url.split("?")[0]
        parsed_url = urlparse(request_url)
        query_params = (
            dict(q.split("=") for q in parsed_url.query.split("&") if q) if parsed_url.query else {}
        )

        links = [
            {
                "href": request_url,
                "rel": "self",
                "type": "application/geo+json",
                "title": "This document",
            }
        ]

        meta = search_results.get("meta", {})
        total_pages = meta.get("totalPages", 1)

        if page < total_pages:
            next_params = query_params.copy()
            next_params["page"] = str(page + 1)
            links.append(
                {
                    "href": f"{base_url}?{urlencode(next_params)}",
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        if page > 1:
            prev_params = query_params.copy()
            prev_params["page"] = str(page - 1)
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
            "timeStamp": search_results.get("queryTime", {}).get(
                "totalResponseTime"
            ),  # Informational, won't strictly be ISO unless adjusted
            "numberMatched": meta.get("totalCount", 0),
            "numberReturned": len(features),
            "features": features,
            "links": links,
        }

    @staticmethod
    def build_queryables(request_url: str) -> Dict[str, Any]:
        """Builds the queryables JSON schema document."""
        return {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "$id": request_url,
            "type": "object",
            "title": "Queryables for BTAA Geospatial Records",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "resourceClass": {"type": "array", "items": {"type": "string"}},
                "resourceType": {"type": "array", "items": {"type": "string"}},
                "provider": {"type": "string"},
                "spatial": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "array", "items": {"type": "string"}},
                "accessRights": {"type": "string"},
                "modified": {"type": "string", "format": "date-time"},
                "dateAccessioned": {"type": "string", "format": "date"},
                "publicationState": {"type": "string"},
                "accrualMethod": {"type": "string"},
            },
        }

    @staticmethod
    def build_sortables(request_url: str) -> Dict[str, Any]:
        """Builds the sortables JSON schema document."""
        return {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "$id": request_url,
            "type": "object",
            "title": "Sortables for BTAA Geospatial Records",
            "properties": {
                "title": {"type": "string"},
                "modified": {"type": "string"},
                "dateAccessioned": {"type": "string"},
                "relevance": {"type": "string"},
            },
        }
