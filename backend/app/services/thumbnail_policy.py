"""Shared thumbnail output policy; all writers and readers use these limits."""

import hashlib
import io
import json
import logging
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()
logger = logging.getLogger(__name__)
THUMBNAIL_CACHE_VERSION = os.getenv("THUMBNAIL_CACHE_VERSION", "v5")
THUMBNAIL_MAX_EDGE = int(os.getenv("THUMBNAIL_MAX_EDGE", "512"))
THUMBNAIL_MAX_BYTES = 512 * 1024
THUMBNAIL_JPEG_QUALITY = int(os.getenv("THUMBNAIL_JPEG_QUALITY", "78"))
IIIF_THUMBNAIL_BOX = os.getenv("IIIF_THUMBNAIL_BOX", "!800,800")


def source_signature(source_url: str) -> str:
    """A lookup key, never an immutable asset identifier.

    The original manifest URL is intentionally sufficient: successful resolution
    is persisted, so cache eviction never requires contacting the provider again.
    Force refresh explicitly re-resolves changed remote manifests.
    """
    policy = [
        "thumbnail-content-v1",
        THUMBNAIL_CACHE_VERSION,
        THUMBNAIL_MAX_EDGE,
        THUMBNAIL_MAX_BYTES,
        THUMBNAIL_JPEG_QUALITY,
        IIIF_THUMBNAIL_BOX,
        source_url,
    ]
    return hashlib.sha256(json.dumps(policy, separators=(",", ":")).encode()).hexdigest()


def valid_thumbnail(content: bytes, image_hash: str) -> bool:
    """Check restored bytes, not just presence or an image MIME label."""
    if not isinstance(content, bytes) or not content or len(content) > THUMBNAIL_MAX_BYTES:
        return False
    if hashlib.sha256(content).hexdigest() != image_hash:
        return False
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"} or max(image.size) > THUMBNAIL_MAX_EDGE:
                return False
            image.load()
        return True
    except Exception:
        return False


def _image_has_alpha(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        return True
    if img.mode == "P":
        return "transparency" in img.info
    return False


def normalize_thumbnail_image(
    content: bytes, content_type: Optional[str] = None
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Normalize thumbnail image bytes for delivery.

    - auto-orients based on EXIF
    - constrains the longest edge to THUMBNAIL_MAX_EDGE
    - strips metadata by re-encoding
    - re-compresses to bounded delivery formats
    """
    if not content:
        return None, None

    try:
        with Image.open(io.BytesIO(content)) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened)

        has_alpha = _image_has_alpha(image)
        normalized_content_type = (content_type or "").lower().split(";")[0].strip()
        if has_alpha:
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")

        image.info.clear()
        if max(image.size) > THUMBNAIL_MAX_EDGE:
            image.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.Resampling.LANCZOS)

        # Detailed or transparent PNGs can exceed the delivery budget even at
        # the pixel limit. Reduce dimensions until encoding fits; keep alpha.
        while True:
            output = io.BytesIO()
            if has_alpha or normalized_content_type == "image/png":
                image.save(output, format="PNG", optimize=True, compress_level=9)
                normalized_type = "image/png"
            else:
                image.save(
                    output,
                    format="JPEG",
                    quality=THUMBNAIL_JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                normalized_type = "image/jpeg"

            normalized = output.getvalue()
            if normalized and len(normalized) <= THUMBNAIL_MAX_BYTES:
                return normalized, normalized_type
            if max(image.size) <= 1:
                return None, None
            edge = max(1, int(max(image.size) * 0.8))
            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    except Exception as exc:
        logger.warning(
            "Thumbnail normalization failed (content_type=%s): %s",
            content_type,
            exc,
        )
        return None, None
