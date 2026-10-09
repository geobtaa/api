import io
import logging
import os
from typing import Optional, Tuple

import redis
import requests
from celery import Celery
from dotenv import load_dotenv
from PIL import Image

from app.services.thumbnail_policy import (
    source_signature,
)
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
        "app.tasks.analytics_events",
        "app.tasks.api_usage_enrichment",
        "app.tasks.static_maps",
        "app.tasks.ogm_harvest",
        "app.tasks.bridge_sync",
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


def _remote_thumbnail_image_hash(image_url: str) -> str:
    """Compute Redis cache key hash for remote/IIIF-derived thumbnail images."""
    return source_signature(image_url)


def _run_thumbnail_capture(task, url: str, doc_id: Optional[str]) -> bool:
    from app.services.thumbnail_capture import capture_thumbnail

    try:
        result = capture_thumbnail(url, doc_id, cache=redis_client)
        if result.status == "deferred":
            raise RuntimeError(result.detail)
        _record_thumbnail_state(
            doc_id,
            state=ThumbnailState.SUCCESS if result.image_hash else ThumbnailState.PLACEHELD,
            source_type=infer_source_type(url),
            source_url=url,
            source_hash=result.image_hash,
            state_detail=result.detail,
            queue_task_id=getattr(getattr(task, "request", None), "id", None),
        )
        return bool(result.image_hash)
    except Exception as exc:
        _record_thumbnail_state(
            doc_id,
            state=ThumbnailState.FAILURE,
            source_type=infer_source_type(url),
            source_url=url,
            source_hash=None,
            state_detail="Thumbnail capture failed",
            last_error=str(exc),
        )
        raise task.retry(exc=exc, countdown=60, max_retries=2) from exc
    finally:
        release_thumbnail_queue_slot(doc_id, url)


@celery_app.task(bind=True, name="fetch_and_cache_image")
def fetch_and_cache_image(self, url: str, doc_id: Optional[str] = None) -> bool:
    return _run_thumbnail_capture(self, url, doc_id)


def _looks_like_manifest_url(url: str) -> bool:
    """Heuristic to detect IIIF manifest URLs by path patterns."""
    if not url:
        return False
    lowered = url.lower()
    if "/full/" in lowered or lowered.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return False
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


def _cog_thumbnail_image_hash(cog_url: str) -> str:
    """Compute Redis cache key hash for a COG-derived thumbnail."""
    return source_signature(cog_url)


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
    return _run_thumbnail_capture(self, cog_url, doc_id)


def _pmtiles_thumbnail_image_hash(pmtiles_url: str) -> str:
    """Compute Redis cache key hash for a PMTiles-derived thumbnail."""
    return source_signature(pmtiles_url)


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
    return _run_thumbnail_capture(self, pmtiles_url, doc_id)


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
