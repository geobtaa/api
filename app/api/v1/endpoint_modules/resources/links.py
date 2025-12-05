from typing import Optional

from fastapi import Query

from app.services.link_service import LinkService

from . import router


@router.get("/resources/{id}/links")
async def get_resource_links(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all links for a resource."""
    return await LinkService.get_resource_links(id)

