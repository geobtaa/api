import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.v1.utils import create_jsonapi_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def api_root(request: Request):
    """Return basic API information including version."""
    api_info = {
        "type": "api_info",
        "id": "root",
        "attributes": {
            "api": "BTAA Geospatial API",
            "version": "0.7.0",
            "description": (
                "A RESTful API that provides access to digitized maps and geospatial data "
                "resources curated by Big Ten Academic Alliance member libraries."
            ),
            "endpoints": [
                "/api/v1/",
                "/api/v1/feedback",
                "/api/v1/home/blog-posts",
                "/api/v1/search",
                "/api/v1/search/facets/{facet_name}",
                "/api/v1/suggest",
                "/api/v1/resources/",
                "/api/v1/resources/{id}",
                "/api/v1/resources/{id}/citation",
                "/api/v1/resources/{id}/citation/json-ld",
                "/api/v1/resources/{id}/citation/ris",
                "/api/v1/resources/{id}/citation/bibtex",
                "/api/v1/resources/{id}/data-dictionaries",
                "/api/v1/resources/{id}/distributions",
                "/api/v1/resources/{id}/downloads",
                "/api/v1/resources/{id}/links",
                "/api/v1/resources/{id}/metadata",
                "/api/v1/resources/{id}/metadata/ogm",
                "/api/v1/resources/{id}/metadata/b1g",
                "/api/v1/resources/{id}/metadata/display",
                "/api/v1/resources/{id}/ogm-viewer",
                "/api/v1/resources/{id}/relationships",
                "/api/v1/resources/{id}/similar-items",
                "/api/v1/resources/{id}/spatial-facets",
                "/api/v1/resources/{id}/static-map",
                "/api/v1/resources/{id}/static-map/no-cache",
                "/api/v1/resources/{id}/thumbnail",
                "/api/v1/resources/{id}/thumbnail/no-cache",
                "/api/v1/resources/{id}/viewer",
                "/api/v1/map/h3",
                "/api/v1/static-maps/institutions/{map_id}",
                "/api/v1/static-maps/{resource_id}",
                "/api/v1/thumbnails/placeholder",
                "/api/v1/thumbnails/{image_hash}",
                "/api/v1/ogm/repos",
                "/api/v1/ogm/harvest/failures",
                "/api/v1/mcp",
                "/api/v1/ogc/",
                "/api/v1/ogc/conformance",
                "/api/v1/ogc/collections",
                "/api/v1/ogc/collections/btaa-records",
                "/api/v1/ogc/collections/btaa-records/queryables",
                "/api/v1/ogc/collections/btaa-records/sortables",
                "/api/v1/ogc/collections/btaa-records/items",
                "/api/v1/ogc/collections/btaa-records/items/{recordId}",
            ],
        },
    }

    # Create JSON:API compliant response
    request_url = str(request.url)
    jsonapi_response = create_jsonapi_response(data=api_info, request_url=request_url)

    return JSONResponse(content=jsonapi_response)
