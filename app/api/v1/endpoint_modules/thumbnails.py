import io
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image

from app.services.image_service import ImageService

logger = logging.getLogger(__name__)

router = APIRouter()


def _detect_image_type(image_data: bytes) -> str:
    """
    Detect the MIME type of image data by examining its content.
    
    Args:
        image_data: The binary image data
        
    Returns:
        MIME type string (defaults to 'image/jpeg' if detection fails)
    """
    if not image_data or len(image_data) < 4:
        return "image/jpeg"
    
    # Check magic bytes first
    magic_bytes = image_data[:4]
    
    # JPEG: FF D8 FF
    if magic_bytes[:3] == b"\xff\xd8\xff":
        try:
            Image.open(io.BytesIO(image_data)).verify()
            return "image/jpeg"
        except Exception:
            pass
    
    # PNG: 89 50 4E 47
    if magic_bytes == b"\x89PNG":
        try:
            Image.open(io.BytesIO(image_data)).verify()
            return "image/png"
        except Exception:
            pass
    
    # GIF: 47 49 46 38 (GIF8)
    if magic_bytes[:3] == b"GIF" or (len(image_data) > 6 and image_data[:6] in [b"GIF87a", b"GIF89a"]):
        try:
            Image.open(io.BytesIO(image_data)).verify()
            return "image/gif"
        except Exception:
            pass
    
    # WebP: RIFF...WEBP
    if len(image_data) >= 12 and image_data[:4] == b"RIFF" and image_data[8:12] == b"WEBP":
        try:
            Image.open(io.BytesIO(image_data)).verify()
            return "image/webp"
        except Exception:
            pass
    
    # Try PIL as fallback
    try:
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        format_map = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "GIF": "image/gif",
            "WEBP": "image/webp",
            "TIFF": "image/tiff",
            "BMP": "image/bmp",
            "ICO": "image/x-icon",
        }
        return format_map.get(img.format, "image/jpeg")
    except Exception:
        pass
    
    # Default fallback
    return "image/jpeg"


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
        logger.error(f"Error retrieving cached image {image_hash}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not image_data:
        raise HTTPException(status_code=404, detail="Image not found")

    # Validate that the cached content is actually an image
    try:
        # Try to verify it's a valid image
        img = Image.open(io.BytesIO(image_data))
        img.verify()
    except Exception as e:
        logger.error(
            f"❌ Cached content for {image_hash} is not a valid image: {e}. "
            f"First 200 bytes: {image_data[:200]!r}"
        )
        # Return 404 for invalid cached content (should have been caught during caching)
        raise HTTPException(
            status_code=404,
            detail="Invalid image data in cache. This may indicate corrupted cache entry."
        )

    # Detect the actual image type
    content_type = _detect_image_type(image_data)

    return Response(
        content=image_data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000"},  # Cache for 1 year
    )
