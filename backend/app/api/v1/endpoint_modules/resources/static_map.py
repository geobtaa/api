from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.sql import select

from app.services.static_map_service import StaticMapService
from app.tasks.static_maps import generate_static_map
from db.models import resources

from . import async_session, logger, router


@router.get("/resources/{id}/static-map")
async def get_resource_static_map(
    id: str,
    request: Request = None,
):
    """Get a static map image for a resource based on its locn_geometry or dcat_bbox."""
    try:

        def _svg_placeholder(*, title: str, subtitle: str) -> Response:
            svg = f"""
            <svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
              <rect width="800" height="600" fill="#f8fafc" stroke="#e5e7eb" stroke-width="2"/>
              <text x="400" y="290" font-family="Arial, sans-serif" font-size="18"
                    text-anchor="middle" fill="#334155">{title}</text>
              <text x="400" y="325" font-family="Arial, sans-serif" font-size="14"
                    text-anchor="middle" fill="#64748b">{subtitle}</text>
            </svg>
            """.strip()
            return Response(
                content=svg,
                media_type="image/svg+xml",
                headers={
                    # Never cache placeholders; otherwise CDNs/browsers can pin “processing”.
                    "Cache-Control": "no-store",
                    "X-Placeholder": "true",
                },
            )

        # First check if the resource exists and has geometry
        async with async_session() as session:
            query = select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox).where(
                resources.c.id == id
            )
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return _svg_placeholder(title="Map unavailable", subtitle="Resource not found")

            resource_dict = dict(row._mapping)
            # Prefer locn_geometry over dcat_bbox
            geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")

            if not geometry:
                return _svg_placeholder(title="No map data", subtitle="Resource has no geometry")

        # Check if map already exists in Redis
        map_service = StaticMapService()

        if map_service.map_exists(id):
            # Map exists, redirect to the serving endpoint
            return RedirectResponse(
                url=f"/api/v1/static-maps/{id}",
                status_code=302,
                headers={
                    # Don't let caches pin the redirect response itself.
                    "Cache-Control": "no-store",
                },
            )

        # Map doesn't exist, trigger Celery task to generate it
        try:
            generate_static_map.delay(id)
            logger.info(f"Triggered static map generation for resource {id}")
        except Exception as e:
            logger.error(f"Error triggering static map generation for resource {id}: {e}")

        # Return a placeholder image while the map is being generated (never JSON to <img>).
        return _svg_placeholder(title="Generating map", subtitle="Please try again shortly")

    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting static map for resource {id}: {str(e)}", exc_info=True)
        return Response(
            content=(
                '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">'
                '<rect width="800" height="600" fill="#f8fafc" stroke="#e5e7eb" stroke-width="2"/>'
                '<text x="400" y="310" font-family="Arial, sans-serif" font-size="16" '
                'text-anchor="middle" fill="#334155">Map unavailable</text>'
                "</svg>"
            ),
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store", "X-Placeholder": "true"},
        )
