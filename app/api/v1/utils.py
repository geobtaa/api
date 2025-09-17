import json
import logging
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse

from app.api.v1.jsonp import JSONPResponse

logger = logging.getLogger(__name__)


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize an object for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif hasattr(obj, "isoformat"):  # Handle datetime objects
        return obj.isoformat()
    elif hasattr(obj, "__dict__"):  # Handle objects with __dict__
        return sanitize_for_json(obj.__dict__)
    # Handle Decimal objects from database
    elif hasattr(obj, "__float__"):
        return float(obj)
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


def add_thumbnail_url(item: Dict) -> Dict:
    """Add the ui_thumbnail_url to the item."""
    from app.services.image_service import ImageService

    image_service = ImageService(item)
    thumbnail_url = image_service.get_thumbnail_url()
    item["ui_thumbnail_url"] = thumbnail_url
    return item


def add_citations(item: Dict) -> Dict:
    """Add citations to an item."""
    # Ensure 'attributes' key exists
    if "attributes" not in item:
        item["attributes"] = {}

    try:
        from app.services.citation_service import CitationService

        citation_service = CitationService(item)
        item["attributes"]["ui_citation"] = citation_service.get_citation()
    except Exception as e:
        logger.error(f"Failed to generate citation: {str(e)}")
        item["attributes"]["ui_citation"] = "Citation unavailable"
    return item


def add_ui_attributes(item: Dict) -> Dict:
    """Add UI attributes to an item."""
    # Parse references if needed
    if isinstance(item.get("dct_references_s"), str):
        try:
            item["dct_references_s"] = json.loads(item["dct_references_s"])
        except json.JSONDecodeError:
            item["dct_references_s"] = {}

    # Create services
    from app.services.citation_service import CitationService
    from app.services.download_service import DownloadService
    from app.services.image_service import ImageService
    from app.services.viewer_service import create_viewer_attributes

    image_service = ImageService(item)
    citation_service = CitationService(item)
    download_service = DownloadService(item)

    # Add viewer attributes
    item.update(create_viewer_attributes(item))

    # Add thumbnail URL if available
    if thumbnail_url := image_service.get_thumbnail_url():
        item["ui_thumbnail_url"] = thumbnail_url

    # Add citation
    item["ui_citation"] = citation_service.get_citation()

    # Add download options
    item["ui_downloads"] = download_service.get_download_options()

    return item


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
                "https://gin.btaa.org/ld/profiles/ogm-aardvark-btaa.profile.jsonld",
                "https://gin.btaa.org/ld/profiles/ogm-ui.profile.jsonld",
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
        "ui_citation",
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

    # Restructure UI fields to remove prefixes and organize viewer
    restructured_ui = {}

    # Simple field mappings (remove ui_ prefix)
    if "ui_thumbnail_url" in ui_fields:
        restructured_ui["thumbnail_url"] = ui_fields["ui_thumbnail_url"]
    if "ui_citation" in ui_fields:
        restructured_ui["citation"] = ui_fields["ui_citation"]
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
        "id": str(resource_data.get("id", "")),
        "attributes": core_attributes,
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

    # Add thumbnail URL
    resource_dict = add_thumbnail_url(resource_dict)

    # Generate citation using CitationService
    citation_service = CitationService(resource_dict)
    ui_citation = citation_service.get_citation()

    # Use ViewerService to get viewer attributes
    viewer_service = ViewerService(resource_dict)
    viewer_attributes = viewer_service.get_viewer_attributes()

    # Use DownloadService to get download options
    download_service = DownloadService(resource_dict)
    ui_downloads = download_service.get_download_options()

    # Use LinkService to get links
    link_service = LinkService(resource_dict)
    ui_links = link_service.get_links()

    # Use RelationshipService to get relationships
    ui_relationships = await RelationshipService.get_resource_relationships(resource_dict["id"])

    # Get Allmaps attributes
    allmaps_service = AllmapsService(resource_dict)
    allmaps_attributes = await allmaps_service.get_allmaps_attributes(session)

    # Create the attributes dictionary
    attributes = {
        **resource_dict,
        "ui_citation": ui_citation,  # Use generated citation
        "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
        "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
        "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
        "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
        "ui_downloads": ui_downloads,
        "ui_links": ui_links,
        "ui_relationships": ui_relationships,
    }

    # Add viewer attributes
    for key, value in viewer_attributes.items():
        if key not in attributes:
            attributes[key] = value

    # Create JSON:API compliant resource first
    resource = create_jsonapi_resource(attributes)

    # Add Allmaps attributes to meta.ui.allmaps section
    if allmaps_attributes:
        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        # Wrap Allmaps attributes in an allmaps object
        resource["meta"]["ui"]["allmaps"] = allmaps_attributes

    return resource


async def process_resource_optimized(resource_dict, allmaps_attributes, apply_field_mapping=True):
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

    # Add thumbnail URL
    resource_dict = add_thumbnail_url(resource_dict)

    # Generate citation using CitationService
    citation_service = CitationService(resource_dict)
    ui_citation = citation_service.get_citation()

    # Use ViewerService to get viewer attributes
    viewer_service = ViewerService(resource_dict)
    viewer_attributes = viewer_service.get_viewer_attributes()

    # Use DownloadService to get download options
    download_service = DownloadService(resource_dict)
    ui_downloads = download_service.get_download_options()

    # Use LinkService to get links
    link_service = LinkService(resource_dict)
    ui_links = link_service.get_links()

    # Use RelationshipService to get relationships
    ui_relationships = await RelationshipService.get_resource_relationships(resource_dict["id"])

    # Use pre-fetched Allmaps attributes (no database query needed!)
    # allmaps_attributes is passed in as a parameter

    # Create the attributes dictionary
    attributes = {
        **resource_dict,
        "ui_citation": ui_citation,  # Use generated citation
        "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
        "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
        "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
        "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
        "ui_downloads": ui_downloads,
        "ui_links": ui_links,
        "ui_relationships": ui_relationships,
    }

    # Add viewer attributes
    for key, value in viewer_attributes.items():
        if key not in attributes:
            attributes[key] = value

    # Create JSON:API compliant resource first
    resource = create_jsonapi_resource(attributes)

    # Add pre-fetched Allmaps attributes to meta.ui.allmaps section
    if allmaps_attributes:
        if "meta" not in resource:
            resource["meta"] = {}
        if "ui" not in resource["meta"]:
            resource["meta"]["ui"] = {}

        # Wrap Allmaps attributes in an allmaps object
        resource["meta"]["ui"]["allmaps"] = allmaps_attributes

    return resource
