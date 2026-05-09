import io
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image

from app.services.cache_service import (
    alias_redirect_cache_control_header,
    cache_control_header,
    immutable_asset_cache_control_header,
    weak_etag_from_body,
)
from app.services.image_service import ImageService
from app.services.thumbnail_alias_service import is_thumbnail_hash, thumbnail_alias_service
from app.services.thumbnail_state_service import ThumbnailState, thumbnail_state_service

logger = logging.getLogger(__name__)

router = APIRouter()

ASSET_CACHE_TTL_SECONDS = int(os.getenv("ASSET_CACHE_TTL_SECONDS", "3600"))


async def _get_resource_alias_redirect(resource_id: str) -> Response | None:
    """Redirect resource-id requests to a hot immutable asset when possible."""
    image_hash = await thumbnail_alias_service.get_hash(resource_id)
    if image_hash:
        if not await _thumbnail_hash_has_cached_image(image_hash):
            await thumbnail_alias_service.delete(resource_id)
            image_hash = None

    if not image_hash:
        state = await thumbnail_state_service.get_state(resource_id)
        if not state:
            return None

        state_hash = state.get("source_hash")
        if (
            state.get("state") != ThumbnailState.SUCCESS
            or not state_hash
            or not is_thumbnail_hash(str(state_hash))
        ):
            return None

        image_hash = str(state_hash)
        if not await _thumbnail_hash_has_cached_image(image_hash):
            return None
        await thumbnail_alias_service.set_hash(resource_id, image_hash)

    return Response(
        status_code=302,
        headers={
            "Location": f"/api/v1/thumbnails/{image_hash}",
            "Cache-Control": alias_redirect_cache_control_header(),
        },
    )


async def _thumbnail_hash_has_cached_image(image_hash: str) -> bool:
    """Return True only when an immutable thumbnail hash resolves to image bytes."""
    if not is_thumbnail_hash(image_hash):
        return False
    try:
        return await ImageService({}).has_cached_image(image_hash)
    except Exception as exc:
        logger.debug("Failed checking thumbnail hash %s: %s", image_hash, exc)
        return False


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

    # The endpoint validates the decoded image once before this MIME sniff.
    # Avoid a second PIL decode on every hot immutable asset response.
    # JPEG: FF D8 FF
    if magic_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"

    # PNG: 89 50 4E 47
    if magic_bytes == b"\x89PNG":
        return "image/png"

    # GIF: 47 49 46 38 (GIF8)
    is_gif = magic_bytes[:3] == b"GIF" or (
        len(image_data) > 6 and image_data[:6] in [b"GIF87a", b"GIF89a"]
    )
    if is_gif:
        return "image/gif"

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
    """Serve a neutral thumbnail placeholder image."""
    placeholder_svg = """
    <svg width="200" height="200" viewBox="0 0 200 200"
         xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Thumbnail placeholder">
        <title>Thumbnail placeholder</title>
        <rect width="200" height="200" fill="#f8fafc" stroke="#e5e7eb" stroke-width="1"/>
        <rect x="54" y="58" width="92" height="84" rx="8" fill="#e2e8f0"/>
        <path d="M68 122L88 96L104 114L116 100L134 122H68Z" fill="#94a3b8"/>
        <circle cx="122" cy="82" r="10" fill="#94a3b8"/>
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
    """Serve a thumbnail asset or resolve a resource-id thumbnail fallback."""
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
            return Response(status_code=404, headers={"Cache-Control": "no-store"})

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
    cache_control = (
        immutable_asset_cache_control_header()
        if is_thumbnail_hash(resource_id)
        else cache_control_header(ttl_seconds=ASSET_CACHE_TTL_SECONDS)
    )
    headers = {
        "ETag": etag,
        "Cache-Control": cache_control,
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
