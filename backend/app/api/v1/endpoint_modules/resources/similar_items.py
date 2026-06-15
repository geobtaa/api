from typing import Optional

from fastapi import HTTPException, Query, Request
from sqlalchemy.sql import select

from app.api.schemas import ResourceSimilarItemsResponse
from app.api.v1.utils import create_response
from app.services.cache_service import cached_endpoint
from app.services.similar_items_service import SimilarItemsService
from db.models import resources

from . import RESOURCE_CACHE_TTL, async_session, logger, router


@router.get("/resources/{id}/similar-items", response_model=ResourceSimilarItemsResponse)
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource_similar_items(
    request: Request,
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get similar items for a resource."""
    try:
        # First check if the resource exists
        async with async_session() as session:
            resource_query = select(resources.c.id).where(resources.c.id == id)
            resource_result = await session.execute(resource_query)
            resource_row = resource_result.fetchone()

            if not resource_row:
                raise HTTPException(status_code=404, detail="Resource not found")

            # Get similar items
            similar_items = await SimilarItemsService.get_similar_items(id, session, limit=12)

            response_payload = {
                "id": id,
                "similar_items": similar_items,
            }

            return create_response(response_payload, callback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting similar items for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get similar items") from e
