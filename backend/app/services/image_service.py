import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import aiohttp
import redis
import requests
from dotenv import load_dotenv

from app.security_utils import url_hostname_matches
from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
)
from app.services.thumbnail_alias_service import thumbnail_alias_service
from app.services.thumbnail_queue_service import acquire_thumbnail_queue_slot
from app.services.thumbnail_state_service import (
    ThumbnailState,
    ThumbnailStatePayload,
    infer_source_type,
    safe_record_thumbnail_state_sync,
    thumbnail_state_service,
)
from app.services.visual_asset_cache import cache_visual_asset, get_durable_visual_asset

# Load environment variables from .env file
try:
    load_dotenv()
except (OSError, PermissionError):
    # In sandboxed environments, .env may be unreadable. Continue with defaults/env.
    pass

logger = logging.getLogger(__name__)

IIIF_THUMBNAIL_BOX = os.getenv("IIIF_THUMBNAIL_BOX", "!800,800")
IIIF_THUMBNAIL_PATH = f"/full/{IIIF_THUMBNAIL_BOX}/0/default.jpg"
THUMBNAIL_CACHE_VERSION = os.getenv("THUMBNAIL_CACHE_VERSION", "v3")
REMOTE_THUMBNAIL_PREFIX = f"remote-thumb-normalized:{THUMBNAIL_CACHE_VERSION}:"
COG_THUMBNAIL_PREFIX = "cog-thumb:"
PMTILES_THUMBNAIL_PREFIX = "pmtiles-thumb:"

# Shared Redis connection pool to avoid creating new connections for each ImageService instance
_redis_connection_pool = None
_redis_image_connection_pool = None


def _get_redis_connection_pool():
    """Get or create shared Redis connection pool for text cache (db=0)."""
    global _redis_connection_pool
    if _redis_connection_pool is None:
        _redis_connection_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            db=0,
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=1.0,  # 1 second timeout to prevent hanging in tests
            socket_timeout=1.0,  # 1 second socket timeout
        )
    return _redis_connection_pool


def _get_redis_image_connection_pool():
    """Get or create shared Redis connection pool for binary images (db=1)."""
    global _redis_image_connection_pool
    if _redis_image_connection_pool is None:
        _redis_image_connection_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            db=1,
            decode_responses=False,
            max_connections=50,
            socket_connect_timeout=1.0,  # 1 second timeout to prevent hanging in tests
            socket_timeout=1.0,  # 1 second socket timeout
        )
    return _redis_image_connection_pool


class ImageService:
    """Service for handling different types of image assets."""

    def __init__(
        self,
        metadata: Dict[str, Any],
        distribution_context: Optional[DistributionContext] = None,
    ):
        """
        Initialize the image service with document metadata.

        Args:
            metadata: Document metadata dictionary
        """
        self.metadata = metadata
        if distribution_context is None:
            distribution_context = build_distribution_context(metadata.get("id", ""), [])
        self.distribution_context = distribution_context
        self.by_uri = distribution_context.by_uri

        # Setup Redis connection using shared connection pool (reuse connections)
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.application_url = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")

        # Use shared connection pool to avoid creating new connections for each instance
        self.cache = redis.Redis(connection_pool=_get_redis_connection_pool())
        # TODO(cache-policy): For thumbnail imagery, replace time-based expiry with
        # metadata/admin-driven invalidation. Keep this TTL fallback until the
        # invalidation workflow is fully implemented end-to-end.
        self.cache_ttl = int(os.getenv("REDIS_TTL", 604800))  # 7 days in seconds

        # Setup binary Redis connection for images using shared connection pool
        self.image_cache = redis.Redis(connection_pool=_get_redis_image_connection_pool())

        # Setup logging (reuse logger, don't create new handlers for each instance)
        self.logger = logging.getLogger("ImageService")
        # Only set level if not already configured (avoid reconfiguring on every instance)
        if not self.logger.handlers:
            log_path = os.getenv("LOG_PATH", "logs")
            os.makedirs(log_path, exist_ok=True)
            log_handler = logging.FileHandler(os.path.join(log_path, "image_service.log"))
            log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(log_handler)
            self.logger.setLevel(logging.INFO)

        # print(f"Document WXS: {self.metadata.get('gbl_wxsidentifier_s')}")

    def _api_v1_base_url(self) -> str:
        """Return APPLICATION_URL normalized to the API v1 root."""
        if self.application_url.endswith("/api/v1"):
            return self.application_url
        return f"{self.application_url}/api/v1"

    def _get_manifest(self, manifest_url: str) -> Optional[Dict]:
        """Get manifest from cache or fetch and cache it."""
        cache_key = f"manifest:{manifest_url}"

        # Try to get from cache
        cached_data = self.cache.get(cache_key)
        if cached_data:
            self.logger.info(f"🚀 Cache HIT for manifest {manifest_url}")
            return json.loads(cached_data)

        # If not in cache, fetch and store
        try:
            self.logger.info(f"🐌 Cache MISS for manifest {manifest_url}")
            # Use User-Agent header to avoid 403 errors from servers that block bots
            headers = {"User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"}
            # Increased timeout for slow servers
            response = requests.get(manifest_url, timeout=5.0, headers=headers)

            # Don't try to parse 403/401 responses - they indicate authorization issues
            if response.status_code in (401, 403):
                self.logger.warning(
                    f"Authorization error ({response.status_code}) "
                    f"for manifest {manifest_url}. Cannot fetch."
                )
                return None

            response.raise_for_status()
            manifest_data = response.json()

            # Cache the manifest
            self.cache.setex(cache_key, self.cache_ttl, json.dumps(manifest_data))
            return manifest_data
        except requests.Timeout:
            self.logger.warning(f"Timeout fetching manifest {manifest_url} (5s timeout)")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching manifest {manifest_url}: {e}")
            return None

    def _extract_thumbnail_from_manifest_json(
        self, manifest_json: Dict, manifest_url: str = ""
    ) -> Optional[str]:
        """
        Extract thumbnail URL from a IIIF manifest JSON object.
        This method does NOT fetch the manifest - it only parses existing JSON.

        Args:
            manifest_json (Dict): The IIIF manifest JSON object
            manifest_url (str): Optional manifest URL for logging

        Returns:
            Optional[str]: Thumbnail URL or None if not found
        """
        try:
            # Prefer explicit thumbnail when present (array or object)
            if manifest_json.get("thumbnail"):
                self.logger.debug("Image: manifest.thumbnail present")
                thumb = manifest_json["thumbnail"]
                if isinstance(thumb, list) and thumb:
                    thumb = thumb[0]
                if isinstance(thumb, dict):
                    # IIIF v2 may use @id; v3 may use id
                    candidate = thumb.get("@id") or thumb.get("id")
                else:
                    candidate = thumb
                if candidate:
                    self.logger.debug(f"Found manifest-level thumbnail: {candidate}")
                    return self._standardize_iiif_url(candidate)

            # Sequences - Prefer direct resource @id, then service @id
            if manifest_json.get("sequences"):
                self.logger.debug("Image: sequences")
                canvas = manifest_json.get("sequences", [{}])[0].get("canvases", [{}])[0]
                image = canvas.get("images", [{}])[0].get("resource", {})

                # Prefer direct image ID when present
                if image.get("@id"):
                    return self._standardize_iiif_url(image["@id"])

                # Fallback to image service @id to construct consistent size
                service_id = image.get("service", {}).get("@id")
                if service_id:
                    return self._standardize_iiif_url(service_id)

            # Items - IIIF v3 style
            elif manifest_json.get("items"):
                # Check for thumbnail in first canvas (items[0].thumbnail)
                first_canvas = (
                    manifest_json.get("items", [{}])[0] if manifest_json.get("items") else {}
                )
                if first_canvas.get("thumbnail"):
                    canvas_thumb = first_canvas["thumbnail"]
                    if isinstance(canvas_thumb, list) and canvas_thumb:
                        canvas_thumb = canvas_thumb[0]
                    if isinstance(canvas_thumb, dict):
                        thumb_id = canvas_thumb.get("id") or canvas_thumb.get("@id")
                        if thumb_id:
                            self.logger.debug("Image: canvas thumbnail id")
                            return self._standardize_iiif_url(thumb_id)
                    elif isinstance(canvas_thumb, str):
                        return self._standardize_iiif_url(canvas_thumb)

                # Navigate through items structure: items[0] -> items[0] -> items[0] -> body
                items_path = (
                    manifest_json.get("items", [{}])[0].get("items", [{}])[0].get("items", [{}])[0]
                )

                # Try body.service.@id first (prefer constructing consistent size)
                body = items_path.get("body", {})
                if isinstance(body, dict):
                    # Handle service as either object or array
                    service = body.get("service")
                    if isinstance(service, list) and service:
                        # Service is an array, get first element
                        service = service[0]

                    if isinstance(service, dict):
                        body_service_id = service.get("@id") or service.get("id")
                    elif isinstance(service, str):
                        body_service_id = service
                    else:
                        body_service_id = None

                    if body_service_id:
                        self.logger.debug(f"Found body service ID: {body_service_id}")
                        return self._standardize_iiif_url(body_service_id)

                    # Next try body.id (prefer direct ID unmodified)
                    if body.get("id"):
                        self.logger.debug(f"Found body ID: {body.get('id')}")
                        return self._standardize_iiif_url(body["id"])

                # Try direct id
                if items_path.get("id"):
                    self.logger.debug(f"Found items path ID: {items_path.get('id')}")
                    return self._standardize_iiif_url(items_path["id"])

            # Thumbnail - Try various thumbnail formats
            elif manifest_json.get("thumbnail"):
                # Already handled above, but keep for safety
                thumbnail = manifest_json["thumbnail"]
                if isinstance(thumbnail, dict):
                    candidate = thumbnail.get("@id") or thumbnail.get("id")
                else:
                    candidate = thumbnail
                if candidate:
                    self.logger.debug(f"Found thumbnail: {candidate}")
                    return self._standardize_iiif_url(candidate)

            # Fallback - couldn't find thumbnail
            self.logger.warning(f"Could not find thumbnail in manifest {manifest_url}")
            return None  # Return None instead of manifest_url to indicate failure

        except Exception as e:
            self.logger.error(f"Error processing IIIF manifest JSON: {e}", exc_info=True)
            return None  # Return None to indicate failure

    def get_iiif_manifest_thumbnail(self, manifest_url: str) -> Optional[str]:
        """
        Get thumbnail URL from IIIF Manifest by fetching it.
        NOTE: This method makes synchronous HTTP requests and should NOT be called
        during API request handling. Use _extract_thumbnail_from_manifest_json() instead
        if you already have the manifest JSON.

        Args:
            manifest_url (str): URL to the IIIF manifest

        Returns:
            Optional[str]: Thumbnail URL or None if not found
        """
        manifest_json = self._get_manifest(manifest_url)
        if not manifest_json:
            self.logger.warning(f"Could not fetch manifest {manifest_url}")
            return None  # Return None instead of manifest_url to indicate failure

        return self._extract_thumbnail_from_manifest_json(manifest_json, manifest_url)

    def _standardize_iiif_url(self, url: str) -> str:
        """
        Standardize IIIF image URLs to ensure consistent size.
        Converts various IIIF image URLs to a standard bounded-box rendition.
        """
        try:
            # Skip if not a likely IIIF URL
            if not any(x in url.lower() for x in ["/iiif/", "/image/", "info.json"]):
                return url

            # If URL points to info.json, convert to a standard image URL
            if url.endswith("/info.json"):
                return url[:-10] + IIIF_THUMBNAIL_PATH

            if url.endswith(("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json")):
                return url

            # If URL already contains /full/, replace everything after it with our standard path
            if "/full/" in url:
                prefix = url.split("/full/")[0]
                return f"{prefix}{IIIF_THUMBNAIL_PATH}"

            # Bare IIIF service endpoint or identifier without an explicit image request
            if not re.search(r"/default\.[A-Za-z0-9]+$", url):
                return f"{url.rstrip('/')}{IIIF_THUMBNAIL_PATH}"

            # As a final fallback, return original URL
            return url
        except Exception as e:
            self.logger.error(f"Error standardizing IIIF URL {url}: {e}")
            return url

    def _b1g_image_source_url(self) -> Optional[str]:
        """Return the configured b1g_image_ss URL when it contains a usable HTTP(S) value."""
        b1g_image = self.metadata.get("b1g_image_ss")
        if not b1g_image:
            return None

        url = None
        if isinstance(b1g_image, list) and b1g_image:
            url = b1g_image[0]
        elif isinstance(b1g_image, str):
            # Handle JSON array string, e.g. '["https://..."]' from DB
            s = b1g_image.strip()
            if s.startswith(("http://", "https://")):
                url = s
            elif s.startswith("["):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list) and parsed:
                        url = parsed[0]
                except (json.JSONDecodeError, TypeError):
                    pass

        if isinstance(url, str) and url.strip().startswith(("http://", "https://")):
            return url.strip()
        return None

    def _current_thumbnail_hash_sync(
        self,
        doc_id: str,
        *,
        source_url: Optional[str],
    ) -> Optional[str]:
        """
        Return the hot immutable hash for the current preferred source, if available.

        Persisted success state is only reused when it still points at the same
        preferred source URL. This lets records self-heal when thumbnail source
        selection changes (for example, switching from a tiny ContentDM derivative
        to a IIIF-derived thumbnail).
        """
        candidate_hash = (
            self._candidate_cached_thumbnail_hash_sync(source_url) if source_url else None
        )
        state = thumbnail_state_service.get_state_sync(doc_id)
        alias_hash = thumbnail_alias_service.get_hash_sync(doc_id)

        if alias_hash:
            alias_matches_state = (
                source_url
                and state is not None
                and state.get("state") == ThumbnailState.SUCCESS
                and state.get("source_hash") == alias_hash
                and state.get("source_url") == source_url
                and self.has_cached_image_sync(alias_hash)
            )
            alias_matches_candidate = candidate_hash is not None and alias_hash == candidate_hash
            if alias_matches_state or alias_matches_candidate:
                return alias_hash
            thumbnail_alias_service.delete_sync(doc_id)

        if state:
            state_hash = state.get("source_hash")
            state_source_url = state.get("source_url")
            if (
                source_url
                and state.get("state") == ThumbnailState.SUCCESS
                and state_hash
                and state_source_url == source_url
                and self.has_cached_image_sync(state_hash)
            ):
                thumbnail_alias_service.set_hash_sync(doc_id, state_hash)
                return state_hash

            if state_hash and not self.has_cached_image_sync(state_hash):
                thumbnail_alias_service.delete_sync(doc_id)

            if source_url and state_source_url and state_source_url != source_url:
                thumbnail_alias_service.delete_sync(doc_id)

        if not source_url:
            return None

        if candidate_hash:
            thumbnail_alias_service.set_hash_sync(doc_id, candidate_hash)
            return candidate_hash

        return None

    def current_thumbnail_hash_sync(self) -> Optional[str]:
        """Return the current hot immutable thumbnail hash for this resource, if any."""
        doc_id = self.metadata.get("id")
        if not doc_id:
            return None
        source_url = self._get_thumbnail_source_url()
        return self._current_thumbnail_hash_sync(doc_id, source_url=source_url)

    async def current_thumbnail_hash(self) -> Optional[str]:
        """Async wrapper for current_thumbnail_hash_sync."""
        return await asyncio.to_thread(self.current_thumbnail_hash_sync)

    def get_thumbnail_url(self) -> Optional[str]:
        """
        Get the thumbnail URL for a resource.
        Returns the resource thumbnail endpoint only when the resource has a real
        thumbnail source.

        Returns:
            /resources/{id}/thumbnail URL if thumbnail source exists, None otherwise
        """
        try:
            # Check for restricted access rights
            if self.metadata.get("dct_accessrights_s") == "Restricted":
                self.logger.info("Skipping thumbnail for restricted item")
                return None

            doc_id = self.metadata.get("id")
            if not doc_id:
                return None

            api_base_url = self._api_v1_base_url()
            source_url = self._get_thumbnail_source_url()
            image_hash = self.current_thumbnail_hash_sync()
            if image_hash:
                return f"{api_base_url}/thumbnails/{image_hash}"

            if source_url:
                # Always return the resource-specific thumbnail endpoint
                return f"{api_base_url}/resources/{doc_id}/thumbnail"

            return None

        except Exception as e:
            logger.error(f"Error getting thumbnail URL: {str(e)}")
            return None

    def get_hot_thumbnail_url(self) -> Optional[str]:
        """
        Return only a hot immutable thumbnail asset URL.

        This never falls back to the slower resource resolver endpoint. Callers can
        use this for first-paint critical UI where a cheap placeholder is preferred
        over a blocking thumbnail generation path.
        """
        try:
            if self.metadata.get("dct_accessrights_s") == "Restricted":
                return None

            doc_id = self.metadata.get("id")
            if not doc_id:
                return None

            api_base_url = self._api_v1_base_url()
            image_hash = self.current_thumbnail_hash_sync()
            return f"{api_base_url}/thumbnails/{image_hash}" if image_hash else None
        except Exception as e:
            logger.error(f"Error getting hot thumbnail URL: {str(e)}")
            return None

    def has_cached_image_sync(self, image_hash: str) -> bool:
        """Return True when image bytes exist in Redis or durable visual storage."""
        try:
            image_key = f"image:{image_hash}"
            if self.image_cache.exists(image_key):
                return True
        except Exception as e:
            self.logger.error(f"Error checking cached image: {e}")
        return get_durable_visual_asset(image_hash) is not None

    def _candidate_cached_thumbnail_hash_sync(self, source_url: str) -> Optional[str]:
        """Return the immutable thumbnail hash for a cached source URL, if known."""
        try:
            image_hash = None

            if self._is_cog_url(source_url):
                image_hash = hashlib.sha256(
                    (COG_THUMBNAIL_PREFIX + source_url).encode()
                ).hexdigest()
            elif self._is_pmtiles_url(source_url):
                image_hash = hashlib.sha256(
                    (PMTILES_THUMBNAIL_PREFIX + source_url).encode()
                ).hexdigest()
            elif self._is_manifest_url(source_url):
                manifest_cache_key = f"manifest:{source_url}"
                cached_manifest_data = self.cache.get(manifest_cache_key)
                if cached_manifest_data:
                    manifest_json = json.loads(cached_manifest_data)
                    resolved_url = self._extract_thumbnail_from_manifest_json(
                        manifest_json, source_url
                    )
                    if resolved_url:
                        standardized_url = self._standardize_iiif_url(resolved_url)
                        image_hash = hashlib.sha256(
                            (REMOTE_THUMBNAIL_PREFIX + standardized_url).encode()
                        ).hexdigest()
            else:
                standardized_url = self._standardize_iiif_url(source_url)
                image_hash = hashlib.sha256(
                    (REMOTE_THUMBNAIL_PREFIX + standardized_url).encode()
                ).hexdigest()

            if image_hash and self.has_cached_image_sync(image_hash):
                return image_hash
            return None
        except Exception as e:
            self.logger.debug("Error resolving cached thumbnail hash for %s: %s", source_url, e)
            return None

    def _get_bbox_for_wms(self) -> Optional[str]:
        """Parse dcat_bbox to WMS 1.3.0 BBOX string (minx,miny,maxx,maxy) for EPSG:4326."""
        bbox_raw = self.metadata.get("dcat_bbox")
        if not bbox_raw or not isinstance(bbox_raw, str):
            return None
        bbox_raw = bbox_raw.strip()
        # ENVELOPE(xmin, xmax, ymax, ymin)
        if bbox_raw.upper().startswith("ENVELOPE"):
            envelope_body = bbox_raw[len("ENVELOPE") :].strip()
            if envelope_body.startswith("(") and envelope_body.endswith(")"):
                envelope_parts = [part.strip() for part in envelope_body[1:-1].split(",")]
                if len(envelope_parts) == 4:
                    try:
                        xmin, xmax, ymax, ymin = (float(x) for x in envelope_parts)
                        return f"{xmin},{ymin},{xmax},{ymax}"
                    except (ValueError, TypeError):
                        pass
        # Comma-separated: assume minx,miny,maxx,maxy or minx,maxx,maxy,miny
        parts = [p.strip() for p in bbox_raw.split(",")]
        if len(parts) == 4:
            try:
                a, b, c, d = (float(x) for x in parts)
                # If a < c and b < d then likely minx,miny,maxx,maxy
                if a <= c and b <= d:
                    return f"{a},{b},{c},{d}"
                # Else assume minx,maxx,maxy,miny (ENVELOPE order)
                return f"{a},{d},{b},{c}"
            except (ValueError, TypeError):
                pass
        return None

    def _parse_legacy_references(self) -> Optional[Dict[str, Any]]:
        """
        Parse dct_references_s from metadata when distribution context is empty.
        Used as fallback for OGM-harvested resources that lack resource_distributions rows.
        """
        raw = self.metadata.get("dct_references_s")
        if not raw:
            return None
        if isinstance(raw, dict):
            refs = raw
        elif isinstance(raw, str):
            try:
                refs = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        else:
            return None
        if not isinstance(refs, dict):
            return None
        result = dict(refs)
        for uri in list(result.keys()):
            if uri.startswith("https://iiif.io/"):
                http_uri = "http://" + uri[len("https://") :]
                result.setdefault(http_uri, result[uri])
        return result

    def _get_thumbnail_source_url(
        self, references: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Extract thumbnail source URL from references without making external calls.
        This method only does local string processing - no HTTP requests.

        When distribution context (resource_distributions) is empty, falls back to
        parsing dct_references_s from metadata (e.g. OGM-harvested resources).
        """
        # Fall back to dct_references_s when distribution context is empty
        if references is None and not self.by_uri:
            references = self._parse_legacy_references()

        # Prefer IIIF sources so we can generate our own consistently sized thumbnail
        # instead of inheriting a tiny upstream derivative from b1g_image_ss.
        for iiif_key in ("http://iiif.io/api/image", "https://iiif.io/api/image"):
            iiif_url = self._first_url(iiif_key, references=references)
            if not iiif_url:
                continue

            # Transform ContentDM IIIF URLs
            if url_hostname_matches(iiif_url, "contentdm.oclc.org"):
                # Handle both /digital/iiif/ and /iiif/ patterns
                # Pattern 1: /digital/iiif/collection/id
                match = re.search(r"/digital/iiif/([^/]+)/(\d+)", iiif_url)
                if match:
                    collection, item_id = match.groups()
                    return self._standardize_iiif_url(
                        f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection}:{item_id}"
                    )

                # Pattern 2: /iiif/collection:id/manifest.json or /iiif/collection:id/
                match = re.search(r"/iiif/([^/]+)/", iiif_url)
                if match:
                    collection_item = match.group(1)
                    return self._standardize_iiif_url(
                        f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection_item}"
                    )

            # For non-ContentDM IIIF URLs, use standard format
            return self._standardize_iiif_url(iiif_url)

        # Check for IIIF Manifest - only extract URL, don't fetch manifest
        # Prefer explicit manifest relation keys (http and https)
        manifest_url = self._first_url(
            "http://iiif.io/api/presentation#manifest", references=references
        ) or self._first_url("https://iiif.io/api/presentation#manifest", references=references)

        # If not found, scan values for common manifest endings
        if not manifest_url:
            for value in self._all_reference_urls(references=references):
                if (
                    value.endswith(
                        ("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json")
                    )
                    or "/manifest" in value
                ):
                    manifest_url = value
                    break

        if manifest_url:
            # Special case: ContentDM manifest URLs can be directly converted to image URLs
            # without fetching the manifest, since we know the pattern
            if (
                url_hostname_matches(manifest_url, "contentdm.oclc.org")
                and "/iiif/" in manifest_url
            ):
                # Extract collection:item from ContentDM manifest URL
                # Pattern: https://cdm16022.contentdm.oclc.org/iiif/p16022coll55:1755/manifest.json
                match = re.search(r"/iiif/([^/]+)/", manifest_url)
                if match:
                    collection_item = match.group(1)
                    # Convert to direct IIIF image URL
                    image_url = self._standardize_iiif_url(
                        f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection_item}"
                    )
                    self.logger.info(
                        f"✅ Directly converted ContentDM manifest to image URL: {image_url}"
                    )
                    return image_url

            # For other manifests, queue background resolution and return manifest URL
            # The Celery worker will resolve the manifest and extract the image URL
            self.logger.info(f"🚀 Queueing manifest resolution for {manifest_url}")
            self._queue_manifest_processing(manifest_url)
            return manifest_url

        # Use curated b1g_image_ss only after exhausting IIIF-based options.
        b1g_image_url = self._b1g_image_source_url()
        if b1g_image_url:
            return b1g_image_url

        # Check for direct thumbnail URL first (support http and https keys).
        for thumb_key in ("http://schema.org/thumbnailUrl", "https://schema.org/thumbnailUrl"):
            if url := self._first_url(thumb_key, references=references):
                return url

        # Check for ESRI services (including FeatureLayer for migration routes, etc.)
        for esri_uri in (
            "urn:x-esri:serviceType:ArcGIS#ImageMapLayer",
            "urn:x-esri:serviceType:ArcGIS#TiledMapLayer",
            "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer",
            "urn:x-esri:serviceType:ArcGIS#FeatureLayer",
        ):
            if viewer_endpoint := self._first_url(esri_uri, references=references):
                return f"{viewer_endpoint.rstrip('/')}/info/thumbnail/thumbnail.png"

        # Check for WMS (standard GetMap with BBOX so the layer content is visible)
        if wms_endpoint := self._first_url(
            "http://www.opengis.net/def/serviceType/ogc/wms", references=references
        ):
            layers = self.metadata.get("gbl_wxsidentifier_s") or self.metadata.get(
                "gbl_wxsIdentifier_s", ""
            )
            if not layers:
                layers = ""  # some WMS use single default layer
            bbox_param = self._get_bbox_for_wms()
            if not bbox_param:
                # Fallback without BBOX (server may use full extent)
                bbox_param = "-180,-90,180,90"
            width, height = 400, 300
            base = wms_endpoint.rstrip("/")
            sep = "&" if "?" in base else "?"
            return (
                f"{base}{sep}SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
                f"&LAYERS={layers}&CRS=EPSG:4326&BBOX={bbox_param}"
                f"&WIDTH={width}&HEIGHT={height}&FORMAT=image/png&TRANSPARENT=TRUE"
            )

        # Check for TMS
        if tms_endpoint := self._first_url(
            "http://www.opengis.net/def/serviceType/ogc/tms", references=references
        ):
            return f"{tms_endpoint}/reflect?format=application/vnd.google-earth.kml+xml"

        # Check for COG - use as thumbnail source when no other image available.
        # COG URLs are processed by generate_cog_thumbnail to produce a picture preview.
        cog_uri = "https://github.com/cogeotiff/cog-spec"
        if cog_url := self._first_url(cog_uri, references=references):
            return cog_url

        # Check for PMTiles - use as thumbnail source when no other image available.
        # PMTiles URLs are processed by generate_pmtiles_thumbnail to produce a picture preview.
        pmtiles_uri = "https://github.com/protomaps/PMTiles"
        if pmtiles_url := self._first_url(pmtiles_uri, references=references):
            return pmtiles_url

        # Some GeoBlacklight records use schema.org/image as a curated gallery
        # preview rather than schema.org/thumbnailUrl. Use it as a direct-image
        # fallback after richer/generated map sources such as COG and PMTiles.
        for image_key in ("http://schema.org/image", "https://schema.org/image"):
            if url := self._first_url(image_key, references=references):
                return url

        # Return None when no thumbnail source is found
        # This allows the frontend to show a default icon based on resource class
        # (gbl_resourceClass_sm)
        return None

    def _is_cog_url(self, url: str) -> bool:
        """Check if URL looks like a COG (Cloud Optimized GeoTIFF) URL."""
        if not url:
            return False
        url_lower = url.lower()
        return (
            url_lower.endswith((".tif", ".tiff"))
            or ".tif?" in url_lower
            or "geotiff" in url_lower
            or "display_raster" in url_lower
        )

    def _is_pmtiles_url(self, url: str) -> bool:
        """Check if URL looks like a PMTiles URL."""
        if not url:
            return False
        url_lower = url.lower()
        return url_lower.endswith(".pmtiles") or ".pmtiles?" in url_lower

    def _is_manifest_url(self, url: str) -> bool:
        """Check if URL looks like a IIIF manifest URL."""
        if not url:
            return False
        url_lower = url.lower()
        # Check for common IIIF manifest patterns
        return (
            url.endswith(("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json"))
            or "/manifest" in url
            or (
                ".json" in url
                and ("iiif" in url_lower or "/object/" in url or "/collection/" in url)
            )
            or ("/api/" in url and ("iiif" in url_lower or "image" in url_lower))
            or ("/cgi/i/image/api/" in url_lower)  # U of Michigan pattern
        )

    def _first_url(self, uri: str, references: Optional[Dict[str, Any]] = None) -> Optional[str]:
        # Prefer distribution context if available and no explicit references provided
        if references is None:
            records = self.by_uri.get(uri, [])
            if records:
                return records[0].url
        else:
            # If explicit references are provided, consult those first
            val = references.get(uri)
            if isinstance(val, str):
                return val
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    return first.get("url") or first.get("@id") or first.get("id")
            if isinstance(val, dict):
                return val.get("url") or val.get("@id") or val.get("id")
            # If not found in provided references, fall back to distribution context
            records = self.by_uri.get(uri, [])
            if records:
                return records[0].url
        return None

    def _all_reference_urls(self, references: Optional[Dict[str, Any]] = None) -> List[str]:
        urls: List[str] = []
        if references is not None:
            for val in references.values():
                if isinstance(val, str):
                    urls.append(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            urls.append(item)
                        elif isinstance(item, dict):
                            u = item.get("url") or item.get("@id") or item.get("id")
                            if u:
                                urls.append(u)
                elif isinstance(val, dict):
                    u = val.get("url") or val.get("@id") or val.get("id")
                    if u:
                        urls.append(u)
        else:
            for records in self.by_uri.values():
                for record in records:
                    urls.append(record.url)
        return urls

    def _queue_thumbnail_processing(self, thumbnail_url: str, doc_id: str) -> None:
        """
        Queue thumbnail processing in the background without blocking.
        This method is fire-and-forget.
        """
        try:
            if not acquire_thumbnail_queue_slot(doc_id, thumbnail_url):
                self.logger.info(f"Thumbnail task already queued for {doc_id}: {thumbnail_url}")
                safe_record_thumbnail_state_sync(
                    ThumbnailStatePayload(
                        resource_id=doc_id,
                        state=ThumbnailState.QUEUED,
                        source_type=infer_source_type(thumbnail_url),
                        source_url=thumbnail_url,
                        state_detail="Thumbnail fetch already queued; waiting for existing task",
                    )
                )
                return

            # LIGHTNING SPEED OPTIMIZATION: Skip validation, queue immediately
            # The Celery worker will handle validation and caching
            from app.tasks.worker import fetch_and_cache_image

            task = fetch_and_cache_image.delay(thumbnail_url, doc_id)
            self.logger.info(f"Task queued for {doc_id}: {task.id}")
            safe_record_thumbnail_state_sync(
                ThumbnailStatePayload(
                    resource_id=doc_id,
                    state=ThumbnailState.QUEUED,
                    source_type=infer_source_type(thumbnail_url),
                    source_url=thumbnail_url,
                    queue_task_id=task.id,
                    state_detail="Queued thumbnail fetch task",
                )
            )

        except Exception as e:
            self.logger.error(f"Failed to queue thumbnail processing for {doc_id}: {e}")
            # Don't raise - this is a background operation that shouldn't fail the main request

    def _queue_manifest_processing(self, manifest_url: str) -> None:
        """
        Queue manifest processing in the background without blocking.
        This method is fire-and-forget.
        """
        try:
            from app.tasks.worker import fetch_and_cache_image

            task = fetch_and_cache_image.delay(manifest_url)
            self.logger.info(f"Manifest resolution queued: {task.id}")

        except Exception as e:
            self.logger.error(f"Failed to queue manifest processing for {manifest_url}: {e}")
            # Don't raise - this is a background operation that shouldn't fail the main request

    async def get_cached_image(self, image_hash: str) -> Optional[bytes]:
        """Retrieve a cached image by its hash."""
        image_key = f"image:{image_hash}"
        try:
            image_data = await asyncio.to_thread(self.image_cache.get, image_key)
            if image_data:
                self.logger.debug(f"Serving cached image {image_hash}")
                return image_data
        except Exception as e:
            self.logger.error(f"Error retrieving cached image: {e}")

        durable = await asyncio.to_thread(get_durable_visual_asset, image_hash)
        if durable:
            image_bytes, content_type = durable
            await asyncio.to_thread(cache_visual_asset, self.image_cache, image_key, image_bytes)
            await asyncio.to_thread(
                cache_visual_asset,
                self.image_cache,
                f"image_type:{image_hash}",
                content_type,
            )
            self.logger.debug(f"Rehydrated cached image {image_hash} from durable store")
            return image_bytes
        return None

    async def has_cached_image(self, image_hash: str) -> bool:
        """Return True when image bytes exist in Redis or durable visual storage."""
        try:
            image_key = f"image:{image_hash}"
            exists = await asyncio.to_thread(self.image_cache.exists, image_key)
            if exists:
                return True
        except Exception as e:
            self.logger.error(f"Error checking cached image: {e}")
        return await asyncio.to_thread(get_durable_visual_asset, image_hash) is not None

    def is_pmtiles_skip_cached(self, image_hash: str) -> bool:
        """
        Check if PMTiles thumbnail generation was skipped (e.g. vector tiles).
        When True, the endpoint should redirect to static map instead of re-queuing.
        """
        try:
            return bool(self.image_cache.exists(f"pmtiles_skip_v2:{image_hash}"))
        except Exception:
            return False

    async def get_iiif_image(self, image_url: str) -> Optional[bytes]:
        """
        Get image data from a IIIF image URL.

        Args:
            image_url: The IIIF image URL

        Returns:
            Image data in bytes, or None if retrieval fails
        """
        try:
            # Remove /info.json from URL if present
            base_url = image_url.replace("/info.json", "")

            # Get a full-size image for better OCR results
            image_url = f"{base_url}/full/full/0/default.jpg"

            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        logger.info(f"Successfully retrieved IIIF image from {image_url}")
                        return image_data
                    else:
                        logger.error(f"Failed to retrieve IIIF image: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error retrieving IIIF image: {str(e)}")
            return None

    async def download_image(self, url: str) -> Optional[bytes]:
        """
        Download an image from a URL.

        Args:
            url: The image URL

        Returns:
            Image data in bytes, or None if download fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        # Check if it's an image
                        content_type = response.headers.get("content-type", "").lower()
                        if not content_type.startswith("image/"):
                            logger.warning(
                                f"URL {url} is not an image (content-type: {content_type})"
                            )
                            return None

                        image_data = await response.read()
                        logger.info(f"Successfully downloaded image from {url}")
                        return image_data
                    else:
                        logger.error(f"Failed to download image: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error downloading image: {str(e)}")
            return None
