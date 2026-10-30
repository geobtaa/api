"""
Service for generating static maps from resource geometries.

This service uses the private MapLibre Native renderer for geographic PNGs.
Maps are stored in Redis (like thumbnails) for sharing between containers.
"""

import asyncio
import hashlib
import io
import json
import logging
import math
import os
import re
from typing import Any, Dict, Optional, Tuple

import cairo
import redis
from dotenv import load_dotenv
from PIL import Image
from shapely import wkt as shapely_wkt
from shapely.geometry import shape

from app.services import native_static_maps
from app.services.visual_asset_cache import (
    cache_visual_asset,
    durable_visual_asset_enabled,
    get_durable_visual_asset,
    get_durable_visual_asset_hash_for_resource,
    has_durable_visual_asset,
    redis_operation_with_loading_retry,
    store_durable_visual_asset,
    store_durable_visual_asset_link,
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

WEB_MERCATOR_MAX_LATITUDE = 85.05112878


class StaticMapService:
    """Service for generating static maps from bounding boxes."""

    def __init__(self, map_width: int = 800, map_height: int = 600):
        """
        Initialize the static map service.

        Args:
            map_width: Width of generated maps in pixels (default: 800)
            map_height: Height of generated maps in pixels (default: 600)
        """
        self.map_width = map_width
        self.map_height = map_height

        # Setup Redis connection for storing maps (same as images)
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        try:
            self.map_cache = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=1,  # Use same DB as images (binary storage)
                decode_responses=False,  # Binary mode for PNG images
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis connection for static maps: {e}")
            self.map_cache = None

    def _parse_bbox_to_geometry(self, bbox: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse bbox string to (xmin, ymin, xmax, ymax) tuple.
        Supports both ENVELOPE format and simple comma-separated format.

        Args:
            bbox: ENVELOPE string like "ENVELOPE(-123.08286, -121.912937, 45.918689, 45.255769)"
                  or simple format like "-123.08286,45.255769,-121.912937,45.918689"
                  (xmin,ymin,xmax,ymax)

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if parsing fails
        """
        try:
            bbox = bbox.strip()

            # Handle ENVELOPE format: ENVELOPE(xmin, xmax, ymax, ymin)
            envelope_match = re.match(
                r"ENVELOPE\(([^,]+),([^,]+),([^,]+),([^)]+)\)", bbox, re.IGNORECASE
            )
            if envelope_match:
                xmin, xmax, ymax, ymin = map(float, envelope_match.groups())

                # Validate bounding box
                if not self._is_valid_bbox(xmin, ymin, xmax, ymax):
                    logger.warning(f"Invalid bounding box: {bbox} - skipping")
                    return None

                return (xmin, ymin, xmax, ymax)

            # Handle simple comma-separated format: xmin,ymin,xmax,ymax
            parts = [p.strip() for p in bbox.split(",")]
            if len(parts) == 4:
                try:
                    xmin, ymin, xmax, ymax = map(float, parts)

                    # Validate bounding box
                    if not self._is_valid_bbox(xmin, ymin, xmax, ymax):
                        logger.warning(f"Invalid bounding box: {bbox} - skipping")
                        return None

                    return (xmin, ymin, xmax, ymax)
                except ValueError:
                    logger.warning(f"Could not parse bbox coordinates: {bbox}")
                    return None

            # Unrecognized format
            logger.warning(f"Unrecognized bbox format: {bbox}")
            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing bbox {bbox}: {e}")
            return None

    def _is_valid_bbox(self, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
        """
        Validate that a bounding box is reasonable for map generation.

        Args:
            xmin, ymin, xmax, ymax: Bounding box coordinates

        Returns:
            True if the bounding box is valid, False otherwise
        """
        # Check for valid coordinate ranges
        if not (-180 <= xmin <= 180) or not (-180 <= xmax <= 180):
            return False
        if not (-90 <= ymin <= 90) or not (-90 <= ymax <= 90):
            return False

        # Check for valid min/max relationships. A zero-area extent in both
        # dimensions is a legitimate point geometry.
        if xmin > xmax or ymin > ymax:
            return False

        if xmin == xmax and ymin == ymax:
            return True

        # Very thin one-dimensional or near-zero rectangles are not useful
        # fallback map extents.
        if (xmax - xmin) < 0.001 or (ymax - ymin) < 0.001:
            return False

        return True

    def _is_global_bbox(self, bbox_coords: Tuple[float, float, float, float]) -> bool:
        """
        Check if a bounding box represents a global dataset (entire world).

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple

        Returns:
            True if the bbox covers the entire world, False otherwise
        """
        xmin, ymin, xmax, ymax = bbox_coords
        tolerance = 1.0

        lon_span = xmax - xmin
        lat_span = ymax - ymin

        is_near_global = (
            lon_span >= (360 - tolerance * 2)
            and lat_span >= (180 - tolerance * 2)
            and xmin >= (-180 - tolerance)
            and xmin <= (-180 + tolerance)
            and xmax <= (180 + tolerance)
            and xmax >= (180 - tolerance)
            and ymin >= (-90 - tolerance)
            and ymin <= (-90 + tolerance)
            and ymax <= (90 + tolerance)
            and ymax >= (90 - tolerance)
        )

        return is_near_global

    def _renderable_bbox(
        self,
        bbox_coords: Tuple[float, float, float, float],
    ) -> Optional[Tuple[float, float, float, float]]:
        """Return a Web-Mercator-safe bbox, or None when no renderable area remains."""
        xmin, ymin, xmax, ymax = bbox_coords
        if not all(math.isfinite(value) for value in bbox_coords):
            return None

        xmin = max(-180.0, min(180.0, xmin))
        xmax = max(-180.0, min(180.0, xmax))
        ymin = max(-WEB_MERCATOR_MAX_LATITUDE, min(WEB_MERCATOR_MAX_LATITUDE, ymin))
        ymax = max(-WEB_MERCATOR_MAX_LATITUDE, min(WEB_MERCATOR_MAX_LATITUDE, ymax))

        if xmin >= xmax or ymin >= ymax:
            return None
        if (xmax - xmin) < 0.001 or (ymax - ymin) < 0.001:
            return None
        return (xmin, ymin, xmax, ymax)

    def _bbox_within_web_mercator(
        self,
        bbox_coords: Tuple[float, float, float, float],
    ) -> bool:
        """Return True when full geometry can be projected safely."""
        _xmin, ymin, _xmax, ymax = bbox_coords
        return ymin >= -WEB_MERCATOR_MAX_LATITUDE and ymax <= WEB_MERCATOR_MAX_LATITUDE

    def _parse_geometry_to_bbox(self, geometry: Any) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse geometry (GeoJSON, WKT, ENVELOPE, or string) to bounding box coordinates.

        Args:
            geometry: Geometry in various formats (GeoJSON dict, WKT string, ENVELOPE string, etc.)

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if parsing fails
        """
        if not geometry:
            return None

        try:
            # If it's already a dict (GeoJSON), use it directly
            if isinstance(geometry, dict):
                return self._extract_bbox_from_geojson(geometry)

            # If it's a string, try to parse it
            if isinstance(geometry, str):
                geometry_str = geometry.strip()

                # Try parsing as JSON first (GeoJSON)
                try:
                    geometry_dict = json.loads(geometry_str)
                    if isinstance(geometry_dict, dict):
                        return self._extract_bbox_from_geojson(geometry_dict)
                except (json.JSONDecodeError, ValueError):
                    pass

                # Try parsing as WKT using Shapely
                try:
                    shapely_geom = shapely_wkt.loads(geometry_str)
                    bounds = shapely_geom.bounds  # Returns (minx, miny, maxx, maxy)
                    return (bounds[0], bounds[1], bounds[2], bounds[3])
                except Exception:
                    pass

                # Try parsing as ENVELOPE or simple bbox format
                bbox_coords = self._parse_bbox_to_geometry(geometry_str)
                if bbox_coords:
                    return bbox_coords

            return None

        except Exception as e:
            logger.error(f"Error parsing geometry: {e}")
            return None

    def _extract_bbox_from_geojson(
        self, geojson: Dict[str, Any]
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Extract bounding box from GeoJSON geometry.

        Args:
            geojson: GeoJSON geometry dict

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if extraction fails
        """
        try:
            # Use Shapely to get bounds from any geometry type
            geom = shape(geojson)
            bounds = geom.bounds  # Returns (minx, miny, maxx, maxy)
            return (bounds[0], bounds[1], bounds[2], bounds[3])
        except Exception as e:
            logger.error(f"Error extracting bbox from GeoJSON: {e}")
            return None

    _MAP_VARIANT = "native_geometry_v1"
    _BASEMAP_VARIANT = "native_basemap_v1"
    _ASSET_KEY_PREFIX = "static_map_asset"
    _ALIAS_KEY_PREFIX = "static_map_alias"
    _HASH_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
    _GLOBAL_SIGNATURE_SEED = "static-map:no-geometry"

    def _ban_icon_image(self, size: int) -> Image.Image:
        """Render the provided ban SVG path exactly via Cairo."""
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 640, 640)
        ctx = cairo.Context(surface)
        ctx.set_source_rgba(23 / 255, 58 / 255, 83 / 255, 235 / 255)

        ctx.move_to(431.2, 476.5)
        ctx.line_to(163.5, 208.8)
        ctx.curve_to(141.1, 240.2, 128, 278.6, 128, 320)
        ctx.curve_to(128, 426, 214, 512, 320, 512)
        ctx.curve_to(361.5, 512, 399.9, 498.9, 431.2, 476.5)
        ctx.close_path()

        ctx.move_to(476.5, 431.2)
        ctx.curve_to(498.9, 399.8, 512, 361.4, 512, 320)
        ctx.curve_to(512, 214, 426, 128, 320, 128)
        ctx.curve_to(278.5, 128, 240.1, 141.1, 208.8, 163.5)
        ctx.line_to(476.5, 431.2)
        ctx.close_path()

        ctx.move_to(64, 320)
        ctx.curve_to(64, 178.6, 178.6, 64, 320, 64)
        ctx.curve_to(461.4, 64, 576, 178.6, 576, 320)
        ctx.curve_to(576, 461.4, 461.4, 576, 320, 576)
        ctx.curve_to(178.6, 576, 64, 461.4, 64, 320)
        ctx.close_path()
        ctx.fill()

        buf = io.BytesIO()
        surface.write_to_png(buf)
        buf.seek(0)
        return Image.open(buf).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)

    def _overlay_no_data_symbol(self, image: Image.Image) -> Image.Image:
        """Overlay a circle-with-slash symbol on a world map for no-geometry resources."""
        rendered = image.convert("RGBA")
        overlay = Image.new("RGBA", rendered.size, (0, 0, 0, 0))

        width, height = rendered.size
        target_size = int(min(width, height) * 0.64)
        icon = self._ban_icon_image(target_size)
        icon_x = (width - target_size) // 2
        icon_y = (height - target_size) // 2
        overlay.alpha_composite(icon, (icon_x, icon_y))
        return Image.alpha_composite(rendered, overlay)

    def _cache_key(
        self,
        resource_id: str,
        *,
        variant: str = "static_map",
        source_signature: str | None = None,
    ) -> str:
        """Build Redis key for a map variant."""
        if source_signature:
            return f"{variant}:{source_signature}:{resource_id}"
        return f"{variant}:{resource_id}"

    def _asset_key(self, map_hash: str) -> str:
        return f"{self._ASSET_KEY_PREFIX}:{map_hash}"

    def _alias_key(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
    ) -> str:
        if source_signature:
            return f"{self._ALIAS_KEY_PREFIX}:{variant}:{source_signature}:{resource_id}"
        return f"{self._ALIAS_KEY_PREFIX}:{variant}:{resource_id}"

    def _is_asset_hash(self, value: str | None) -> bool:
        return bool(value and self._HASH_RE.fullmatch(value))

    def _asset_hash(self, map_bytes: bytes) -> str:
        return hashlib.sha256(map_bytes).hexdigest()

    def _asset_content_type(self, map_bytes: bytes) -> str:
        stripped = map_bytes.lstrip()
        if map_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if stripped.startswith(b"<svg") or (
            stripped.startswith(b"<?xml") and b"<svg" in stripped[:512]
        ):
            return "image/svg+xml"
        return "application/octet-stream"

    def _alias_cache(self):
        try:
            return redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=0,
                decode_responses=True,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis alias cache for static maps: {e}")
            return None

    @staticmethod
    def campus_asset_hash(resource_id: str, variant: str, source_signature: str | None) -> str:
        """Stable campus camera identity without a resource-table foreign key."""
        value = json.dumps([resource_id, variant, source_signature], separators=(",", ":"))
        return hashlib.sha256(value.encode()).hexdigest()

    def geometry_variant(self) -> str:
        return self._MAP_VARIANT

    def basemap_variant(self) -> str:
        return self._BASEMAP_VARIANT

    def geometry_signature(self, geometry: Any) -> str:
        """Return a stable content signature for the current geometry input."""
        if geometry in (None, ""):
            normalized = self._GLOBAL_SIGNATURE_SEED
        else:
            geojson = self._geometry_to_geojson_dict(geometry)
            if geojson is not None:
                normalized = json.dumps(geojson, sort_keys=True, separators=(",", ":"))
            elif isinstance(geometry, str):
                normalized = geometry.strip()
            else:
                normalized = json.dumps(
                    geometry,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
        return (
            native_static_maps.signature(
                [normalized, self.map_width, self.map_height]
                + (["compact-credits-v1"] if self.map_width < 500 else [])
            )
            if native_static_maps.renderer_url()
            else hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        )

    def centered_basemap_signature(self, *, latitude: float, longitude: float, zoom: int) -> str:
        """Return a stable content signature for a campus-centered basemap request."""
        payload = json.dumps(
            {
                "latitude": round(float(latitude), 6),
                "longitude": round(float(longitude), 6),
                "zoom": int(zoom),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return (
            native_static_maps.signature([payload, self.map_width, self.map_height])
            if native_static_maps.renderer_url()
            else hashlib.sha256(payload.encode("utf-8")).hexdigest()
        )

    def get_asset_hash_sync(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[str]:
        hot_hash = self.get_hot_asset_hash_sync(
            resource_id,
            variant=variant,
            source_signature=source_signature,
        )
        if hot_hash:
            return hot_hash

        if resource_id.startswith("institution:"):
            return None

        value = get_durable_visual_asset_hash_for_resource(
            resource_id,
            asset_kind=variant,
            source_signature=source_signature,
        )
        if value and self._is_asset_hash(value):
            if not hydrate_asset:
                self.set_asset_hash_sync(
                    resource_id,
                    variant=variant,
                    map_hash=value,
                    source_signature=source_signature,
                )
                return value
            if self.get_cached_asset_sync(value):
                self.set_asset_hash_sync(
                    resource_id,
                    variant=variant,
                    map_hash=value,
                    source_signature=source_signature,
                )
                return value
        return None

    def get_hot_asset_hash_sync(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
    ) -> Optional[str]:
        alias_cache = self._alias_cache()
        if alias_cache:
            alias_key = self._alias_key(
                resource_id,
                variant=variant,
                source_signature=source_signature,
            )
            try:
                value = redis_operation_with_loading_retry(
                    lambda: alias_cache.get(alias_key),
                    operation_name=f"read static map alias {alias_key}",
                )
                if self._is_asset_hash(value):
                    return value
                if value:
                    redis_operation_with_loading_retry(
                        lambda: alias_cache.delete(alias_key),
                        operation_name=f"delete invalid static map alias {alias_key}",
                    )
            except Exception as e:
                logger.warning(
                    "Failed to read static map alias for %s (%s): %s",
                    resource_id,
                    variant,
                    e,
                )
        return None

    async def get_asset_hash(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[str]:
        return await asyncio.to_thread(
            self.get_asset_hash_sync,
            resource_id,
            variant=variant,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def set_asset_hash_sync(
        self,
        resource_id: str,
        *,
        variant: str,
        map_hash: str,
        source_signature: str | None = None,
    ) -> bool:
        alias_cache = self._alias_cache()
        if not alias_cache or not self._is_asset_hash(map_hash):
            return False

        try:
            return cache_visual_asset(
                alias_cache,
                self._alias_key(
                    resource_id,
                    variant=variant,
                    source_signature=source_signature,
                ),
                map_hash,
            )
        except Exception as e:
            logger.warning(
                "Failed to cache static map alias for %s (%s) -> %s: %s",
                resource_id,
                variant,
                map_hash,
                e,
            )
            return False

    async def set_asset_hash(
        self,
        resource_id: str,
        *,
        variant: str,
        map_hash: str,
        source_signature: str | None = None,
    ) -> bool:
        return await asyncio.to_thread(
            self.set_asset_hash_sync,
            resource_id,
            variant=variant,
            map_hash=map_hash,
            source_signature=source_signature,
        )

    def delete_asset_hash_sync(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
    ) -> bool:
        alias_cache = self._alias_cache()
        if not alias_cache:
            return False

        try:
            return bool(
                alias_cache.delete(
                    self._alias_key(
                        resource_id,
                        variant=variant,
                        source_signature=source_signature,
                    )
                )
            )
        except Exception as e:
            logger.warning(
                "Failed to delete static map alias for %s (%s): %s",
                resource_id,
                variant,
                e,
            )
            return False

    async def delete_asset_hash(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
    ) -> bool:
        return await asyncio.to_thread(
            self.delete_asset_hash_sync,
            resource_id,
            variant=variant,
            source_signature=source_signature,
        )

    def has_cached_asset_sync(self, map_hash: str) -> bool:
        if not self._is_asset_hash(map_hash):
            return False
        if self.map_cache:
            try:
                asset_key = self._asset_key(map_hash)
                if redis_operation_with_loading_retry(
                    lambda: self.map_cache.exists(asset_key),
                    operation_name=f"check static map asset {asset_key}",
                ):
                    return True
            except Exception as exc:
                logger.warning("Redis asset check failed: %s", type(exc).__name__)
        return has_durable_visual_asset(map_hash)

    async def has_cached_asset(self, map_hash: str) -> bool:
        return await asyncio.to_thread(self.has_cached_asset_sync, map_hash)

    def get_cached_asset_sync(self, map_hash: str) -> Optional[bytes]:
        if not self._is_asset_hash(map_hash):
            return None

        if self.map_cache:
            try:
                asset_key = self._asset_key(map_hash)
                cached = redis_operation_with_loading_retry(
                    lambda: self.map_cache.get(asset_key),
                    operation_name=f"read static map asset {asset_key}",
                )
                if cached:
                    return cached
            except Exception as e:
                logger.error(f"Error retrieving cached static map asset {map_hash}: {e}")
        durable = get_durable_visual_asset(map_hash)
        if not durable:
            return None

        map_bytes, _content_type = durable
        self.cache_asset_sync(map_hash, map_bytes)
        return map_bytes

    async def get_cached_asset(self, map_hash: str) -> Optional[bytes]:
        return await asyncio.to_thread(self.get_cached_asset_sync, map_hash)

    def cache_asset_sync(self, map_hash: str, map_bytes: bytes) -> bool:
        if not self.map_cache or not self._is_asset_hash(map_hash):
            return False

        try:
            return cache_visual_asset(self.map_cache, self._asset_key(map_hash), map_bytes)
        except Exception as e:
            logger.error(f"Error caching static map asset {map_hash}: {e}")
            return False

    def materialize_asset_sync(
        self,
        resource_id: str,
        *,
        variant: str,
        map_bytes: bytes,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[str]:
        if not map_bytes:
            return None

        is_campus = resource_id.startswith("institution:")
        map_hash = self._asset_hash(map_bytes)
        stored = store_durable_visual_asset(
            map_hash,
            asset_kind=variant,
            content_type=self._asset_content_type(map_bytes),
            body=map_bytes,
        )
        if durable_visual_asset_enabled() and not stored:
            return None
        if stored and not is_campus:
            if not store_durable_visual_asset_link(
                resource_id,
                asset_hash=map_hash,
                asset_kind=variant,
                source_signature=source_signature,
            ):
                return None
            if source_signature and not store_durable_visual_asset_link(
                resource_id,
                asset_hash=map_hash,
                asset_kind=variant,
                source_signature=None,
            ):
                return None
        if hydrate_asset:
            cached = self.cache_asset_sync(map_hash, map_bytes)
            if not stored and not cached:
                return None
        self.set_asset_hash_sync(
            resource_id,
            variant=variant,
            map_hash=map_hash,
            source_signature=source_signature,
        )
        if source_signature:
            self.set_asset_hash_sync(
                resource_id,
                variant=variant,
                map_hash=map_hash,
                source_signature=None,
            )
        return map_hash

    async def materialize_asset(
        self,
        resource_id: str,
        *,
        variant: str,
        map_bytes: bytes,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[str]:
        return await asyncio.to_thread(
            self.materialize_asset_sync,
            resource_id,
            variant=variant,
            map_bytes=map_bytes,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def materialize_cached_variant_sync(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[str]:
        map_hash = self.get_asset_hash_sync(
            resource_id,
            variant=variant,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )
        if map_hash and not hydrate_asset:
            return map_hash
        if map_hash and self.get_cached_asset_sync(map_hash):
            return map_hash
        if map_hash:
            self.delete_asset_hash_sync(
                resource_id,
                variant=variant,
                source_signature=source_signature,
            )

        if not self.map_cache:
            return None

        try:
            map_bytes = self.map_cache.get(
                self._cache_key(
                    resource_id,
                    variant=variant,
                    source_signature=source_signature,
                )
            )
        except Exception as e:
            logger.error(
                "Error retrieving cached static map variant for %s (%s): %s",
                resource_id,
                variant,
                e,
            )
            return None

        if not map_bytes:
            return None

        return self.materialize_asset_sync(
            resource_id,
            variant=variant,
            map_bytes=map_bytes,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    async def materialize_cached_variant(
        self,
        resource_id: str,
        *,
        variant: str,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[str]:
        return await asyncio.to_thread(
            self.materialize_cached_variant_sync,
            resource_id,
            variant=variant,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def _geometry_to_geojson_dict(self, geometry: Any) -> Optional[Dict[str, Any]]:
        """If geometry is or parses to a GeoJSON geometry dict, return it; else None."""
        if (
            isinstance(geometry, dict)
            and geometry.get("type")
            and geometry.get("coordinates") is not None
        ):
            return geometry
        if isinstance(geometry, str):
            geometry = geometry.strip()
            try:
                parsed = json.loads(geometry)
                if (
                    isinstance(parsed, dict)
                    and parsed.get("type")
                    and parsed.get("coordinates") is not None
                ):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # Try WKT (e.g. POLYGON, MULTIPOLYGON, LINESTRING) for locn_geometry
            try:
                geom = shapely_wkt.loads(geometry)
                geojson = geom.__geo_interface__
                if (
                    isinstance(geojson, dict)
                    and geojson.get("type")
                    and geojson.get("coordinates") is not None
                ):
                    return geojson
            except Exception:
                pass
        return None

    def generate_map(
        self,
        resource_id: str,
        geometry: Any,
        *,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[bytes]:
        """
        Generate a static map image from a geometry and store it in Redis.
        Uses full GeoJSON (polygons, lines) when available to match the show page;
        otherwise falls back to a bbox rectangle.

        Args:
            resource_id: The resource ID
            geometry: Geometry in various formats (GeoJSON dict, WKT string, ENVELOPE string, etc.)

        Returns:
            PNG image bytes if successful, None if generation failed
        """
        return native_static_maps.generate(
            self,
            resource_id,
            geometry,
            overlay=True,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def generate_global_map(
        self,
        resource_id: str,
        *,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[bytes]:
        """
        Generate a world-view static map (no bbox) for resources with no geometry.
        Uses the same tile layer and cache key as generate_map.
        """
        return native_static_maps.generate(
            self,
            resource_id,
            None,
            overlay=True,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def generate_basemap(
        self,
        resource_id: str,
        geometry: Any,
        *,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[bytes]:
        """
        Generate a basemap-only image using the resource extent with no visible geometry overlay.
        """
        return native_static_maps.generate(
            self,
            resource_id,
            geometry,
            overlay=False,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def generate_global_basemap(
        self,
        resource_id: str,
        *,
        source_signature: str | None = None,
        hydrate_asset: bool = True,
    ) -> Optional[bytes]:
        """Generate a world-view basemap image with no geometry overlay."""
        return native_static_maps.generate(
            self,
            resource_id,
            None,
            overlay=False,
            source_signature=source_signature,
            hydrate_asset=hydrate_asset,
        )

    def generate_centered_basemap(
        self,
        resource_id: str,
        *,
        latitude: float,
        longitude: float,
        zoom: int = 15,
        source_signature: str | None = None,
    ) -> Optional[bytes]:
        """Generate a basemap centered on a specific lat/lon at a fixed zoom."""
        return native_static_maps.generate(
            self,
            resource_id,
            overlay=False,
            center=[longitude, latitude],
            zoom=zoom,
            source_signature=source_signature
            or self.centered_basemap_signature(latitude=latitude, longitude=longitude, zoom=zoom),
        )

    async def get_cached_map(
        self,
        resource_id: str,
        *,
        source_signature: str | None = None,
    ) -> Optional[bytes]:
        """
        Retrieve a cached static map from Redis.

        Args:
            resource_id: The resource ID

        Returns:
            PNG image bytes if found, None otherwise
        """
        if not self.map_cache:
            return None

        try:
            map_key = self._cache_key(
                resource_id,
                variant=self._MAP_VARIANT,
                source_signature=source_signature,
            )
            map_data = await asyncio.to_thread(self.map_cache.get, map_key)
            if map_data:
                logger.debug(f"Serving cached static map for resource {resource_id}")
                return map_data
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached static map for {resource_id}: {e}")
            return None

    async def get_cached_basemap(
        self,
        resource_id: str,
        *,
        source_signature: str | None = None,
    ) -> Optional[bytes]:
        """Retrieve a cached basemap-only image from Redis."""
        if not self.map_cache:
            return None

        try:
            map_key = self._cache_key(
                resource_id,
                variant=self._BASEMAP_VARIANT,
                source_signature=source_signature,
            )
            map_data = await asyncio.to_thread(self.map_cache.get, map_key)
            if map_data:
                logger.debug(f"Serving cached basemap for resource {resource_id}")
                return map_data
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached basemap for {resource_id}: {e}")
            return None

    def basemap_exists(self, resource_id: str, *, source_signature: str | None = None) -> bool:
        """Check if a basemap-only image exists in Redis cache."""
        if not self.map_cache:
            return False

        try:
            map_key = self._cache_key(
                resource_id,
                variant=self._BASEMAP_VARIANT,
                source_signature=source_signature,
            )
            return bool(self.map_cache.exists(map_key))
        except Exception as e:
            logger.error(f"Error checking if basemap exists for {resource_id}: {e}")
            return False

    def map_exists(self, resource_id: str, *, source_signature: str | None = None) -> bool:
        """
        Check if a static map exists in Redis cache.

        Args:
            resource_id: The resource ID

        Returns:
            True if the map exists in cache, False otherwise
        """
        if not self.map_cache:
            return False

        try:
            map_key = self._cache_key(
                resource_id,
                variant=self._MAP_VARIANT,
                source_signature=source_signature,
            )
            return bool(self.map_cache.exists(map_key))
        except Exception as e:
            logger.error(f"Error checking if static map exists for {resource_id}: {e}")
            return False
