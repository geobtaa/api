import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def api_root():
    """Return basic API information including version."""
    return JSONResponse(
        content={
            "api": "GeoBTAA API",
            "version": "0.1.0",
            "description": (
                "API for accessing Big Ten Academic Alliance geospatial data."
            ),
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

        }
    )
