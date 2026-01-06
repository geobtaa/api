import io
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image

from app.services.static_map_service import StaticMapService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/static-maps/{resource_id}")
async def get_static_map(resource_id: str):
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

    return Response(
        content=map_data,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
            "Content-Disposition": "inline",  # Display inline in browser
        },
    )

