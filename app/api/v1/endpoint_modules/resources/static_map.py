from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.sql import select

from app.services.cache_service import cached_endpoint
from app.services.static_map_service import StaticMapService
from app.tasks.static_maps import generate_static_map
from db.models import resources

from . import RESOURCE_CACHE_TTL, async_session, logger, router


@router.get("/resources/{id}/static-map")
@router.get("/resources/{id}/location")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource_static_map(
    id: str,
    request: Request = None,
):
    """Get a static map image for a resource based on its locn_geometry or dcat_bbox."""
    try:
        # First check if the resource exists and has geometry
        async with async_session() as session:
            query = select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox).where(
                resources.c.id == id
            )
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = dict(row._mapping)
            # Prefer locn_geometry over dcat_bbox
            geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")

            if not geometry:
                return JSONResponse(content={"error": "Resource has no geometry"}, status_code=404)

        # Check if map already exists
        map_service = StaticMapService()
        map_path = map_service.get_map_path(id)

        if map_path and map_path.exists():
            # Return the map image (display inline in browser)
            # Remove filename parameter to prevent download, browser will display inline
            return FileResponse(
                str(map_path),
                media_type="image/png",
                headers={"Content-Disposition": "inline"},
            )

        # Map doesn't exist, trigger Celery task to generate it
        try:
            generate_static_map.delay(id)
            logger.info(f"Triggered static map generation for resource {id}")
        except Exception as e:
            logger.error(f"Error triggering static map generation for resource {id}: {e}")

        # Return 202 Accepted while map is being generated
        return JSONResponse(
            content={
                "status": "processing",
                "message": "Static map is being generated. Please try again in a few moments.",
            },
            status_code=202,
        )

    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting static map for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

