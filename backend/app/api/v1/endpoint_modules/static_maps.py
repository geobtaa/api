import io
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image

from app.services.cache_service import cache_control_header, weak_etag_from_body
from app.services.static_map_service import StaticMapService

logger = logging.getLogger(__name__)

router = APIRouter()

ASSET_CACHE_TTL_SECONDS = int(os.getenv("ASSET_CACHE_TTL_SECONDS", "3600"))


@router.get("/static-maps/{resource_id}")
async def get_static_map(resource_id: str, request: Request):
    """Serve a cached static map image from Redis."""
    try:
        map_service = StaticMapService()
        map_data = await map_service.get_cached_map(resource_id)
    except Exception as e:
        logger.error(f"Error retrieving cached static map {resource_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not map_data:
        raise HTTPException(status_code=404, detail="Static map not found")

    # Validate that the cached content is actually a valid PNG image
    try:
        img = Image.open(io.BytesIO(map_data))
        img.verify()
    except Exception as e:
        logger.error(
            f"❌ Cached content for {resource_id} is not a valid image: {e}. "
            f"First 200 bytes: {map_data[:200]!r}"
        )
        raise HTTPException(
            status_code=404,
            detail="Invalid image data in cache. This may indicate corrupted cache entry.",
        ) from None

    etag = weak_etag_from_body(map_data)
    headers = {
        "ETag": etag,
        "Cache-Control": cache_control_header(ttl_seconds=ASSET_CACHE_TTL_SECONDS),
        "Content-Disposition": "inline",
        "Vary": "Accept-Encoding",
    }

    inm = request.headers.get("if-none-match")
    if inm and inm == etag:
        return Response(status_code=304, headers=headers)

    return Response(
        content=map_data,
        media_type="image/png",
        headers=headers,
    )
