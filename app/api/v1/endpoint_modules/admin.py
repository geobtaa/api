import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.v1.auth import verify_credentials
from app.api.v1.utils import create_response
from app.elasticsearch.index import reindex_resources
from app.services.cache_service import ENDPOINT_CACHE, CacheService, invalidate_cache_with_prefix
from app.tasks.entities import generate_geo_entities
from app.tasks.summarization import generate_resource_summary
from db.database import database
from db.models import resources

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cache/clear")
async def clear_cache(
    cache_type: Optional[str] = Query(
        None, description="Type of cache to clear (search, item, suggest, all)"
    ),
    credentials=Depends(verify_credentials),  # noqa: B008
):
    """Clear specified cache or all cache if not specified."""
    try:
        cache_service = CacheService()

        if cache_type == "search" or cache_type is None:
            await invalidate_cache_with_prefix("app.api.v1.endpoints:search")

        if cache_type == "resource" or cache_type is None:
            await invalidate_cache_with_prefix("app.api.v1.endpoints:get_resource")

        if cache_type == "suggest" or cache_type is None:
            await invalidate_cache_with_prefix("app.api.v1.endpoints:suggest")

        if cache_type == "all" or cache_type is None:
            await cache_service.flush_all()

        return create_response({"message": f"Cache cleared successfully: {cache_type or 'all'}"})
    except Exception as e:
        return create_response({"error": f"Failed to clear cache: {str(e)}"}, status_code=500)


@router.post("/reindex")
async def reindex(
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    credentials=Depends(verify_credentials),  # noqa: B008
):
    """Trigger reindexing of all items in Elasticsearch."""
    try:
        # When reindexing, invalidate all search and suggest caches
        if ENDPOINT_CACHE:
            logger.info("Invalidating search and suggest caches")
            await invalidate_cache_with_prefix("app.api.v1.endpoints:search")
            await invalidate_cache_with_prefix("app.api.v1.endpoints:suggest")

        result = await reindex_resources()
        return create_response(
            {"status": "success", "message": "Reindexing completed", "details": result}, callback
        )
    except Exception as e:
        logger.error(f"Reindexing failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"message": "Reindexing failed", "error": str(e)}
        ) from e


@router.post("/resources/{id}/summarize")
async def summarize_resource(
    id: str,
    background_tasks: BackgroundTasks,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    credentials=Depends(verify_credentials),  # noqa: B008
):
    """
    Trigger the generation of a summary for a resource.
    This endpoint will:
    1. Fetch the resource metadata
    2. Get the asset path and type
    3. Trigger an asynchronous task to generate the summary
    4. Return immediately with task ID
    """
    try:
        # Fetch the resource
        async with database.transaction():
            query = select(resources).where(resources.c.id == id)
            result = await database.fetch_one(query)

            if not result:
                raise HTTPException(status_code=404, detail="Resource not found")

            # Convert to dict and handle datetime serialization
            resource = dict(result)
            for key, value in resource.items():
                if isinstance(value, datetime):
                    resource[key] = value.isoformat()

            # Trigger the background task
            background_tasks.add_task(generate_resource_summary, id, resource)

            return create_response(
                {
                    "status": "success",
                    "message": "Summary generation started",
                    "resource_id": id,
                    "task": "generate_resource_summary",
                },
                callback,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to start summary generation for resource {id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to start summary generation", "error": str(e)},
        ) from e


@router.post("/resources/{id}/identify-geo-entities")
async def identify_geo_entities(
    id: str,
    background_tasks: BackgroundTasks,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    credentials=Depends(verify_credentials),  # noqa: B008
):
    """
    Trigger the identification of geographic entities for a resource.
    This endpoint will:
    1. Fetch the resource metadata
    2. Trigger an asynchronous task to identify geo entities
    3. Return immediately with task ID
    """
    try:
        # Fetch the resource
        async with database.transaction():
            query = select(resources).where(resources.c.id == id)
            result = await database.fetch_one(query)

            if not result:
                raise HTTPException(status_code=404, detail="Resource not found")

            # Convert to dict and handle datetime serialization
            resource = dict(result)
            for key, value in resource.items():
                if isinstance(value, datetime):
                    resource[key] = value.isoformat()

            # Trigger the background task
            background_tasks.add_task(generate_geo_entities, id, resource)

            return create_response(
                {
                    "status": "success",
                    "message": "Geographic entity identification started",
                    "resource_id": id,
                    "task": "generate_geo_entities",
                },
                callback,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to start geo entity identification for resource {id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to start geo entity identification", "error": str(e)},
        ) from e
