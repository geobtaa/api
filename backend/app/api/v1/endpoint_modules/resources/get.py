from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_jsonapi_response, process_resource, sanitize_for_json
from app.services.cache_service import cached_endpoint
from db.models import resources

from . import RESOURCE_CACHE_TTL, filter_resource_fields, get_async_session, logger, router


@router.get("/resources/{id}")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
    request: Request = None,
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

            # Apply field filtering if fields parameter is provided
            if fields:
                resource_dict = filter_resource_fields(resource_dict, fields)
                logger.info(f"Filtered resource dict: {resource_dict}")

            # Process the resource using the shared function (this will add Allmaps to meta.ui)
            jsonapi_resource = await process_resource(resource_dict, session)

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=jsonapi_resource, request_url=request_url, callback=callback
        )

        return JSONResponse(content=jsonapi_response)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

