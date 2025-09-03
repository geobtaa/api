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
            "api": "GeoBTAA API",
            "version": "0.1.0",
            "description": ("API for accessing Big Ten Academic Alliance geospatial data."),
            "endpoints": [
                "/resources",
                "/resources/{id}",
                "/resources/{id}/summaries",
                "/search",
                "/suggest",
                "/thumbnails",
                "/gazetteers",
                "/gazetteers/btaa",
                "/gazetteers/geonames",
                "/gazetteers/wof",
                "/gazetteers/wof/{wok_id}",
                "/shapefiles",
            ],
        },
    }

    # Create JSON:API compliant response
    request_url = str(request.url) if request else None
    jsonapi_response = create_jsonapi_response(data=api_info, request_url=request_url)

    return JSONResponse(content=jsonapi_response)
