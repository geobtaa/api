from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_jsonapi_response, process_resource, sanitize_for_json
from app.services.cache_service import cached_endpoint
from db.models import resources

from . import LIST_CACHE_TTL, filter_resource_fields, get_async_session, logger, router


@router.get("/resources/")
@cached_endpoint(ttl=LIST_CACHE_TTL)
async def list_resources(
    request: Request,
    skip: int = 0,
    limit: int = 10,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
):
    try:
        async with get_async_session() as session:
            query = select(resources).offset(skip).limit(limit)
            logger.debug("Executing resource list query: %s", query)
            result = await session.execute(query)
            results = result.fetchall()  # Get full rows instead of scalars
            logger.debug("Found %s resources for list response", len(results))

        processed_resources = []
        for row in results:
            try:
                # Convert to dict and sanitize datetime objects
                resource_dict = sanitize_for_json(dict(row._mapping))

                # Apply field filtering if fields parameter is provided
                if fields:
                    resource_dict = filter_resource_fields(resource_dict, fields)

                # Process the resource after releasing the list query connection.
                jsonapi_resource = await process_resource(
                    resource_dict,
                    None,
                    include_similar_items=False,
                )
                processed_resources.append(jsonapi_resource)
            except Exception:
                logger.error("Error processing resource in list_resources", exc_info=True)
                continue

        logger.debug("Returning %s processed resources", len(processed_resources))

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=processed_resources, request_url=request_url, callback=callback
        )

        return JSONResponse(content=jsonapi_response)
    except Exception as e:
        logger.error("Error in list_resources", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list resources") from e
