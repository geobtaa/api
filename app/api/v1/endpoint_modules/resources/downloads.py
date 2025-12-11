from typing import Optional

from fastapi import Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_response, sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.download_service import DownloadService
from db.models import resources

from . import async_session, logger, router


@router.get("/resources/{id}/downloads")
async def get_resource_downloads(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    request: Request = None,
):
    """Get the download options for a resource."""
    try:
        # Fetch resource to access metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Generate download options using DownloadService
        distribution_context = await fetch_distribution_context(id)
        download_service = DownloadService(resource_dict, distribution_context=distribution_context)
        downloads = download_service.get_download_options()

        response_payload = {
            "id": id,
            "downloads": downloads,
        }

        return create_response(response_payload, callback)
    except Exception as e:
        logger.error(f"Error getting downloads for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

