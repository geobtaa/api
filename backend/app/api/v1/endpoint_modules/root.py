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
            "version": "0.3.0-pre-alpha",
            "description": (
                "A RESTful API for accessing digitized maps and geospatial data resources "
                "from Big Ten Academic Alliance member libraries."
            ),
            "endpoints": [
                "/",
                "/search",
                "/search/facets/{facet_name}",
                "/suggest",
                "/resources",
                "/resources/{id}",
                "/resources/{id}/citation",
                "/resources/{id}/distributions",
                "/resources/{id}/downloads",
                "/resources/{id}/links",
                "/resources/{id}/location",
                "/resources/{id}/metadata",
                "/resources/{id}/metadata/ogm",
                "/resources/{id}/metadata/b1g",
                "/resources/{id}/ogm-viewer",
                "/resources/{id}/relationships",
                "/resources/{id}/similar-items",
                "/resources/{id}/spatial-facets",
                "/resources/{id}/static-map",
                "/resources/{id}/thumbnail",
                "/resources/{id}/viewer",
                "/thumbnails/placeholder",
                "/thumbnails/{image_hash}",
                "/map/h3",
                "/mcp",
            ],
        },
    }

    # Create JSON:API compliant response
    request_url = str(request.url) if request else None
    jsonapi_response = create_jsonapi_response(data=api_info, request_url=request_url)

    return JSONResponse(content=jsonapi_response)
