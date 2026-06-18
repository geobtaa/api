import json
import logging
import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional

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
    fetch_distribution_context,  # noqa: F401 - used by ResourcePresenter via utils shim
)
from app.services.licensed_access_repository import (
    fetch_resource_licensed_accesses,
    serialize_resource_licensed_accesses,
)
from db.database import database
from db.models import resource_assets

logger = logging.getLogger(__name__)
IMMUTABLE_THUMBNAIL_URL_RE = re.compile(
    r"(?:https?://[^/]+)?/api/v1/thumbnails/[0-9a-f]{64}(?:\?.*)?$",
    re.IGNORECASE,
)
_UNSET = object()


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
    elif isinstance(obj, BaseException):
        return "Internal error"
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
        hydrate_asset=False,
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
    map_hash = map_service.get_asset_hash_sync(
        resource_id,
        variant="resource-class-icon",
        source_signature=source_signature,
        hydrate_asset=False,
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
    urls_by_id = await _get_thumbnail_asset_urls([resource_id])
    return urls_by_id.get(resource_id)


async def _get_thumbnail_asset_urls(resource_ids: Iterable[str]) -> Dict[str, str]:
    """
    Return the first thumbnail-capable asset URL for each resource, if any.

    We look for resource_assets rows where:
    - resource_id matches
    - thumbnail is true
    - file_url is not null/empty
    and prefer the lowest position/id for stable ordering.
    """
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    try:
        if not database.is_connected:
            await database.connect()
        query = (
            select(resource_assets.c.resource_id, resource_assets.c.file_url)
            .where(
                resource_assets.c.resource_id.in_(ids),
                resource_assets.c.thumbnail.is_(True),
                resource_assets.c.file_url.is_not(None),
            )
            .order_by(
                resource_assets.c.resource_id.asc(),
                resource_assets.c.position.asc(),
                resource_assets.c.id.asc(),
            )
        )
        rows = await database.fetch_all(query)
        urls_by_id: Dict[str, str] = {}
        for row in rows:
            resource_id = str(row["resource_id"] or "")
            if not resource_id or resource_id in urls_by_id:
                continue
            raw_url = row["file_url"]
            if not isinstance(raw_url, str):
                continue
            url = raw_url.strip()
            if url:
                urls_by_id[resource_id] = url
        return urls_by_id
    except Exception:
        # Never fail the request because of asset lookup issues
        logger.exception("Failed to resolve thumbnail assets for resources %s", ids)
        return {}


def _build_resource_thumbnail_url(resource_id: str) -> str:
    """Return the stable API thumbnail endpoint for a resource."""
    application_url = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")
    return f"{application_url}/api/v1/resources/{resource_id}/thumbnail"


def _build_thumbnail_asset_url(image_hash: str) -> str:
    """Return the immutable API thumbnail asset URL for a cached image hash."""
    return f"{_application_url()}/api/v1/thumbnails/{image_hash}"


def _hot_thumbnail_url_for_resource(
    resource_dict: Dict[str, Any],
    *,
    distribution_context: DistributionContext | None = None,
    thumbnail_asset_url: str | None = None,
) -> Optional[str]:
    """Return an immutable thumbnail URL for the current source when bytes exist."""
    resource_id = resource_dict.get("id")
    if not resource_id:
        return None

    try:
        from app.services.image_service import ImageService

        if distribution_context is None:
            distribution_context = build_distribution_context(str(resource_id), [])
        image_service = ImageService(resource_dict, distribution_context=distribution_context)
        image_hash = image_service.current_thumbnail_hash_with_asset_sync(
            thumbnail_asset_url=thumbnail_asset_url
        )
        return _build_thumbnail_asset_url(image_hash) if image_hash else None
    except Exception as exc:
        logger.debug("Failed resolving hot thumbnail for %s: %s", resource_id, exc)
        return None


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
    from app.api.v1.presenters import ResourcePresenter

    return ResourcePresenter.serialize_jsonapi_resource(resource_data, request_url=request_url)


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


async def _fetch_allmaps_attributes_for_resource(resource_dict, session=None):
    from app.services.allmaps_service import AllmapsService

    allmaps_service = AllmapsService(resource_dict)
    if session is not None:
        return await allmaps_service.get_allmaps_attributes(session)

    from db.session import async_session as app_async_session

    async with app_async_session() as owned_session:
        return await allmaps_service.get_allmaps_attributes(owned_session)


async def _fetch_data_dictionaries_payload_for_resource(resource_id: str, session=None):
    if session is not None:
        data_dictionaries = await fetch_resource_data_dictionaries(
            resource_id,
            session=session,
        )
    else:
        from db.session import async_session as app_async_session

        async with app_async_session() as owned_session:
            data_dictionaries = await fetch_resource_data_dictionaries(
                resource_id,
                session=owned_session,
            )

    if not data_dictionaries:
        return None

    return sanitize_for_json(serialize_resource_data_dictionaries(data_dictionaries))


async def _fetch_licensed_accesses_payload_for_resource(resource_id: str, session=None):
    if session is not None:
        licensed_accesses = await fetch_resource_licensed_accesses(
            resource_id,
            session=session,
        )
    else:
        from db.session import async_session as app_async_session

        async with app_async_session() as owned_session:
            licensed_accesses = await fetch_resource_licensed_accesses(
                resource_id,
                session=owned_session,
            )

    if not licensed_accesses:
        return None

    return sanitize_for_json(serialize_resource_licensed_accesses(licensed_accesses))


async def add_similar_items_to_resource(resource, resource_dict, session=None):
    """Attach similar items to a JSON:API resource object."""
    try:
        from app.services.similar_items_service import SimilarItemsService

        if session is not None:
            similar_items = await SimilarItemsService.get_similar_items(
                resource_dict["id"], session, limit=12
            )
        else:
            from db.session import async_session as app_async_session

            async with app_async_session() as owned_session:
                similar_items = await SimilarItemsService.get_similar_items(
                    resource_dict["id"], owned_session, limit=12
                )

        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["similar_items"] = similar_items
    except Exception as e:
        logger.warning(
            f"Error getting similar items for resource {resource_dict.get('id')}: {str(e)}"
        )
        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["similar_items"] = []

    return resource


async def process_resource(
    resource_dict,
    session=None,
    apply_field_mapping=True,
    *,
    include_similar_items: bool = True,
    hot_only_thumbnail_url: bool = False,
    distribution_context: DistributionContext | None = None,
    ui_downloads: list[dict[str, Any]] | None = None,
    bridge_asset_download_rows: Any = None,
    licensed_accesses_payload: list[dict[str, Any]] | None | object = _UNSET,
    ui_relationships: dict[str, Any] | None = None,
    ui_relationship_counts: dict[str, int] | None = None,
    ui_relationship_browse_links: dict[str, str] | None = None,
    allmaps_attributes: dict[str, Any] | None = None,
    data_dictionaries_payload: list[dict[str, Any]] | None | object = _UNSET,
    thumbnail_asset_url: str | None | object = _UNSET,
):
    """
    Process a resource to add UI fields and prepare it for JSON:API response.
    Compatibility wrapper around ResourcePresenter.

    Args:
        resource_dict: The resource data from the database
        session: Optional database session to reuse for DB-backed enrichments.
        apply_field_mapping: Whether to apply OGM field mapping (default: True)

    Returns:
        JSON:API compliant resource object
    """
    from app.api.v1.presenters import (
        RESOURCE_PRESENTATION_UNSET,
        ResourceHydrationContext,
        ResourcePresenter,
    )

    hydration = ResourceHydrationContext(
        distribution_context=distribution_context,
        ui_downloads=ui_downloads,
        bridge_asset_download_rows=bridge_asset_download_rows,
        licensed_accesses_payload=(
            RESOURCE_PRESENTATION_UNSET
            if licensed_accesses_payload is _UNSET
            else licensed_accesses_payload
        ),
        ui_relationships=ui_relationships,
        ui_relationship_counts=ui_relationship_counts,
        ui_relationship_browse_links=ui_relationship_browse_links,
        allmaps_attributes=allmaps_attributes,
        data_dictionaries_payload=(
            RESOURCE_PRESENTATION_UNSET
            if data_dictionaries_payload is _UNSET
            else data_dictionaries_payload
        ),
        thumbnail_asset_url=(
            RESOURCE_PRESENTATION_UNSET if thumbnail_asset_url is _UNSET else thumbnail_asset_url
        ),
    )

    return await ResourcePresenter(session=session).present_full(
        resource_dict,
        apply_field_mapping=apply_field_mapping,
        include_similar_items=include_similar_items,
        hot_only_thumbnail_url=hot_only_thumbnail_url,
        hydration=hydration,
    )


async def add_licensed_accesses_to_resource(
    resource: dict[str, Any],
    resource_id: str,
    session=None,
) -> dict[str, Any]:
    """Attach current licensed access rows to a JSON:API resource."""
    try:
        payload = await _fetch_licensed_accesses_payload_for_resource(resource_id, session)
    except Exception as e:
        logger.warning("Failed to load licensed accesses for resource %s: %s", resource_id, str(e))
        return resource

    resource.setdefault("meta", {})
    resource["meta"].setdefault("ui", {})
    if payload:
        resource["meta"]["ui"]["licensed_accesses"] = payload
    else:
        resource["meta"]["ui"].pop("licensed_accesses", None)

    return resource


async def process_resource_homepage(resource_dict, session=None, apply_field_mapping=True):
    """
    Lightweight resource processor for homepage previews.

    The homepage only needs the core OGM attributes plus thumbnail/viewer metadata,
    so this path intentionally skips downloads, relationships, similar items, and
    other expensive enrichments used by the full resource view.
    """
    from app.api.v1.presenters import ResourcePresenter

    return await ResourcePresenter(session=session).present_homepage(
        resource_dict,
        apply_field_mapping=apply_field_mapping,
    )


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
    from app.api.v1.presenters import ResourcePresenter

    return await ResourcePresenter(session=None).present_search_result(
        resource_dict,
        allmaps_attributes,
        apply_field_mapping=apply_field_mapping,
        hot_only_thumbnail_url=hot_only_thumbnail_url,
    )
