import html
import os
from urllib.parse import quote

from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.sql import select

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

        # Build the record URL for the viewer
        base_url = os.getenv("APPLICATION_URL", "http://localhost:8000")
        record_url = f"{base_url}/api/v1/resources/{quote(id, safe='')}/metadata/ogm"
        escaped_record_url = html.escape(record_url, quote=True)
        escaped_id = html.escape(id)

        # Create the HTML content
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGM Viewer - Resource {escaped_id}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .viewer-container {{
            width: 100vw;
            height: 100vh;
        }}
        {".viewer-container { height: 600px; }" if embed else ""}
    </style>
</head>
<body>
    <div class="viewer-container">
        <ogm-viewer 
            record-url="{escaped_record_url}"
            >
        </ogm-viewer>
    </div>
    
    <!-- Load the OGM Viewer web component -->
    <script type="module" src="https://unpkg.com/ogm-viewer"></script>
</body>
</html>
"""

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
