import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.security import HTTPBasic
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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
from app.services.api_key_service import APIKeyService
from db.config import DATABASE_URL
from db.models import api_keys, api_service_tiers

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

# Create async engine and session for API key operations
api_key_engine = create_async_engine(DATABASE_URL)
api_key_session = sessionmaker(api_key_engine, class_=AsyncSession, expire_on_commit=False)

# API Key Service instance
api_key_service = APIKeyService()


# Pydantic models for request/response
class CreateAPIKeyRequest(BaseModel):
    tier_name: str
    name: Optional[str] = None


class UpdateAPIKeyRequest(BaseModel):
    tier_name: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None


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
    except CacheManagementError as e:
        logger.error(f"Cache management error: {str(e)}")
        return create_response({"error": str(e)}, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error clearing cache: {str(e)}")
        return create_response({"error": f"Failed to clear cache: {str(e)}"}, status_code=500)


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
        logger.error(f"Reindexing error: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"message": "Reindexing failed", "error": str(e)}
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during reindexing: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"message": "Reindexing failed", "error": str(e)}
        ) from e


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
        logger.error(f"Resource not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ResourceProcessingError as e:
        logger.error(f"Resource processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error triggering summary generation for resource {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        logger.error(f"Resource not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ResourceProcessingError as e:
        logger.error(f"Resource processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(
            f"Unexpected error triggering geographic entity identification "
            f"for resource {id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# API Key Management Endpoints


@router.post("/api-keys")
async def create_api_key(
    request: CreateAPIKeyRequest,
):
    """Create a new API key."""
    try:
        result = await api_key_service.create_api_key(
            tier_name=request.tier_name,
            name=request.name,
        )

        if result is None:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create API key. Tier '{request.tier_name}' may not exist.",
            )

        return create_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api-keys")
async def list_api_keys():
    """List all API keys."""
    try:
        async with api_key_session() as session:
            # Join with tiers to get tier information
            stmt = (
                select(api_keys, api_service_tiers)
                .join(api_service_tiers, api_keys.c.tier_id == api_service_tiers.c.id)
                .order_by(api_keys.c.created_at.desc())
            )

            result = await session.execute(stmt)
            rows = result.all()

            keys = []
            for row in rows:
                keys.append(
                    {
                        "id": row[api_keys.c.id],
                        "key_hash": row[api_keys.c.key_hash][:16]
                        + "...",  # Partial hash for display
                        "tier_name": row[api_service_tiers.c.tier_name],
                        "tier_display_name": row[api_service_tiers.c.display_name],
                        "name": row[api_keys.c.name],
                        "is_active": row[api_keys.c.is_active],
                        "created_at": row[api_keys.c.created_at].isoformat()
                        if row[api_keys.c.created_at]
                        else None,
                        "last_used_at": row[api_keys.c.last_used_at].isoformat()
                        if row[api_keys.c.last_used_at]
                        else None,
                    }
                )

            return create_response({"keys": keys})
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/api-keys/{key_id}")
async def update_api_key(
    key_id: int,
    request: UpdateAPIKeyRequest,
):
    """Update an API key."""
    try:
        async with api_key_session() as session:
            # Get existing key
            stmt = select(api_keys).where(api_keys.c.id == key_id)
            result = await session.execute(stmt)
            key_row = result.first()

            if key_row is None:
                raise HTTPException(status_code=404, detail="API key not found")

            # Build update values
            update_values = {}
            if request.tier_name is not None:
                # Get tier ID
                tier_stmt = select(api_service_tiers).where(
                    api_service_tiers.c.tier_name == request.tier_name
                )
                tier_result = await session.execute(tier_stmt)
                tier_row = tier_result.first()

                if tier_row is None:
                    raise HTTPException(
                        status_code=400, detail=f"Tier '{request.tier_name}' not found"
                    )

                update_values["tier_id"] = tier_row[api_service_tiers.c.id]

            if request.is_active is not None:
                update_values["is_active"] = request.is_active

            if request.name is not None:
                update_values["name"] = request.name

            if not update_values:
                raise HTTPException(status_code=400, detail="No fields to update")

            # Update key
            update_stmt = api_keys.update().where(api_keys.c.id == key_id).values(**update_values)
            await session.execute(update_stmt)
            await session.commit()

            return create_response({"message": "API key updated successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating API key: {str(e)}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: int):
    """Revoke (deactivate) an API key."""
    try:
        async with api_key_session() as session:
            # Get key hash
            stmt = select(api_keys).where(api_keys.c.id == key_id)
            result = await session.execute(stmt)
            key_row = result.first()

            if key_row is None:
                raise HTTPException(status_code=404, detail="API key not found")

            key_hash = key_row[api_keys.c.key_hash]

            # Revoke key
            success = await api_key_service.revoke_api_key(key_hash)

            if not success:
                raise HTTPException(status_code=500, detail="Failed to revoke API key")

            return create_response({"message": "API key revoked successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api-tiers")
async def list_api_tiers():
    """List all service tiers."""
    try:
        async with api_key_session() as session:
            stmt = select(api_service_tiers).order_by(api_service_tiers.c.id)
            result = await session.execute(stmt)
            rows = result.all()

            tiers = []
            for row in rows:
                tiers.append(
                    {
                        "id": row[api_service_tiers.c.id],
                        "tier_name": row[api_service_tiers.c.tier_name],
                        "display_name": row[api_service_tiers.c.display_name],
                        "requests_per_minute": row[api_service_tiers.c.requests_per_minute],
                        "description": row[api_service_tiers.c.description],
                    }
                )

            return create_response({"tiers": tiers})
    except Exception as e:
        logger.error(f"Error listing API tiers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
