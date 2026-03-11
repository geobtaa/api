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

from app.services.provider_throttle import provider_request_slot
from app.services.thumbnail_queue_service import release_thumbnail_queue_slot
from app.services.thumbnail_state_service import (
    ThumbnailState,
    ThumbnailStatePayload,
    infer_source_type,
    safe_record_thumbnail_state_sync,
)

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


def _record_thumbnail_state(
    resource_id: Optional[str],
    *,
    state: str,
    source_type: str | None,
    source_url: str | None,
    source_hash: str | None,
    queue_task_id: str | None = None,
    state_detail: str | None = None,
    last_error: str | None = None,
) -> None:
    if not resource_id:
        return
    safe_record_thumbnail_state_sync(
        ThumbnailStatePayload(
            resource_id=resource_id,
            state=state,
            source_type=source_type,
            source_url=source_url,
            source_hash=source_hash,
            queue_task_id=queue_task_id,
            state_detail=state_detail,
            last_error=last_error,
        )
    )


def _is_terminal_retry(self, status_code: int | None = None) -> bool:
    if status_code in (401, 403, 404, 418):
        return True
    max_retries = getattr(self, "max_retries", None)
    current_retries = getattr(getattr(self, "request", None), "retries", 0)
    return max_retries is not None and current_retries >= max_retries


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
        source_type = infer_source_type(url)
        # Determine the actual image URL; handle IIIF manifests by resolving to a thumbnail
        resolved_url = _resolve_image_url(url)
        logger.info(f"Resolved URL: {url} -> {resolved_url}")

        # Generate cache key based on the resolved image URL (not the original manifest URL)
        source_hash = hashlib.sha256(resolved_url.encode()).hexdigest()
        image_key = f"image:{source_hash}"

        # Check if already cached, but tolerate Redis outages
        redis_available = True
        try:
            if redis_client.exists(image_key):
                logger.info(f"Image already cached: {resolved_url}")
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.SUCCESS,
                    source_type=source_type,
                    source_url=url,
                    source_hash=source_hash,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail="Thumbnail already cached",
                )
                return True
        except Exception as redis_err:
            redis_available = False
            logger.warning(f"Redis unavailable during exists() for {resolved_url}: {redis_err}")

        logger.info(f"Fetching image: {resolved_url}")
        # Use User-Agent header to avoid 403 errors from servers that block bots
        # Some ArcGIS ImageServer exportImage URLs can take 15-30s when server is cold
        fetch_timeout = int(os.getenv("THUMBNAIL_FETCH_TIMEOUT", "30"))
        headers = {"User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"}
        with provider_request_slot(resolved_url, action="thumbnail fetch") as lease:
            response = requests.get(resolved_url, timeout=fetch_timeout, headers=headers)

        # Don't retry non-recoverable bot-block/authorization responses.
        # - 401/403: auth
        # - 418: common bot-block response (e.g., MSU)
        if response.status_code in (401, 403, 418):
            logger.warning(
                f"Authorization error ({response.status_code}) for {resolved_url}. Not caching."
            )
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type=source_type,
                source_url=url,
                source_hash=source_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail=f"Non-retryable HTTP status {response.status_code}",
                last_error=f"HTTP {response.status_code} from {resolved_url}",
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
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type=source_type,
                source_url=url,
                source_hash=source_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Invalid image content",
                last_error=f"Invalid image content from {resolved_url}",
            )
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
                detail = "Cached thumbnail successfully"
                if lease.waited_seconds > 0:
                    detail = f"{detail}; provider pacing waited {lease.waited_seconds:.2f}s"
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.SUCCESS,
                    source_type=source_type,
                    source_url=url,
                    source_hash=source_hash,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail=detail,
                )
                return True
            except Exception as redis_err:
                logger.warning(
                    f"Failed to cache image due to Redis error for {resolved_url}: {redis_err}"
                )
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.FAILURE,
                    source_type=source_type,
                    source_url=url,
                    source_hash=source_hash,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail="Redis cache write failed",
                    last_error=str(redis_err),
                )
                return False
        else:
            logger.warning(f"Skipping cache store for {resolved_url}: Redis unavailable")
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type=source_type,
                source_url=url,
                source_hash=source_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Redis unavailable during cache store",
                last_error="Redis unavailable during cache store",
            )
            return False
    except requests.RequestException as http_err:
        # Don't retry non-recoverable bot-block/authorization responses.
        if isinstance(http_err, requests.HTTPError) and hasattr(http_err.response, "status_code"):
            if http_err.response.status_code in (401, 403, 418):
                logger.warning(
                    f"Non-retryable HTTP status ({http_err.response.status_code}) "
                    f"for {url}: {http_err}. Not retrying."
                )
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.FAILURE,
                    source_type=infer_source_type(url),
                    source_url=url,
                    source_hash=None,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail="Non-retryable HTTP error",
                    last_error=str(http_err),
                )
                return False
            if _is_terminal_retry(self, http_err.response.status_code):
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.FAILURE,
                    source_type=infer_source_type(url),
                    source_url=url,
                    source_hash=None,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail="Exhausted retries after HTTP error",
                    last_error=str(http_err),
                )
        logger.error(f"HTTP error caching image {url}: {http_err}")
        self.retry(exc=http_err, countdown=60, max_retries=3)
        return False
    except Exception as e:
        if _is_terminal_retry(self):
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type=infer_source_type(url),
                source_url=url,
                source_hash=None,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Exhausted retries after unexpected error",
                last_error=str(e),
            )
        logger.error(f"Unexpected error caching image {url}: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)
        return False
    finally:
        release_thumbnail_queue_slot(doc_id, url)


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
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.SUCCESS,
                    source_type="cog",
                    source_url=cog_url,
                    source_hash=image_hash,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail="COG thumbnail already cached",
                )
                return True
        except Exception as redis_err:
            logger.warning(f"Redis unavailable during COG cache check: {redis_err}")

        with provider_request_slot(cog_url, action="COG thumbnail generation") as lease:
            image_bytes = _generate_cog_thumbnail_bytes(cog_url)
        if not image_bytes or len(image_bytes) < 100:
            logger.error(f"COG render produced invalid output for {cog_url}")
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type="cog",
                source_url=cog_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="COG render returned no image",
                last_error="COG render produced invalid output",
            )
            return False

        # Validate as image
        is_valid, _ = _validate_image_content(image_bytes, "image/png")
        if not is_valid:
            logger.error(f"COG thumbnail failed validation for {cog_url}")
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type="cog",
                source_url=cog_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="COG thumbnail failed validation",
                last_error="COG thumbnail failed validation",
            )
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
            detail = "Cached COG thumbnail successfully"
            if lease.waited_seconds > 0:
                detail = f"{detail}; provider pacing waited {lease.waited_seconds:.2f}s"
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.SUCCESS,
                source_type="cog",
                source_url=cog_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail=detail,
            )
            return True
        except Exception as redis_err:
            logger.warning(f"Failed to cache COG thumbnail: {redis_err}")
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type="cog",
                source_url=cog_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Failed to cache COG thumbnail",
                last_error=str(redis_err),
            )
            return False

    except Exception as e:
        if _is_terminal_retry(self):
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type="cog",
                source_url=cog_url,
                source_hash=None,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Exhausted retries for COG thumbnail generation",
                last_error=str(e),
            )
        logger.error(f"COG thumbnail generation failed for {cog_url}: {e}", exc_info=True)
        self.retry(exc=e, countdown=60, max_retries=2)
        return False
    finally:
        release_thumbnail_queue_slot(doc_id, cog_url)


PMTILES_THUMBNAIL_PREFIX = "pmtiles-thumb:"


def _pmtiles_thumbnail_image_hash(pmtiles_url: str) -> str:
    """Compute Redis cache key hash for a PMTiles-derived thumbnail."""
    return hashlib.sha256((PMTILES_THUMBNAIL_PREFIX + pmtiles_url).encode()).hexdigest()


def _is_pmtiles_url(url: str) -> bool:
    """Heuristic to detect PMTiles URLs."""
    if not url:
        return False
    url_lower = url.lower()
    return url_lower.endswith(".pmtiles") or ".pmtiles?" in url_lower


def _http_get_bytes(url: str):
    """Return a get_bytes(offset, length) function for PMTiles Reader using HTTP range requests."""

    def get_bytes(offset: int, length: int) -> bytes:
        # Request extra bytes for small ranges: some servers (e.g. pmtiles.io CDN)
        # truncate short Range responses. PMTiles needs full header (127+ bytes).
        fetch_len = max(length, 512)
        end = offset + fetch_len - 1
        headers = {
            "User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)",
            "Range": f"bytes={offset}-{end}",
            # Avoid gzip: range of gzip stream is not independently decompressible.
            "Accept-Encoding": "identity",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.content
        return data[:length] if len(data) >= length else data

    return get_bytes


def _lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    """Convert WGS84 lon/lat to web mercator tile x,y at given zoom."""
    import math

    n = 1 << zoom
    x = int((lon + 180.0) / 360.0 * n) % n
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    y = max(0, min(y, n - 1))
    return x, y


def _extract_mvt_points(geom: dict) -> list[tuple[float, float]]:
    """Extract all (x, y) points from an MVT geometry for bbox calculation."""
    pts: list[tuple[float, float]] = []
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return pts
    if gtype == "Point":
        pts.append((coords[0], coords[1]))
    elif gtype == "LineString":
        pts.extend((p[0], p[1]) for p in coords)
    elif gtype == "Polygon":
        for ring in coords:
            pts.extend((p[0], p[1]) for p in ring)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                pts.extend((p[0], p[1]) for p in ring)
    return pts


def _render_mvt_to_png(mvt_bytes: bytes, z: int, x: int, y: int) -> Optional[bytes]:
    """Render MVT tile bytes to PNG. Fits geometry to frame, centered."""
    try:
        import mapbox_vector_tile

        decoded = mapbox_vector_tile.decode(mvt_bytes)
        if not decoded:
            return None

        extent = 4096  # MVT default extent
        base_size = 256
        render_size = 512

        # Collect all points to compute bounding box
        all_pts: list[tuple[float, float]] = []
        for layer_data in decoded.values():
            for feat in layer_data.get("features") or []:
                geom = feat.get("geometry")
                if geom:
                    all_pts.extend(_extract_mvt_points(geom))

        if not all_pts:
            return None

        min_x = min(p[0] for p in all_pts)
        max_x = max(p[0] for p in all_pts)
        min_y = min(p[1] for p in all_pts)
        max_y = max(p[1] for p in all_pts)

        bbox_w = max(max_x - min_x, 1.0)
        bbox_h = max(max_y - min_y, 1.0)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        # Scale to fill ~90% of frame, centered
        pad = 0.05
        avail = render_size * (1 - 2 * pad)
        scale = (avail / max(bbox_w, bbox_h)) if max(bbox_w, bbox_h) > 0 else 1.0
        ox = render_size / 2 - center_x * scale
        oy = render_size / 2 - (extent - center_y) * scale  # Y flip for display

        def to_px(px: float, py: float) -> tuple[int, int]:
            sx = int(px * scale + ox)
            sy = int((extent - py) * scale + oy)
            return sx, sy

        bg = (248, 250, 252, 255)
        img = Image.new("RGBA", (render_size, render_size), bg)
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        fill = (59, 130, 246, 160)
        outline = (37, 99, 235, 255)

        for _layer_name, layer_data in decoded.items():
            features = layer_data.get("features") or []
            for feat in features:
                geom = feat.get("geometry")
                if not geom:
                    continue
                gtype = geom.get("type")
                coords = geom.get("coordinates")
                if not coords:
                    continue
                if gtype == "Point":
                    sx, sy = to_px(coords[0], coords[1])
                    r = 4
                    draw.ellipse(
                        [sx - r, sy - r, sx + r, sy + r],
                        fill=fill,
                        outline=outline,
                    )
                elif gtype == "LineString":
                    points = [to_px(p[0], p[1]) for p in coords]
                    if len(points) >= 2:
                        draw.line(points, fill=outline, width=3)
                elif gtype == "Polygon":
                    for ring in coords:
                        points = [to_px(p[0], p[1]) for p in ring]
                        if len(points) >= 3:
                            draw.polygon(points, fill=fill, outline=outline)
                elif gtype == "MultiPolygon":
                    for poly in coords:
                        for ring in poly:
                            points = [to_px(p[0], p[1]) for p in ring]
                            if len(points) >= 3:
                                draw.polygon(points, fill=fill, outline=outline)

        img = img.resize((base_size, base_size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.debug(f"MVT render failed: {e}")
    return None


def _generate_pmtiles_thumbnail_bytes(pmtiles_url: str) -> Optional[bytes]:
    """
    Generate PNG thumbnail bytes from a PMTiles URL. Returns None on failure.
    Supports raster (PNG/JPEG/WebP) and vector (MVT) tiles; MVT is rendered to PNG.
    """
    try:
        from pmtiles.reader import Reader
        from pmtiles.tile import Compression, TileType

        get_bytes = _http_get_bytes(pmtiles_url)
        reader = Reader(get_bytes)
        header = reader.header()

        # Tile type: 0=Unknown, 1=MVT, 2=PNG, 3=JPEG, 4=WebP
        tile_type = header.get("tile_type") or header.get("tileType")
        if hasattr(tile_type, "value"):
            tile_type_val = tile_type.value
        else:
            tile_type_val = int(tile_type) if tile_type is not None else 0
        min_zoom = header.get("min_zoom", 0) or header.get("minZoom", 0)
        max_zoom = header.get("max_zoom", 14) or header.get("maxZoom", 14)

        # Pick zoom and tile inside data bounds
        zoom = min(max(min_zoom, 4), max_zoom) if max_zoom >= min_zoom else min_zoom
        min_lon_e7 = header.get("min_lon_e7", int(-180 * 1e7))
        min_lat_e7 = header.get("min_lat_e7", int(-90 * 1e7))
        max_lon_e7 = header.get("max_lon_e7", int(180 * 1e7))
        max_lat_e7 = header.get("max_lat_e7", int(90 * 1e7))
        center_lon = (min_lon_e7 + max_lon_e7) / 2.0 / 1e7
        center_lat = (min_lat_e7 + max_lat_e7) / 2.0 / 1e7
        x, y = _lonlat_to_tile(center_lon, center_lat, zoom)

        tile_data = reader.get(zoom, x, y)
        if not tile_data or len(tile_data) < 10:
            for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
                xi = max(0, min(x + dx, (1 << zoom) - 1))
                yi = max(0, min(y + dy, (1 << zoom) - 1))
                tile_data = reader.get(zoom, xi, yi)
                if tile_data and len(tile_data) >= 10:
                    x, y = xi, yi
                    break
        if not tile_data or len(tile_data) < 10:
            for z in [min_zoom, zoom]:
                for xi, yi in [(0, 0), (1, 0), (0, 1)]:
                    if z <= max_zoom:
                        tile_data = reader.get(z, xi, yi)
                        if tile_data and len(tile_data) >= 10:
                            zoom, x, y = z, xi, yi
                            break
                if tile_data and len(tile_data) >= 10:
                    break

        if not tile_data or len(tile_data) < 10:
            return None

        # MVT: decompress if needed, then render to PNG
        if tile_type_val == TileType.MVT.value:
            mvt_bytes = bytes(tile_data)
            # PMTiles stores tiles with tile_compression (GZIP); Reader returns raw bytes.
            tile_comp = header.get("tile_compression") or header.get("tileCompression")
            if tile_comp is not None:
                comp_val = getattr(tile_comp, "value", tile_comp)
                if comp_val == Compression.GZIP.value:
                    import gzip

                    try:
                        mvt_bytes = gzip.decompress(mvt_bytes)
                    except Exception as e:
                        logger.debug(f"MVT gzip decompress failed: {e}")
                        return None
            return _render_mvt_to_png(mvt_bytes, zoom, x, y)

        # Raster: use as-is
        return bytes(tile_data)
    except Exception as e:
        logger.warning(f"PMTiles thumbnail generation failed for {pmtiles_url}: {e}")
        return None


@celery_app.task(bind=True, name="generate_pmtiles_thumbnail")
def generate_pmtiles_thumbnail(self, pmtiles_url: str, doc_id: Optional[str] = None) -> bool:
    """
    Generate a thumbnail from a PMTiles URL and cache in Redis.
    Returns True if successful, False otherwise.
    """
    logger.info(f"Starting PMTiles thumbnail generation for {pmtiles_url}")
    try:
        image_hash = _pmtiles_thumbnail_image_hash(pmtiles_url)
        image_key = f"image:{image_hash}"

        try:
            if redis_client.exists(image_key):
                logger.info(f"PMTiles thumbnail already cached for {pmtiles_url}")
                _record_thumbnail_state(
                    doc_id,
                    state=ThumbnailState.SUCCESS,
                    source_type="pmtiles",
                    source_url=pmtiles_url,
                    source_hash=image_hash,
                    queue_task_id=getattr(getattr(self, "request", None), "id", None),
                    state_detail="PMTiles thumbnail already cached",
                )
                return True
        except Exception as redis_err:
            logger.warning(f"Redis unavailable during PMTiles cache check: {redis_err}")

        with provider_request_slot(pmtiles_url, action="PMTiles thumbnail generation") as lease:
            image_bytes = _generate_pmtiles_thumbnail_bytes(pmtiles_url)
        if not image_bytes or len(image_bytes) < 100:
            logger.debug(f"PMTiles thumbnail not generated for {pmtiles_url} (vector or empty)")
            # Cache a skip marker so we don't keep re-queuing; endpoint will redirect to
            # static map instead. Version prefix allows retry after logic improvements.
            try:
                skip_key = f"pmtiles_skip_v2:{image_hash}"
                ttl = int(os.getenv("REDIS_TTL", 604800))
                redis_client.setex(skip_key, ttl, b"1")
            except Exception as skip_err:
                logger.warning(f"Failed to cache PMTiles skip marker: {skip_err}")
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.PLACEHELD,
                source_type="pmtiles",
                source_url=pmtiles_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="PMTiles source yielded no raster thumbnail; using placeholder",
            )
            return False

        is_valid, content_type = _validate_image_content(image_bytes, None)
        if not is_valid:
            logger.error(f"PMTiles thumbnail failed validation for {pmtiles_url}")
            try:
                skip_key = f"pmtiles_skip_v2:{image_hash}"
                ttl = int(os.getenv("REDIS_TTL", 604800))
                redis_client.setex(skip_key, ttl, b"1")
            except Exception:
                pass
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.PLACEHELD,
                source_type="pmtiles",
                source_url=pmtiles_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="PMTiles source produced invalid/non-raster output; using placeholder",
            )
            return False

        try:
            ttl = int(os.getenv("REDIS_TTL", 604800))
            redis_client.setex(image_key, ttl, image_bytes)
            type_key = f"image_type:{image_hash}"
            redis_client.setex(type_key, ttl, content_type or "image/png")
            logger.info(
                f"Successfully cached PMTiles thumbnail for {pmtiles_url} "
                f"(size: {len(image_bytes)} bytes)"
            )
            detail = "Cached PMTiles thumbnail successfully"
            if lease.waited_seconds > 0:
                detail = f"{detail}; provider pacing waited {lease.waited_seconds:.2f}s"
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.SUCCESS,
                source_type="pmtiles",
                source_url=pmtiles_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail=detail,
            )
            return True
        except Exception as redis_err:
            logger.warning(f"Failed to cache PMTiles thumbnail: {redis_err}")
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type="pmtiles",
                source_url=pmtiles_url,
                source_hash=image_hash,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Failed to cache PMTiles thumbnail",
                last_error=str(redis_err),
            )
            return False

    except Exception as e:
        if _is_terminal_retry(self):
            _record_thumbnail_state(
                doc_id,
                state=ThumbnailState.FAILURE,
                source_type="pmtiles",
                source_url=pmtiles_url,
                source_hash=None,
                queue_task_id=getattr(getattr(self, "request", None), "id", None),
                state_detail="Exhausted retries for PMTiles thumbnail generation",
                last_error=str(e),
            )
        logger.error(
            f"PMTiles thumbnail generation failed for {pmtiles_url}: {e}",
            exc_info=True,
        )
        self.retry(exc=e, countdown=60, max_retries=2)
        return False
    finally:
        release_thumbnail_queue_slot(doc_id, pmtiles_url)


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
