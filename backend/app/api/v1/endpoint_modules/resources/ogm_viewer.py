import os

from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.sql import select

from app.services.viewer_html import resource_viewer_html
from db.models import resources

from . import get_async_session, logger, router


@router.get("/resources/{id}/ogm-viewer", response_class=HTMLResponse)
async def get_resource_viewer(
    id: str,
    embed: bool = Query(False, description="Embedded mode for iframe usage"),
):
    """Get an HTML page with the embedded OGM viewer for a specific resource."""
    try:
        # First check if the resource exists
        async with get_async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Resource not found")

        base_url = os.getenv("APPLICATION_URL", "http://localhost:8000")
        html_content = resource_viewer_html(base_url, id, embed)

        # Create response with iframe-friendly headers
        response = HTMLResponse(content=html_content)

        # Allow iframe embedding from any domain
        response.headers["X-Frame-Options"] = "ALLOWALL"
        response.headers["Content-Security-Policy"] = "frame-ancestors *"

        # Use credentialless COEP for maximum compatibility with parent pages
        # This allows embedding in pages with strict COEP policies
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"

        return response
    except HTTPException:
        # Re-raise HTTPExceptions (like 404) without modification
        raise
    except Exception as e:
        logger.error(f"Error creating viewer page for resource {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create viewer page") from e
