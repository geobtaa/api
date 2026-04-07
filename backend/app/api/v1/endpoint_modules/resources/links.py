from typing import Optional

from fastapi import Query
from fastapi.responses import JSONResponse

from app.api.v1.utils import create_response
from app.services.link_service import LinkService

from . import logger, router


@router.get("/resources/{id}/links")
async def get_resource_links(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all links for a resource."""
    try:
        links = await LinkService.get_resource_links(id)

        response_payload = {
            "id": id,
            "links": links,
        }

        return create_response(response_payload, callback)
    except Exception:
        logger.error("Error getting links for resource %s", id, exc_info=True)
        return JSONResponse(content={"error": "Failed to get links"}, status_code=500)
