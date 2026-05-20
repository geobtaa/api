from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import (
    add_licensed_accesses_to_resource,
    add_similar_items_to_resource,
    create_jsonapi_response,
    process_resource,
    process_resource_homepage,
    sanitize_for_json,
)
from app.services.cache_service import cached_endpoint
from app.services.resource_representation_cache import get_or_build_resource_representation
from db.models import resources

from . import RESOURCE_CACHE_TTL, filter_resource_fields, get_async_session, logger, router


@router.get("/resources/{id}")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource(
    request: Request,
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    ui_profile: Optional[str] = Query(
        None,
        description="Optional lightweight response profile (for example: homepage).",
    ),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
):
    """Get a single resource by ID."""
    try:
        # Get resource data directly from database (not Elasticsearch)
        # to ensure clean Aardvark fields
        async with get_async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize for JSON serialization
            resource_dict = sanitize_for_json(dict(row._mapping))
            resource_dict["id"] = id  # Ensure ID is set

            if ui_profile == "homepage":
                if fields:
                    resource_dict = filter_resource_fields(resource_dict, fields)
                    logger.debug("Filtered resource dict: %s", resource_dict)
                jsonapi_resource = await process_resource_homepage(resource_dict, session)
            elif fields:
                resource_dict = filter_resource_fields(resource_dict, fields)
                logger.debug("Filtered resource dict: %s", resource_dict)
                jsonapi_resource = await process_resource(resource_dict, session)
            else:

                async def build_resource(resource_data: dict):
                    return await process_resource(
                        resource_data,
                        session,
                        include_similar_items=False,
                    )

                jsonapi_resource = await get_or_build_resource_representation(
                    resource_dict,
                    build_resource,
                )
                jsonapi_resource = await add_similar_items_to_resource(
                    jsonapi_resource,
                    resource_dict,
                    session,
                )
                jsonapi_resource = await add_licensed_accesses_to_resource(
                    jsonapi_resource,
                    id,
                    session,
                )

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=jsonapi_resource, request_url=request_url, callback=callback
        )

        return JSONResponse(content=jsonapi_response)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception:
        logger.error("Error getting resource %s", id, exc_info=True)
        return JSONResponse(content={"error": "Failed to get resource"}, status_code=500)
