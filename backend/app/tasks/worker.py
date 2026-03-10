import hashlib
import io
import logging
import os
from typing import Optional, Tuple

import redis
import requests
from celery import Celery
from dotenv import load_dotenv
from PIL import Image

# Load environment variables from .env file
load_dotenv()

# Setup logging
log_dir = os.getenv("LOG_PATH", "logs")
try:
    os.makedirs(log_dir, exist_ok=True)
except Exception:
    # If we can't create the directory (permissions/RO FS), fall back to stdout-only logging.
    log_dir = ""

log_handlers = [logging.StreamHandler()]
if log_dir:
    try:
        log_handlers.append(
            logging.FileHandler(os.path.join(log_dir, "app.log"), mode="a", encoding="utf-8")
        )
    except Exception:
        # If file logging is unavailable, continue with stdout-only.
        pass

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

# Setup Celery
broker_url = os.getenv(
    "CELERY_BROKER_URL",
    (
        f"redis://:{os.getenv('REDIS_PASSWORD', '')}"
        f"@{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/0"
    ),
)
result_backend = os.getenv(
    "CELERY_RESULT_BACKEND",
    (
        f"redis://:{os.getenv('REDIS_PASSWORD', '')}"
        f"@{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/1"
    ),
)

celery_app = Celery("tasks", broker=broker_url, backend=result_backend)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,  # Don't let Celery hijack the root logger
    worker_redirect_stdouts=False,  # Don't redirect stdout/stderr
    task_track_started=True,  # Track when tasks are started
    worker_send_task_events=True,  # Needed for Flower visibility
    task_send_sent_event=True,  # Show SENT state in Flower
    task_time_limit=300,  # 5 minute timeout for tasks
    task_soft_time_limit=240,  # Soft timeout 4 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time
    task_acks_late=True,  # Only acknowledge tasks after they complete
    imports=[
        "app.tasks.worker",
        "app.tasks.entities",
        "app.tasks.summarization",
        "app.tasks.ocr",
        "app.tasks.spatial_facets",
        "app.tasks.allmaps",
        "app.tasks.api_usage_enrichment",
        "app.tasks.static_maps",
        "app.tasks.ogm_harvest",
        "app.tasks.gin_blog_sync",
    ],
)

# Setup Redis for image storage
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    db=1,  # Use different DB for images
    decode_responses=False,
)


@celery_app.task(bind=True, name="fetch_and_cache_image")
def fetch_and_cache_image(self, url: str, doc_id: Optional[str] = None) -> bool:
    """
    Fetch image from URL and store in Redis.
    Invalidates search cache when thumbnail is successfully cached.
    Returns True if successful, False otherwise.

    Args:
        url: The image URL to fetch and cache
        doc_id: Optional resource ID - used for cache invalidation
    """
    logger.info(f"Starting task to fetch image: {url}")
    try:
        # Determine the actual image URL; handle IIIF manifests by resolving to a thumbnail
        resolved_url = _resolve_image_url(url)
        logger.info(f"Resolved URL: {url} -> {resolved_url}")

        # Generate cache key based on the resolved image URL (not the original manifest URL)
        image_key = f"image:{hashlib.sha256(resolved_url.encode()).hexdigest()}"

        # Check if already cached, but tolerate Redis outages
        redis_available = True
        try:
            if redis_client.exists(image_key):
                logger.info(f"Image already cached: {resolved_url}")
                return True
        except Exception as redis_err:
            redis_available = False
            logger.warning(f"Redis unavailable during exists() for {resolved_url}: {redis_err}")

        logger.info(f"Fetching image: {resolved_url}")
        # Use User-Agent header to avoid 403 errors from servers that block bots
        # Some ArcGIS ImageServer exportImage URLs can take 15-30s when server is cold
        fetch_timeout = int(os.getenv("THUMBNAIL_FETCH_TIMEOUT", "30"))
        headers = {"User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"}
        response = requests.get(resolved_url, timeout=fetch_timeout, headers=headers)

        # Don't retry non-recoverable bot-block/authorization responses.
        # - 401/403: auth
        # - 418: common bot-block response (e.g., MSU)
        if response.status_code in (401, 403, 418):
            logger.warning(
                f"Authorization error ({response.status_code}) for {resolved_url}. Not caching."
            )
            return False

        response.raise_for_status()

        # Validate that the response is actually an image
        content_type = response.headers.get("Content-Type", "")
        is_valid, detected_type = _validate_image_content(response.content, content_type)

        if not is_valid:
            logger.error(
                f"❌ Invalid image content from {resolved_url}: "
                f"Content-Type={content_type}, detected_type={detected_type}, "
                f"first_bytes={response.content[:100]!r}"
            )
            # Don't cache invalid content - return False to indicate failure
            return False

        # Cache image if Redis is available; otherwise, skip caching without retry storms
        if redis_available:
            try:
                # TODO(cache-policy): Thumbnail cache should move away from fixed TTL eviction.
                # Keep thumbnails effectively long-lived and invalidate only when:
                # 1) associated resource metadata changes in a thumbnail-affecting way, or
                # 2) an admin explicitly purges thumbnail cache entries.
                # Implementation options: resource revision in cache key, tag-based invalidation,
                # and targeted admin purge by resource ID/hash.
                ttl = int(os.getenv("REDIS_TTL", 604800))  # 7 days default
                # Store image content with detected type (prepend type as metadata)
                # We'll use a simple format: store content as-is, content type in separate key
                redis_client.setex(image_key, ttl, response.content)
                # Store content type metadata separately (optional, for faster lookups)
                type_key = f"image_type:{image_key.split(':')[1]}"
                redis_client.setex(type_key, ttl, detected_type or "image/jpeg")
                logger.info(
                    f"✅ Successfully cached valid image: {resolved_url} "
                    f"(type: {detected_type}, size: {len(response.content)} bytes)"
                )
                # Note: No need to invalidate search cache - search results always include
                # /resources/{id}/thumbnail URL, and that endpoint handles checking if
                # image is ready
                return True
            except Exception as redis_err:
                logger.warning(
                    f"Failed to cache image due to Redis error for {resolved_url}: {redis_err}"
                )
                return False
        else:
            logger.warning(f"Skipping cache store for {resolved_url}: Redis unavailable")
            return False
    except requests.RequestException as http_err:
        # Don't retry non-recoverable bot-block/authorization responses.
        if isinstance(http_err, requests.HTTPError) and hasattr(http_err.response, "status_code"):
            if http_err.response.status_code in (401, 403, 418):
                logger.warning(
                    f"Non-retryable HTTP status ({http_err.response.status_code}) "
                    f"for {url}: {http_err}. Not retrying."
                )
                return False
        logger.error(f"HTTP error caching image {url}: {http_err}")
        self.retry(exc=http_err, countdown=60, max_retries=3)
        return False
    except Exception as e:
        logger.error(f"Unexpected error caching image {url}: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)
        return False


def _looks_like_manifest_url(url: str) -> bool:
    """Heuristic to detect IIIF manifest URLs by path patterns."""
    if not url:
        return False
    lowered = url.lower()
    return (
        url.endswith(("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json"))
        or "/manifest" in url
        or (".json" in url and ("iiif" in lowered or "/object/" in url or "/collection/" in url))
        or ("/api/" in url and ("iiif" in lowered or "image" in lowered))
        or "/cgi/i/image/api/" in lowered  # U of Michigan pattern
    )


def _validate_image_content(
    content: bytes, content_type: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate that content is a valid image and return its detected MIME type.

    Args:
        content: The binary content to validate
        content_type: Optional Content-Type header from HTTP response

    Returns:
        Tuple of (is_valid, detected_mime_type)
    """
    if not content or len(content) < 4:
        return False, None

    # Check Content-Type header first (but don't trust it blindly)
    if content_type:
        content_type_lower = content_type.lower().split(";")[0].strip()
        # Reject non-image content types
        if not content_type_lower.startswith("image/"):
            logger.warning(f"Content-Type indicates non-image: {content_type}")
            return False, None

    # Check magic bytes (file signatures) for common image formats
    magic_bytes = content[:4]

    # JPEG: FF D8 FF
    if magic_bytes[:3] == b"\xff\xd8\xff":
        try:
            Image.open(io.BytesIO(content)).verify()
            return True, "image/jpeg"
        except Exception as e:
            logger.warning(f"Invalid JPEG: {e}")
            return False, None

    # PNG: 89 50 4E 47
    if magic_bytes == b"\x89PNG":
        try:
            Image.open(io.BytesIO(content)).verify()
            return True, "image/png"
        except Exception as e:
            logger.warning(f"Invalid PNG: {e}")
            return False, None

    # GIF: 47 49 46 38 (GIF8)
    if magic_bytes[:3] == b"GIF" or (len(content) > 6 and content[:6] in [b"GIF87a", b"GIF89a"]):
        try:
            Image.open(io.BytesIO(content)).verify()
            return True, "image/gif"
        except Exception as e:
            logger.warning(f"Invalid GIF: {e}")
            return False, None

    # WebP: RIFF...WEBP (check first 12 bytes)
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        try:
            Image.open(io.BytesIO(content)).verify()
            return True, "image/webp"
        except Exception as e:
            logger.warning(f"Invalid WebP: {e}")
            return False, None

    # Try PIL to validate as fallback (for other formats like TIFF, BMP, etc.)
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        # PIL can identify the format
        format_map = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "GIF": "image/gif",
            "WEBP": "image/webp",
            "TIFF": "image/tiff",
            "BMP": "image/bmp",
            "ICO": "image/x-icon",
        }
        detected_type = format_map.get(img.format, "image/jpeg")
        return True, detected_type
    except Exception as e:
        logger.warning(f"PIL validation failed: {e}")
        return False, None


COG_THUMBNAIL_PREFIX = "cog-thumb:"


def _cog_thumbnail_image_hash(cog_url: str) -> str:
    """Compute Redis cache key hash for a COG-derived thumbnail."""
    return hashlib.sha256((COG_THUMBNAIL_PREFIX + cog_url).encode()).hexdigest()


def _is_cog_url(url: str) -> bool:
    """Heuristic to detect COG (Cloud Optimized GeoTIFF) URLs."""
    if not url:
        return False
    url_lower = url.lower()
    return (
        url_lower.endswith((".tif", ".tiff"))
        or ".tif?" in url_lower
        or "geotiff" in url_lower
        or "display_raster" in url_lower
    )


def _generate_cog_thumbnail_bytes(cog_url: str) -> Optional[bytes]:
    """
    Generate PNG thumbnail bytes from a COG URL. Returns None on failure.
    Used by both the Celery task and the no-cache thumbnail endpoint.
    """
    try:
        import numpy as np
        from rio_tiler.io import Reader
        from rio_tiler.utils import linear_rescale
        from rio_tiler.utils import render as rio_render

        with Reader(cog_url) as src:
            img = src.preview(max_size=512)
            if img is None or img.data is None:
                return None

            data = img.data
            if data.dtype != "uint8":
                compressed = (
                    np.ma.compressed(data) if hasattr(data, "compressed") else data.flatten()
                )
                if len(compressed) == 0:
                    p2, p98 = 0, 255
                else:
                    p2, p98 = np.percentile(compressed, (2, 98))
                    if p2 >= p98:
                        p2, p98 = 0, 255
                data = linear_rescale(
                    np.ma.filled(data, 0) if hasattr(data, "filled") else data,
                    (float(p2), float(p98)),
                    (0, 255),
                ).astype("uint8")

            return rio_render(data, img.mask, img_format="PNG")
    except Exception as e:
        logger.warning(f"COG thumbnail generation failed for {cog_url}: {e}")
        return None


@celery_app.task(bind=True, name="generate_cog_thumbnail")
def generate_cog_thumbnail(self, cog_url: str, doc_id: Optional[str] = None) -> bool:
    """
    Generate a thumbnail from a COG URL using rio-tiler and cache in Redis.
    Returns True if successful, False otherwise.
    """
    logger.info(f"Starting COG thumbnail generation for {cog_url}")
    try:
        image_hash = _cog_thumbnail_image_hash(cog_url)
        image_key = f"image:{image_hash}"

        # Check if already cached
        try:
            if redis_client.exists(image_key):
                logger.info(f"COG thumbnail already cached for {cog_url}")
                return True
        except Exception as redis_err:
            logger.warning(f"Redis unavailable during COG cache check: {redis_err}")

        image_bytes = _generate_cog_thumbnail_bytes(cog_url)
        if not image_bytes or len(image_bytes) < 100:
            logger.error(f"COG render produced invalid output for {cog_url}")
            return False

        # Validate as image
        is_valid, _ = _validate_image_content(image_bytes, "image/png")
        if not is_valid:
            logger.error(f"COG thumbnail failed validation for {cog_url}")
            return False

        # Cache in Redis
        try:
            ttl = int(os.getenv("REDIS_TTL", 604800))
            redis_client.setex(image_key, ttl, image_bytes)
            type_key = f"image_type:{image_hash}"
            redis_client.setex(type_key, ttl, "image/png")
            logger.info(
                f"Successfully cached COG thumbnail for {cog_url} (size: {len(image_bytes)} bytes)"
            )
            return True
        except Exception as redis_err:
            logger.warning(f"Failed to cache COG thumbnail: {redis_err}")
            return False

    except Exception as e:
        logger.error(f"COG thumbnail generation failed for {cog_url}: {e}", exc_info=True)
        self.retry(exc=e, countdown=60, max_retries=2)
        return False


def _resolve_image_url(url: str) -> str:
    """Resolve the URL to an actual image URL if given a manifest; otherwise return the original."""
    try:
        # Only run manifest resolution when it looks like a manifest URL
        if _looks_like_manifest_url(url):
            from app.services.image_service import ImageService

            service = ImageService({})
            # Use service to extract thumbnail from manifest JSON
            thumb_url: Optional[str] = service.get_iiif_manifest_thumbnail(url)
            if thumb_url:
                # Standardize IIIF image URLs to consistent size
                thumb_url = service._standardize_iiif_url(thumb_url)
                return thumb_url
    except Exception as e:
        logger.warning(f"Failed to resolve manifest to image for {url}: {e}")

    # Fallback to original URL
    return url
