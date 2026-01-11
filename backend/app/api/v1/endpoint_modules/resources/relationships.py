from typing import Optional

from fastapi import Query
from fastapi.responses import JSONResponse

from app.api.v1.utils import create_response
from app.services.relationship_service import RelationshipService

from . import logger, router


@router.get("/resources/{id}/relationships")
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
    except Exception as e:
        logger.error(f"Error getting relationships for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)
