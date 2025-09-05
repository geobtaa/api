import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.image_service import ImageService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/thumbnails/placeholder")
async def get_placeholder_thumbnail():
    """Serve a placeholder thumbnail image for resources that don't have cached thumbnails yet."""
    # Create a simple SVG placeholder image
    placeholder_svg = """
    <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
        <rect width="200" height="200" fill="#f0f0f0" stroke="#cccccc" stroke-width="1"/>
        <text x="100" y="100" font-family="Arial, sans-serif" font-size="14" 
              text-anchor="middle" fill="#666666">
            Thumbnail
        </text>
        <text x="100" y="120" font-family="Arial, sans-serif" font-size="12" 
              text-anchor="middle" fill="#999999">
            Processing...
        </text>
    </svg>
    """.strip()

    return Response(
        content=placeholder_svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "X-Placeholder": "true",
        },
    )


@router.get("/thumbnails/{image_hash}")
async def get_thumbnail(image_hash: str):
    """Serve a cached thumbnail image."""
    try:
        # Create service without resource (we only need cache access)
        image_service = ImageService({})
        image_data = await image_service.get_cached_image(image_hash)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not image_data:
        raise HTTPException(status_code=404, detail="Image not found")

    return Response(
        content=image_data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000"},  # Cache for 1 year
    )
