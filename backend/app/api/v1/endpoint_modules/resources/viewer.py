from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_response, sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.viewer_service import ViewerService
from db.models import resources

from . import async_session, logger, router


@router.get("/resources/{id}/viewer")
async def get_resource_viewer_data(
    request: Request,
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get the viewer data for a resource."""
    try:
        # Fetch resource to access metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                # Align with tests: return 404 with {"detail": "Resource not found"}
                raise HTTPException(status_code=404, detail="Resource not found")

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Generate viewer attributes using ViewerService
        distribution_context = await fetch_distribution_context(id)
        viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
        viewer_attributes = viewer_service.get_viewer_attributes()

        # Structure viewer data in the same format as meta.ui.viewer
        viewer_data = {}
        if viewer_attributes.get("ui_viewer_protocol"):
            viewer_data["protocol"] = viewer_attributes["ui_viewer_protocol"]
        if viewer_attributes.get("ui_viewer_endpoint"):
            viewer_data["endpoint"] = viewer_attributes["ui_viewer_endpoint"]
        if viewer_attributes.get("ui_viewer_geometry"):
            viewer_data["geometry"] = viewer_attributes["ui_viewer_geometry"]

        response_payload = {
            "id": id,
            "viewer": viewer_data if viewer_data else None,
        }

        return create_response(response_payload, callback)
    except Exception as e:
        logger.error(f"Error getting viewer data for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)
