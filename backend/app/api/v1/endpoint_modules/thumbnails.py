import io
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image

from app.services.cache_service import cache_control_header, weak_etag_from_body
from app.services.image_service import ImageService
from app.services.thumbnail_alias_service import is_thumbnail_hash, thumbnail_alias_service
from app.services.thumbnail_state_service import ThumbnailState, thumbnail_state_service

logger = logging.getLogger(__name__)

router = APIRouter()

ASSET_CACHE_TTL_SECONDS = int(os.getenv("ASSET_CACHE_TTL_SECONDS", "3600"))


async def _get_resource_alias_redirect(resource_id: str) -> Response | None:
    """Redirect resource-id requests to a hot immutable asset when possible."""
    image_service = ImageService({})

    image_hash = await thumbnail_alias_service.get_hash(resource_id)
    if image_hash:
        if await image_service.has_cached_image(image_hash):
            return Response(
                status_code=302,
                headers={
                    "Location": f"/api/v1/thumbnails/{image_hash}",
                    "Cache-Control": "no-store",
                },
            )
        await thumbnail_alias_service.delete(resource_id)

    state = await thumbnail_state_service.get_state(resource_id)
    if not state:
        return None

    state_hash = state.get("source_hash")
    if state.get("state") != ThumbnailState.SUCCESS or not state_hash:
        return None

    if not await image_service.has_cached_image(state_hash):
        await thumbnail_alias_service.delete(resource_id)
        return None

    await thumbnail_alias_service.set_hash(resource_id, state_hash)
    return Response(
        status_code=302,
        headers={
            "Location": f"/api/v1/thumbnails/{state_hash}",
            "Cache-Control": "no-store",
        },
    )


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
    is_gif = magic_bytes[:3] == b"GIF" or (
        len(image_data) > 6 and image_data[:6] in [b"GIF87a", b"GIF89a"]
    )
    if is_gif:
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
            # Placeholders must not be cached aggressively or clients/CDNs can get pinned.
            "Cache-Control": "no-store",
            "X-Placeholder": "true",
        },
    )


@router.get("/thumbnails/{resource_id}")
async def get_thumbnail(resource_id: str, request: Request):
    """Serve a resource thumbnail asset with a guaranteed image fallback."""
    if not is_thumbnail_hash(resource_id):
        redirect = await _get_resource_alias_redirect(resource_id)
        if redirect is not None:
            return redirect

    try:
        # Create service without resource (we only need cache access)
        image_service = ImageService({})
        image_data = await image_service.get_cached_image(resource_id)
    except Exception as e:
        logger.error(f"Error retrieving cached image {resource_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not image_data:
        if is_thumbnail_hash(resource_id):
            raise HTTPException(status_code=404, detail="Thumbnail asset not found")

        from app.api.v1.endpoint_modules.resources.thumbnail import (
            _get_resource_thumbnail_response,
        )

        try:
            return await _get_resource_thumbnail_response(
                resource_id,
                request,
                variant="icon-gradient",
                not_found_placeholder=False,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving resource thumbnail asset {resource_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    # Validate that the cached content is actually an image
    try:
        # Try to verify it's a valid image
        img = Image.open(io.BytesIO(image_data))
        img.verify()
    except Exception as e:
        logger.error(
            f"❌ Cached content for {resource_id} is not a valid image: {e}. "
            f"First 200 bytes: {image_data[:200]!r}"
        )
        # Return 404 for invalid cached content (should have been caught during caching)
        raise HTTPException(
            status_code=404,
            detail="Invalid image data in cache. This may indicate corrupted cache entry.",
        ) from None

    # Detect the actual image type
    content_type = _detect_image_type(image_data)

    etag = weak_etag_from_body(image_data)
    headers = {
        "ETag": etag,
        "Cache-Control": cache_control_header(ttl_seconds=ASSET_CACHE_TTL_SECONDS),
        # If anything ends up being compressed, this avoids representation mixups.
        "Vary": "Accept-Encoding",
    }

    inm = request.headers.get("if-none-match")
    if inm and inm == etag:
        return Response(status_code=304, headers=headers)

    return Response(
        content=image_data,
        media_type=content_type,
        headers=headers,
    )
