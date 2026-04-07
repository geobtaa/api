import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.security import HTTPBasic

from app.api.v1.auth import verify_credentials
from app.api.v1.utils import create_response, sanitize_for_json
from app.services.admin_service import (
    AdminService,
    CacheManagementError,
    CacheManagementService,
    ReindexingError,
    ReindexingService,
    ResourceNotFoundError,
    ResourceProcessingError,
    ResourceProcessingService,
)

logger = logging.getLogger(__name__)

security = HTTPBasic()
router = APIRouter(dependencies=[Depends(verify_credentials)])


def get_admin_service() -> AdminService:
    """Dependency injection for AdminService."""
    cache_management_service = CacheManagementService()
    reindexing_service = ReindexingService()
    resource_processing_service = ResourceProcessingService()
    return AdminService(cache_management_service, reindexing_service, resource_processing_service)


# Module-level singleton for dependency injection
_admin_service_dependency = Depends(get_admin_service)


@router.post("/cache/clear")
async def clear_cache(
    cache_type: Optional[str] = Query(
        None, description="Type of cache to clear (search, item, suggest, all)"
    ),
    service: AdminService = _admin_service_dependency,
):
    """Clear specified cache or all cache if not specified."""
    try:
        result = await service.clear_cache(cache_type)
        return create_response(result)
    except CacheManagementError:
        logger.error("Cache management error while clearing cache", exc_info=True)
        return create_response({"error": "Failed to clear cache"}, status_code=500)
    except Exception:
        logger.error("Unexpected error clearing cache", exc_info=True)
        return create_response({"error": "Failed to clear cache"}, status_code=500)


@router.post("/reindex")
async def reindex(
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: AdminService = _admin_service_dependency,
):
    """Trigger reindexing of all items in Elasticsearch."""
    try:
        result = await service.reindex_resources()
        return create_response(result, callback)
    except ReindexingError as e:
        logger.error("Reindexing error", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Reindexing failed"}) from e
    except Exception as e:
        logger.error("Unexpected error during reindexing", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Reindexing failed"}) from e


@router.post("/resources/{id}/summarize")
async def summarize_resource(
    id: str,
    background_tasks: BackgroundTasks,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: AdminService = _admin_service_dependency,
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
        result = await service.summarize_resource(id)

        # Sanitize the response data before returning
        sanitized_response = sanitize_for_json(result)
        return create_response(sanitized_response, callback)
    except ResourceNotFoundError as e:
        logger.error("Resource not found while summarizing %s", id, exc_info=True)
        raise HTTPException(status_code=404, detail="Resource not found") from e
    except ResourceProcessingError as e:
        logger.error("Resource processing error while summarizing %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start summary generation") from e
    except Exception as e:
        logger.error(
            "Unexpected error triggering summary generation for resource %s",
            id,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to start summary generation") from e


@router.post("/resources/{id}/identify-geo-entities")
async def identify_geo_entities(
    id: str,
    background_tasks: BackgroundTasks,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: AdminService = _admin_service_dependency,
):
    """
    Trigger the identification of geographic entities in a resource.
    This endpoint will:
    1. Fetch the resource metadata
    2. Trigger an asynchronous task to identify geographic entities
    3. Return immediately with task ID
    """
    try:
        result = await service.identify_geo_entities(id)
        return create_response(result, callback)
    except ResourceNotFoundError as e:
        logger.error(
            "Resource not found while identifying geographic entities for %s",
            id,
            exc_info=True,
        )
        raise HTTPException(status_code=404, detail="Resource not found") from e
    except ResourceProcessingError as e:
        logger.error(
            "Resource processing error while identifying geographic entities for %s",
            id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to start geographic entity identification"
        ) from e
    except Exception as e:
        logger.error(
            "Unexpected error triggering geographic entity identification for resource %s",
            id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to start geographic entity identification"
        ) from e
