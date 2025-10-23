import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.v1.utils import create_jsonapi_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def api_root(request: Request = None):
    """Return basic API information including version."""
    api_info = {
        "type": "api_info",
        "id": "root",
        "attributes": {
            "api": "BTAA Geospatial API",
            "version": "0.2.0",
            "description": ("API for accessing BTAA Geospatial data."),
            "endpoints": [
                "/",
                "/search",
                "/suggest",
                "/resources",
                "/resources/{id}",
                "/resources/{id}/distributions",
                "/resources/{id}/links",
                "/resources/{id}/ogm",
                "/resources/{id}/relationships",
                "/resources/{id}/spatial_facets",
                "/resources/{id}/summaries",
                "/resources/{id}/viewer",
                "/thumbnails/placeholder",
                "/thumbnails/{image_hash}",
                "/mcp",
                "/gazetteers",
                "/gazetteers/search",
                "/gazetteers/btaa/search",
                "/gazetteers/geonames/search",
                "/gazetteers/wof/search",
                "/shapefiles/query",
                "/shapefiles/schema",
                "/shapefiles/preview"
            ],
        },
    }

    # Create JSON:API compliant response
    request_url = str(request.url) if request else None
    jsonapi_response = create_jsonapi_response(data=api_info, request_url=request_url)

    return JSONResponse(content=jsonapi_response)
