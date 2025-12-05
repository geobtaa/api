from typing import Optional

from fastapi import Query

from app.services.relationship_service import RelationshipService

from . import router


@router.get("/resources/{id}/relationships")
async def get_resource_relationships(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all relationships for a resource."""
    return await RelationshipService.get_resource_relationships(id)

