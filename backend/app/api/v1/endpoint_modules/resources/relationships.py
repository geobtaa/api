from typing import Optional

from fastapi import HTTPException, Query

from app.api.schemas import ResourceRelationshipsResponse
from app.api.v1.utils import create_response
from app.services.relationship_service import RelationshipService

from . import logger, router


@router.get("/resources/{id}/relationships", response_model=ResourceRelationshipsResponse)
async def get_resource_relationships(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all relationships for a resource."""
    try:
        relationships = await RelationshipService.get_resource_relationships(id)

        response_payload = {
            "id": id,
            "relationships": relationships,
        }

        return create_response(response_payload, callback)
    except Exception:
        logger.error("Error getting relationships for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get relationships") from None
