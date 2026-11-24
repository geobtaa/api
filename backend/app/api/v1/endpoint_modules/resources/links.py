from typing import Optional

from fastapi import HTTPException, Query
from fastapi.responses import JSONResponse

from app.api.schemas import ResourceLinksResponse
from app.api.v1.utils import create_response
from app.services.link_service import LinkService

from . import logger, router


@router.get("/resources/{id}/links", response_model=ResourceLinksResponse)
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
        raise HTTPException(status_code=500, detail="Failed to get links") from None


@router.get("/resources/{id}/geolibre/{key}.geolibre.json")
async def get_geolibre_project(id: str, key: str):
    """Open a public record's named WMS or WMTS layer as a GeoLibre project."""
    service = await LinkService.for_resource_id(id)
    project = service.get_raster_projects().get(key) if service else None
    if project is None:
        raise HTTPException(status_code=404, detail="GeoLibre project not found")
    return JSONResponse(
        project, headers={"Access-Control-Allow-Origin": "https://web.geolibre.app"}
    )
