import json
import logging
import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1.jsonp import JSONPResponse
from app.services.data_dictionary_repository import (
    fetch_resource_data_dictionaries,
    serialize_resource_data_dictionaries,
)
from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
    fetch_distribution_context,
)
from app.services.ogm_field_mapper import OGMFieldMapper
from db.database import database
from db.models import resource_assets

logger = logging.getLogger(__name__)
IMMUTABLE_THUMBNAIL_URL_RE = re.compile(
    r"(?:https?://[^/]+)?/api/v1/thumbnails/[0-9a-f]{64}(?:\?.*)?$",
    re.IGNORECASE,
)


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize an object for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (datetime, date)):  # Handle datetime and date objects
        return obj.isoformat()
    elif hasattr(obj, "isoformat"):  # Handle other objects with isoformat (fallback)
        return obj.isoformat()
    elif hasattr(obj, "__dict__"):  # Handle objects with __dict__
        return sanitize_for_json(obj.__dict__)
    elif isinstance(obj, bool):  # Handle boolean objects (before float conversion)
        return obj
    # Handle Decimal objects from database explicitly (do not coerce ints to float)
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


def filter_empty_values(obj: Any) -> Any:
    """
    Recursively filter out empty arrays and empty strings from a dictionary or list.
    Preserves None values and other falsy values like 0 and False.

    Args:
        obj: The object to filter (dict, list, or other)

    Returns:
        Filtered object with empty arrays and empty strings removed
    """
    if isinstance(obj, dict):
        filtered = {}
        for key, value in obj.items():
            # Recursively filter nested structures
            filtered_value = filter_empty_values(value)

            # Skip empty arrays
            if isinstance(filtered_value, list) and len(filtered_value) == 0:
                continue

            # Skip empty strings
            if isinstance(filtered_value, str) and filtered_value == "":
                continue

            # Include the filtered value
            filtered[key] = filtered_value
        return filtered
    elif isinstance(obj, list):
        # Filter each item in the list
        filtered = [filter_empty_values(item) for item in obj]
        # Remove None entries that might result from filtering (if needed)
        return [
            item for item in filtered if item is not None or isinstance(item, (bool, int, float))
        ]
    else:
        # Return primitive values as-is
        return obj


def create_response(
    content: Dict | JSONResponse, callback: Optional[str] = None, status_code: int = 200
) -> JSONResponse:
    """Create either a JSON or JSONP response based on callback parameter."""
    # If content is already a JSONResponse, return it as is
    if isinstance(content, JSONResponse):
        return content

    # Sanitize content before serialization
    sanitized_content = sanitize_for_json(content)

    if callback:
        return JSONPResponse(content=sanitized_content, callback=callback, status_code=status_code)
    return JSONResponse(content=sanitized_content, status_code=status_code)


def add_thumbnail_url(
    item: Dict,
    distribution_context: Optional[DistributionContext] = None,
    *,
    hot_only: bool = False,
) -> Dict:
    """Add the ui_thumbnail_url to the item."""
    from app.services.image_service import ImageService

    if distribution_context is None:
        distribution_context = build_distribution_context(item.get("id", ""), [])

    image_service = ImageService(item, distribution_context=distribution_context)
    thumbnail_url = (
        image_service.get_hot_thumbnail_url() if hot_only else image_service.get_thumbnail_url()
    )

    # Only set thumbnail_url if one was found (or placeholder for processing)
    # If None, frontend can use resource class (gbl_resourceClass_sm) to show default icon
    item["ui_thumbnail_url"] = thumbnail_url
    return item


def _is_immutable_thumbnail_url(url: Optional[str]) -> bool:
    return isinstance(url, str) and IMMUTABLE_THUMBNAIL_URL_RE.search(url) is not None


def _application_url() -> str:
    return os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")


def _build_static_map_url(resource_id: str) -> str:
    return f"{_application_url()}/api/v1/static-maps/{resource_id}/geometry"


def _build_static_map_asset_url(map_hash: str, *, kind: str | None = None) -> str:
    asset_url = f"{_application_url()}/api/v1/static-map-assets/{map_hash}"
    return f"{asset_url}?kind={kind}" if kind else asset_url


def _hot_static_map_url(resource_dict: Dict[str, Any]) -> Optional[str]:
    geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
    if not geometry:
        return None

    from app.services.static_map_service import StaticMapService

    map_service = StaticMapService()
    source_signature = map_service.geometry_signature(geometry)
    map_hash = map_service.materialize_cached_variant_sync(
        resource_dict["id"],
        variant=map_service.geometry_variant(),
        source_signature=source_signature,
    )
    if not map_hash:
        return None

    return _build_static_map_asset_url(map_hash)


def _hot_resource_class_icon_url(resource_dict: Dict[str, Any]) -> Optional[str]:
    from app.api.v1.endpoint_modules.resources.thumbnail import _resource_class_icon_signature
    from app.services.static_map_service import StaticMapService

    resource_id = resource_dict.get("id")
    if not resource_id:
        return None

    map_service = StaticMapService()
    source_signature = _resource_class_icon_signature(
        resource_dict,
        variant="icon-basemap",
    )
    map_hash = map_service.get_hot_asset_hash_sync(
        resource_id,
        variant="resource-class-icon",
        source_signature=source_signature,
    )
    if not map_hash:
        return None

    return _build_static_map_asset_url(
        map_hash,
        kind="resource-class-icon",
    )


def add_citations(item: Dict, distribution_context: Optional[DistributionContext] = None) -> Dict:
    """Add citations to an item."""
    # Ensure 'attributes' key exists
    if "attributes" not in item:
        item["attributes"] = {}

    try:
        from app.services.citation_service import CitationService

        if distribution_context is None:
            distribution_context = build_distribution_context(item.get("id", ""), [])

        citation_service = CitationService(item, distribution_context=distribution_context)
        item["attributes"]["ui_citation"] = citation_service.get_citation()
    except Exception as e:
        logger.error(f"Failed to generate citation: {str(e)}")
        item["attributes"]["ui_citation"] = "Citation unavailable"
    return item


def add_ui_attributes(
    item: Dict, distribution_context: Optional[DistributionContext] = None
) -> Dict:
    """Add UI attributes to an item."""
    if distribution_context is None:
        distribution_context = build_distribution_context(item.get("id", ""), [])

    # Create services
    from app.services.citation_service import CitationService
    from app.services.download_service import DownloadService
    from app.services.image_service import ImageService
    from app.services.viewer_service import create_viewer_attributes

    image_service = ImageService(item, distribution_context=distribution_context)
    citation_service = CitationService(item, distribution_context=distribution_context)
    download_service = DownloadService(item, distribution_context=distribution_context)

    # Add viewer attributes
    item.update(create_viewer_attributes(item, distribution_context=distribution_context))

    # Add thumbnail URL (always add, even if None)
    item["ui_thumbnail_url"] = image_service.get_thumbnail_url()

    # Add citation
    item["ui_citation"] = citation_service.get_citation()

    # Add download options
    item["ui_downloads"] = download_service.get_download_options()

    return item


async def _get_thumbnail_asset_url(resource_id: str) -> Optional[str]:
    """
    Return the first thumbnail-capable asset URL for a resource, if any.

    We look for resource_assets rows where:
    - resource_id matches
    - thumbnail is true
    - file_url is not null/empty
    and prefer the lowest position/id for stable ordering.
    """
    try:
        if not database.is_connected:
            await database.connect()
        query = (
            select(resource_assets.c.file_url)
            .where(
                resource_assets.c.resource_id == resource_id,
                resource_assets.c.thumbnail.is_(True),
                resource_assets.c.file_url.is_not(None),
            )
            .order_by(resource_assets.c.position.asc(), resource_assets.c.id.asc())
            .limit(1)
        )
        row = await database.fetch_one(query)
        if not row:
            return None
        # databases.Record supports dict-style access, not .get()
        raw_url = row["file_url"]
        if not isinstance(raw_url, str):
            return None
        url = raw_url.strip()
        return url or None
    except Exception:
        # Never fail the request because of asset lookup issues
        logger.exception("Failed to resolve thumbnail asset for resource %s", resource_id)
        return None


def _build_resource_thumbnail_url(resource_id: str) -> str:
    """Return the stable API thumbnail endpoint for a resource."""
    application_url = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")
    return f"{application_url}/api/v1/resources/{resource_id}/thumbnail"


def create_jsonapi_response(data, request_url=None, callback=None):
    """
    Create a JSON:API compliant response.

    Args:
        data: The data to include in the response
        request_url: The full URL of the request for self link
        callback: JSONP callback name if provided

    Returns:
        JSON:API compliant response structure
    """
    response = {
        "jsonapi": {
            "version": "1.1",
            "profile": [
                "https://gin.btaa.org/api/v1/ld/profiles/ogm-b1g.profile.jsonld",
                "https://gin.btaa.org/api/v1/ld/profiles/ogm-ui.profile.jsonld",
            ],
        }
    }

    # Add links if request_url is provided
    if request_url:
        response["links"] = {"self": request_url}

    # Add data
    response["data"] = data

    # Handle JSONP callback
    if callback:
        return f"{callback}({json.dumps(response)})"

    return response


def create_jsonapi_resource(resource_data, request_url=None):
    """
    Create a JSON:API compliant resource object.

    Args:
        resource_data: The resource data from the database
        request_url: The full URL of the request for self link

    Returns:
        JSON:API compliant resource structure
    """
    # Extract UI-related fields to move to meta.ui
    ui_fields = {}
    core_attributes = {}

    # Fields that should go to meta.ui
    ui_field_names = [
        "ui_thumbnail_url",
        "ui_resource_class_icon_url",
        "ui_citation",
        "ui_citations",
        "ui_downloads",
        "ui_links",
        "ui_viewer_protocol",
        "ui_viewer_endpoint",
        "ui_viewer_geometry",
        "ui_relationships",
        "ui_summaries",
        "ai_summaries",
        "suggest",
    ]

    for key, value in resource_data.items():
        if key in ui_field_names:
            ui_fields[key] = value
        else:
            # Only include non-null values in attributes
            if value is not None:
                core_attributes[key] = value

    # Filter out empty arrays and empty strings from core_attributes
    core_attributes = filter_empty_values(core_attributes)

    # Get resource ID for root level (required by JSON:API spec)
    resource_id = core_attributes.get("id") or resource_data.get("id", "")

    # Separate OGM Aardvark fields from B1G custom fields
    ogm_fields = {}
    b1g_fields = {}
    ogm_aardvark_field_set = OGMFieldMapper.get_ogm_aardvark_fields()

    # Classify each field (including 'id' which goes into ogm namespace)
    for key, value in core_attributes.items():
        if key in ogm_aardvark_field_set:
            ogm_fields[key] = value
        else:
            # All other fields (B1G custom fields and legacy/internal fields) go to b1g
            b1g_fields[key] = value

    # Filter empty values from both dictionaries
    ogm_fields = filter_empty_values(ogm_fields)
    b1g_fields = filter_empty_values(b1g_fields)

    # Build nested attributes structure
    nested_attributes = {}
    if ogm_fields:
        nested_attributes["ogm"] = ogm_fields
    if b1g_fields:
        nested_attributes["b1g"] = b1g_fields

    # Restructure UI fields to remove prefixes and organize viewer
    restructured_ui = {}

    # Simple field mappings (remove ui_ prefix)
    if "ui_thumbnail_url" in ui_fields and ui_fields["ui_thumbnail_url"] is not None:
        thumbnail_url = ui_fields["ui_thumbnail_url"]
        restructured_ui["thumbnail_url"] = thumbnail_url
        # Add placeholder flag if it's a placeholder URL
        if "/thumbnails/placeholder" in str(thumbnail_url):
            restructured_ui["thumbnail_placeholder"] = True
    if (
        "ui_resource_class_icon_url" in ui_fields
        and ui_fields["ui_resource_class_icon_url"] is not None
    ):
        restructured_ui["resource_class_icon_url"] = ui_fields["ui_resource_class_icon_url"]
    if "ui_citation" in ui_fields:
        restructured_ui["citation"] = ui_fields["ui_citation"]
    if "ui_citations" in ui_fields:
        restructured_ui["citations"] = ui_fields["ui_citations"]
    if "ui_downloads" in ui_fields:
        restructured_ui["downloads"] = ui_fields["ui_downloads"]
    if "ui_links" in ui_fields:
        restructured_ui["links"] = ui_fields["ui_links"]
    if "ui_relationships" in ui_fields:
        restructured_ui["relationships"] = ui_fields["ui_relationships"]
    if "ui_summaries" in ui_fields:
        restructured_ui["summaries"] = ui_fields["ui_summaries"]
    if "ai_summaries" in ui_fields:
        restructured_ui["ai_summaries"] = ui_fields["ai_summaries"]
    if "suggest" in ui_fields:
        restructured_ui["suggest"] = ui_fields["suggest"]

    # Group viewer-related fields into a nested viewer object
    viewer_fields = {}
    if "ui_viewer_protocol" in ui_fields:
        viewer_fields["protocol"] = ui_fields["ui_viewer_protocol"]
    if "ui_viewer_endpoint" in ui_fields:
        viewer_fields["endpoint"] = ui_fields["ui_viewer_endpoint"]
    if "ui_viewer_geometry" in ui_fields:
        viewer_fields["geometry"] = ui_fields["ui_viewer_geometry"]

    if viewer_fields:
        restructured_ui["viewer"] = viewer_fields

    # Create the resource structure
    resource = {
        "type": "resource",
        "id": str(resource_id),
        "attributes": nested_attributes if nested_attributes else {},
        "meta": {
            "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
            "@type": "BtaaAardvarkRecord",
            "ui": restructured_ui,
        },
    }

    return resource


def strong_params(request, allowed_params):
    """
    Rails-style strong parameters for FastAPI.
    Whitelist and sanitize query parameters to prevent mass assignment vulnerabilities.

    Args:
        request: FastAPI Request object
        allowed_params: List of allowed parameter names

    Returns:
        Dictionary containing only whitelisted parameters
    """
    from urllib.parse import parse_qs

    if not request.query_params:
        return {}

    # Parse the query string to preserve all parameters including arrays
    raw_params = parse_qs(str(request.query_params))

    # Filter to only allowed parameters
    filtered_params = {}
    for key, values in raw_params.items():
        if key in allowed_params:
            if len(values) == 1:
                filtered_params[key] = values[0]
            else:
                # For multiple values, preserve as list
                filtered_params[key] = values
            continue

        # Support dynamic filter params when placeholders like include_filters[field][] are allowed
        has_include_placeholder = any(
            p.startswith("include_filters[") and p.endswith("][]") for p in allowed_params
        )
        has_exclude_placeholder = any(
            p.startswith("exclude_filters[") and p.endswith("][]") for p in allowed_params
        )
        if (has_include_placeholder and key.startswith("include_filters[")) or (
            has_exclude_placeholder and key.startswith("exclude_filters[")
        ):
            if len(values) == 1:
                filtered_params[key] = values[0]
            else:
                filtered_params[key] = values

        # Support fq[field] and fq[field][] style when any explicit fq[...][] is present
        if any(p.startswith("fq[") for p in allowed_params):
            if key.startswith("fq["):
                if len(values) == 1:
                    filtered_params[key] = values[0]
                else:
                    filtered_params[key] = values

    return filtered_params


def create_pagination_links(
    request, current_page, total_pages, pagination_type="page", allowed_params=None
):
    """
    Create pagination links that preserve whitelisted query parameters from the original request.

    Args:
        request: FastAPI Request object
        current_page: Current page number (1-based for page type, 0-based for offset type)
        total_pages: Total number of pages
        pagination_type: Either "page" or "offset" to determine pagination style
        allowed_params: List of allowed parameter names (if None, allows all)

    Returns:
        Dictionary of pagination links
    """
    from urllib.parse import urlencode

    # Get base URL without query params
    base_url = str(request.url).split("?")[0]

    # Use strong parameters if allowed_params is specified
    if allowed_params is not None:
        params = strong_params(request, allowed_params)
    else:
        # Fallback to allowing all parameters (for backward compatibility)
        from urllib.parse import parse_qs

        if request.query_params:
            raw_params = parse_qs(str(request.query_params))
            params = {}
            for key, values in raw_params.items():
                if len(values) == 1:
                    params[key] = values[0]
                else:
                    params[key] = values
        else:
            params = {}

    def build_url(page_param_value):
        """Build URL with updated pagination parameter."""
        updated_params = params.copy()

        if pagination_type == "page":
            updated_params["page"] = page_param_value
        else:  # offset type
            updated_params["offset"] = page_param_value

        # Use urlencode to properly handle arrays and special characters
        query_string = urlencode(updated_params, doseq=True)
        return f"{base_url}?{query_string}" if query_string else base_url

    # Create pagination links
    links = {"self": build_url(current_page)}

    if current_page < total_pages:
        if pagination_type == "page":
            links["next"] = build_url(current_page + 1)
        else:  # offset type
            # For offset, we need to calculate the next offset
            # Assuming limit is in params, default to 10
            limit = int(params.get("limit", 10))
            next_offset = current_page + limit
            links["next"] = build_url(next_offset)

    if current_page > (1 if pagination_type == "page" else 0):
        if pagination_type == "page":
            links["prev"] = build_url(current_page - 1)
        else:  # offset type
            # For offset, we need to calculate the previous offset
            limit = int(params.get("limit", 10))
            prev_offset = max(0, current_page - limit)
            links["prev"] = build_url(prev_offset)

    if total_pages > 1:
        if pagination_type == "page":
            links["first"] = build_url(1)
            links["last"] = build_url(total_pages)
        else:  # offset type
            links["first"] = build_url(0)
            limit = int(params.get("limit", 10))
            last_offset = (total_pages - 1) * limit
            links["last"] = build_url(last_offset)

    return links


def create_gazetteer_meta_and_links(
    request, q, limit, offset, total_count, gazetteer_name, allowed_params=None
):
    """
    Create pagination meta information and links for gazetteer endpoints.

    Args:
        request: FastAPI Request object
        q: Search query string
        limit: Number of results per page
        offset: Number of results to skip
        total_count: Total number of results
        gazetteer_name: Name of the gazetteer (geonames, wof, btaa)
        allowed_params: List of allowed parameter names for strong parameters

    Returns:
        Tuple of (meta, links) dictionaries
    """
    # Calculate pagination info
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1

    # Use the enhanced pagination links function with strong parameters
    links = create_pagination_links(
        request, offset, total_pages, pagination_type="offset", allowed_params=allowed_params
    )

    # Build comprehensive meta information
    meta = {
        "totalCount": total_count,
        "totalPages": total_pages,
        "currentPage": current_page,
        "perPage": limit,
        "query": q,
        "offset": offset,
        "gazetteer": gazetteer_name,
    }

    return meta, links


async def process_resource(resource_dict, session, apply_field_mapping=True):
    """
    Process a resource to add UI fields and prepare it for JSON:API response.
    This function is shared between resources and search endpoints.

    Args:
        resource_dict: The resource data from the database
        session: Database session for Allmaps queries
        apply_field_mapping: Whether to apply OGM field mapping (default: True)

    Returns:
        JSON:API compliant resource object
    """
    from app.services.allmaps_service import AllmapsService
    from app.services.citation_service import CitationService
    from app.services.download_service import DownloadService
    from app.services.link_service import LinkService
    from app.services.ogm_field_mapper import OGMFieldMapper
    from app.services.relationship_service import RelationshipService
    from app.services.viewer_service import ViewerService

    # Map database column names to proper OGM field names (only if requested)
    if apply_field_mapping:
        resource_dict = OGMFieldMapper.map_resource_fields(resource_dict)

    distribution_context = await fetch_distribution_context(resource_dict["id"])

    # Add thumbnail URL
    resource_dict = add_thumbnail_url(resource_dict, distribution_context=distribution_context)

    # Generate citations (APA, MLA, Chicago)
    citation_service = CitationService(resource_dict, distribution_context=distribution_context)
    ui_citations = citation_service.get_all_citations()
    ui_citation = ui_citations["apa"]

    # Use ViewerService to get viewer attributes
    viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
    viewer_attributes = viewer_service.get_viewer_attributes()

    # Use DownloadService to get download options
    download_service = DownloadService(resource_dict, distribution_context=distribution_context)
    ui_downloads = await download_service.get_download_options_with_bridge_asset_downloads()

    # Use LinkService to get links
    link_service = LinkService(resource_dict, distribution_context=distribution_context)
    ui_links = link_service.get_links()

    # Use RelationshipService to get relationships
    ui_relationships = await RelationshipService.get_resource_relationships(resource_dict["id"])

    # Get Allmaps attributes
    allmaps_service = AllmapsService(resource_dict)
    allmaps_attributes = await allmaps_service.get_allmaps_attributes(session)

    # Create the attributes dictionary
    attributes = {
        **resource_dict,
        "ui_citation": ui_citation,
        "ui_citations": ui_citations,
        "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
        "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
        "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
        "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
        "ui_downloads": ui_downloads,
        "ui_links": ui_links,
        "ui_relationships": ui_relationships,
    }

    # Attach read-only resource data dictionaries.
    try:
        data_dictionaries = await fetch_resource_data_dictionaries(
            resource_dict["id"], session=session
        )
        if data_dictionaries:
            attributes["data_dictionaries"] = sanitize_for_json(
                serialize_resource_data_dictionaries(data_dictionaries)
            )
    except Exception as e:
        logger.warning(
            "Failed to load data dictionaries for resource %s: %s",
            resource_dict.get("id"),
            str(e),
        )

    # Regenerate dct_references_s from resource_distributions for OGM Aardvark compatibility
    try:
        legacy_refs = distribution_context.legacy_reference_payload
        if legacy_refs:
            attributes["dct_references_s"] = json.dumps(legacy_refs)
    except Exception:
        # Do not fail response generation due to references serialization issues
        pass

    # Add viewer attributes
    for key, value in viewer_attributes.items():
        if key not in attributes:
            attributes[key] = value

    # Create JSON:API compliant resource first
    resource = create_jsonapi_resource(attributes)

    # If a bridge-synced thumbnail asset exists, expose the stable thumbnail endpoint
    # instead of the raw stored object so clients go through the resize/cache pipeline.
    thumb_asset_url = await _get_thumbnail_asset_url(resource_dict["id"])
    current_thumbnail_url = ((resource.get("meta") or {}).get("ui") or {}).get("thumbnail_url")
    if thumb_asset_url and not _is_immutable_thumbnail_url(current_thumbnail_url):
        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["thumbnail_url"] = _build_resource_thumbnail_url(resource_dict["id"])

    # Add Allmaps attributes to meta.ui.allmaps section
    if allmaps_attributes:
        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        # Wrap Allmaps attributes in an allmaps object
        resource["meta"]["ui"]["allmaps"] = allmaps_attributes

    # Add static map URL to meta.ui if resource has geometry (locn_geometry or dcat_bbox).
    # This points directly at the geometry-overlay asset variant.
    geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
    if geometry:
        static_map_url = _hot_static_map_url(resource_dict) or _build_static_map_url(
            resource_dict["id"]
        )

        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        resource["meta"]["ui"]["static_map"] = static_map_url

    # Add similar items to meta.ui
    try:
        from app.services.similar_items_service import SimilarItemsService

        similar_items = await SimilarItemsService.get_similar_items(
            resource_dict["id"], session, limit=12
        )

        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        resource["meta"]["ui"]["similar_items"] = similar_items
    except Exception as e:
        # Log error but don't fail resource processing
        logger.warning(
            f"Error getting similar items for resource {resource_dict.get('id')}: {str(e)}"
        )
        # Ensure ui block exists even if similar items fail
        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}
        resource["meta"]["ui"]["similar_items"] = []

    return resource


async def process_resource_homepage(resource_dict, session, apply_field_mapping=True):
    """
    Lightweight resource processor for homepage previews.

    The homepage only needs the core OGM attributes plus thumbnail/viewer metadata,
    so this path intentionally skips downloads, relationships, similar items, and
    other expensive enrichments used by the full resource view.
    """
    from app.services.allmaps_service import AllmapsService
    from app.services.ogm_field_mapper import OGMFieldMapper
    from app.services.viewer_service import ViewerService

    if apply_field_mapping:
        resource_dict = OGMFieldMapper.map_resource_fields(resource_dict)

    distribution_context = await fetch_distribution_context(resource_dict["id"])
    resource_dict = add_thumbnail_url(resource_dict, distribution_context=distribution_context)

    viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
    viewer_attributes = viewer_service.get_viewer_attributes()

    allmaps_service = AllmapsService(resource_dict)
    allmaps_attributes = await allmaps_service.get_allmaps_attributes(session)

    attributes = {
        **resource_dict,
        "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
        "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
        "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
        "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
    }

    for key, value in viewer_attributes.items():
        if key not in attributes:
            attributes[key] = value

    resource = create_jsonapi_resource(attributes)

    thumb_asset_url = await _get_thumbnail_asset_url(resource_dict["id"])
    current_thumbnail_url = ((resource.get("meta") or {}).get("ui") or {}).get("thumbnail_url")
    if thumb_asset_url and not _is_immutable_thumbnail_url(current_thumbnail_url):
        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["thumbnail_url"] = _build_resource_thumbnail_url(resource_dict["id"])

    if allmaps_attributes:
        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["allmaps"] = allmaps_attributes

    return resource


async def process_resource_optimized(
    resource_dict,
    allmaps_attributes,
    apply_field_mapping=True,
    *,
    hot_only_thumbnail_url: bool = False,
):
    """
    Optimized version of process_resource for search results that uses pre-fetched Allmaps data.
    This eliminates the need for individual database queries during resource processing.

    Args:
        resource_dict: The resource data from the database
        allmaps_attributes: Pre-fetched Allmaps attributes (dict)
        apply_field_mapping: Whether to apply OGM field mapping (default: True)

    Returns:
        JSON:API compliant resource object
    """
    from app.services.citation_service import CitationService
    from app.services.download_service import DownloadService
    from app.services.link_service import LinkService
    from app.services.ogm_field_mapper import OGMFieldMapper
    from app.services.relationship_service import RelationshipService
    from app.services.viewer_service import ViewerService

    # Map database column names to proper OGM field names (only if requested)
    if apply_field_mapping:
        resource_dict = OGMFieldMapper.map_resource_fields(resource_dict)

    distribution_context = await fetch_distribution_context(resource_dict["id"])

    # Add thumbnail URL
    resource_dict = add_thumbnail_url(
        resource_dict,
        distribution_context=distribution_context,
        hot_only=hot_only_thumbnail_url,
    )
    if hot_only_thumbnail_url and not resource_dict.get("ui_thumbnail_url"):
        resource_dict["ui_resource_class_icon_url"] = _hot_resource_class_icon_url(resource_dict)

    # Generate citations (APA, MLA, Chicago)
    citation_service = CitationService(resource_dict, distribution_context=distribution_context)
    ui_citations = citation_service.get_all_citations()
    ui_citation = ui_citations["apa"]

    # Use ViewerService to get viewer attributes
    viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
    viewer_attributes = viewer_service.get_viewer_attributes()

    # Use DownloadService to get download options
    download_service = DownloadService(resource_dict, distribution_context=distribution_context)
    ui_downloads = await download_service.get_download_options_with_bridge_asset_downloads()

    # Use LinkService to get links
    link_service = LinkService(resource_dict, distribution_context=distribution_context)
    ui_links = link_service.get_links()

    # Use RelationshipService to get relationships
    ui_relationships = await RelationshipService.get_resource_relationships(resource_dict["id"])

    # Use pre-fetched Allmaps attributes (no database query needed!)
    # allmaps_attributes is passed in as a parameter

    # Create the attributes dictionary
    attributes = {
        **resource_dict,
        "ui_citation": ui_citation,
        "ui_citations": ui_citations,
        "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
        "ui_resource_class_icon_url": resource_dict.get("ui_resource_class_icon_url"),
        "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
        "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
        "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
        "ui_downloads": ui_downloads,
        "ui_links": ui_links,
        "ui_relationships": ui_relationships,
    }

    # Regenerate dct_references_s from resource_distributions for OGM Aardvark compatibility
    try:
        legacy_refs = distribution_context.legacy_reference_payload
        if legacy_refs:
            attributes["dct_references_s"] = json.dumps(legacy_refs)
    except Exception:
        pass

    # Add viewer attributes
    for key, value in viewer_attributes.items():
        if key not in attributes:
            attributes[key] = value

    # Create JSON:API compliant resource first
    resource = create_jsonapi_resource(attributes)

    # Prefer the stable thumbnail endpoint when a bridge-synced thumbnail asset exists.
    thumb_asset_url = await _get_thumbnail_asset_url(resource_dict["id"])
    current_thumbnail_url = ((resource.get("meta") or {}).get("ui") or {}).get("thumbnail_url")
    if (
        thumb_asset_url
        and not hot_only_thumbnail_url
        and not _is_immutable_thumbnail_url(current_thumbnail_url)
    ):
        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["thumbnail_url"] = _build_resource_thumbnail_url(resource_dict["id"])

    # Add pre-fetched Allmaps attributes to meta.ui.allmaps section
    if allmaps_attributes:
        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        # Wrap Allmaps attributes in an allmaps object
        resource["meta"]["ui"]["allmaps"] = allmaps_attributes

    # Add static map URL to meta.ui if resource has geometry (locn_geometry or dcat_bbox).
    # See notes above in process_resource().
    geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
    if geometry:
        static_map_url = _hot_static_map_url(resource_dict) or _build_static_map_url(
            resource_dict["id"]
        )

        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        resource["meta"]["ui"]["static_map"] = static_map_url

    # Note: Similar items are intentionally omitted from process_resource_optimized to avoid
    # per-result similarity lookups on search results. Clients should fetch them lazily
    # via the `/api/v1/resources/{id}/similar-items` endpoint when needed.

    return resource
