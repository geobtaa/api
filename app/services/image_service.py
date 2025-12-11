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

from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
)

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

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
            headers = {
                "User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"
            }
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
                    return image["@id"]

                # Fallback to image service @id to construct consistent size
                service_id = image.get("service", {}).get("@id")
                if service_id:
                    return f"{service_id}/full/400,/0/default.jpg"

            # Items - IIIF v3 style
            elif manifest_json.get("items"):
                # Check for thumbnail in first canvas (items[0].thumbnail)
                first_canvas = (
                    manifest_json.get("items", [{}])[0]
                    if manifest_json.get("items")
                    else {}
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
                        return f"{body_service_id}/full/400,/0/default.jpg"

                    # Next try body.id (prefer direct ID unmodified)
                    if body.get("id"):
                        self.logger.debug(f"Found body ID: {body.get('id')}")
                        return body["id"]

                # Try direct id
                if items_path.get("id"):
                    self.logger.debug(f"Found items path ID: {items_path.get('id')}")
                    return items_path["id"]

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
        Converts various IIIF image URLs to a standard 400px wide version.
        """
        try:
            # Skip if not a likely IIIF URL
            if not any(x in url.lower() for x in ["/iiif/", "/image/", "info.json"]):
                return url

            # If URL points to info.json, convert to a standard image URL
            if url.endswith("/info.json"):
                return url[:-10] + "/full/400,/0/default.jpg"

            # Preserve Stanford IIIF URLs that already include sizing or '!'
            if "stacks.stanford.edu" in url and ("/full/!" in url or "/full/400," in url):
                return url

            # If URL already contains /full/, replace everything after it with our standard path
            if "/full/" in url:
                prefix = url.split("/full/")[0]
                return f"{prefix}/full/400,/0/default.jpg"

            # As a final fallback, return original URL
            return url
        except Exception as e:
            self.logger.error(f"Error standardizing IIIF URL {url}: {e}")
            return url

    def get_thumbnail_url(self) -> Optional[str]:
        """
        Get the thumbnail URL from document metadata with caching support.
        This method is now truly async - it only checks cache and queues background jobs.
        No external HTTP calls are made during this method execution.

        Returns:
            Cached thumbnail URL if available, placeholder URL if queued,
            None if no thumbnail source
        """
        try:
            # Check for restricted access rights
            if self.metadata.get("dct_accessrights_s") == "Restricted":
                self.logger.info("Skipping thumbnail for restricted item")
                return None

            doc_id = self.metadata.get("id")
            if not doc_id:
                return None

            # Determine the source thumbnail URL without making external calls
            thumbnail_url = self._get_thumbnail_source_url()

            if thumbnail_url:
                # For manifest URLs, check if we have a cached resolution
                # If manifest is cached, we can resolve it synchronously to check image cache
                # Otherwise, queue it for background processing (no blocking HTTP calls)
                if self._is_manifest_url(thumbnail_url):
                    # Check if manifest is cached first (no HTTP request)
                    manifest_cache_key = f"manifest:{thumbnail_url}"
                    try:
                        cached_manifest_data = self.cache.get(manifest_cache_key)
                        if cached_manifest_data:
                            # Manifest is cached, safe to resolve synchronously
                            try:
                                manifest_json = json.loads(cached_manifest_data)
                                resolved_url = self._extract_thumbnail_from_manifest_json(
                                    manifest_json, thumbnail_url
                                )
                                if resolved_url:
                                    resolved_url = self._standardize_iiif_url(resolved_url)
                                    
                                    # Check if the resolved image URL is already cached
                                    image_hash = hashlib.sha256(resolved_url.encode()).hexdigest()
                                    image_key = f"image:{image_hash}"
                                    
                                    if self.image_cache.exists(image_key):
                                        self.logger.info(
                                            f"🚀 Cache HIT for resolved manifest image {doc_id}"
                                        )
                                        return (
                                            f"{self.application_url}/api/v1/thumbnails/{image_hash}"
                                        )
                            except Exception as e:
                                # If resolution fails, queue for background processing
                                self.logger.debug(
                                    f"Failed to resolve cached manifest for {doc_id}: {e}"
                                )
                    except Exception as e:
                        # If Redis is unavailable, fall back to non-cached behavior
                        self.logger.debug(
                            f"Redis unavailable while checking manifest cache "
                            f"for {doc_id}: {e}"
                        )
                    
                    # Manifest not cached or resolution failed - queue for background processing
                    # DO NOT fetch manifest synchronously - this blocks the API response
                    self.logger.info(
                        f"🚀 Queueing manifest resolution for {doc_id}: {thumbnail_url}"
                    )
                    self._queue_thumbnail_processing(thumbnail_url, doc_id)
                    
                    # Return None - frontend will use resource class icon until ready
                    return None
                else:
                    # Direct image URL - standardize and check cache
                    thumbnail_url = self._standardize_iiif_url(thumbnail_url)

                    # Check if we have the image cached
                    image_hash = hashlib.sha256(thumbnail_url.encode()).hexdigest()
                    image_key = f"image:{image_hash}"

                    try:
                        if self.image_cache.exists(image_key):
                            self.logger.info(f"🚀 Cache HIT for image {doc_id}")
                            return f"{self.application_url}/api/v1/thumbnails/{image_hash}"
                    except Exception as e:
                        # If Redis is unavailable, fall back to non-cached behavior
                        self.logger.warning(
                            f"Redis unavailable while checking cache for {doc_id}: {e}"
                        )

                    # Queue thumbnail for processing in the background
                    # Return None so frontend can show resource class icon until thumbnail is ready
                    self.logger.info(f"🚀 Queueing image fetch for {doc_id}: {thumbnail_url}")
                    self._queue_thumbnail_processing(thumbnail_url, doc_id)

                    # Return None instead of placeholder - frontend will use resource class icon
                    return None

            return None

        except Exception as e:
            logger.error(f"Error getting thumbnail URL: {str(e)}")
            return None

    def _get_thumbnail_source_url(
        self, references: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Extract thumbnail source URL from references without making external calls.
        This method only does local string processing - no HTTP requests.
        """
        # Check for direct thumbnail URL first (support http and https keys)
        for thumb_key in ("http://schema.org/thumbnailUrl", "https://schema.org/thumbnailUrl"):
            if url := self._first_url(thumb_key, references=references):
                return url

        # Check for IIIF thumbnail URL
        for iiif_key in ("http://iiif.io/api/image", "https://iiif.io/api/image"):
            iiif_url = self._first_url(iiif_key, references=references)
            if not iiif_url:
                continue

            # Transform ContentDM IIIF URLs
            if "contentdm.oclc.org" in iiif_url:
                # Handle both /digital/iiif/ and /iiif/ patterns
                # Pattern 1: /digital/iiif/collection/id
                match = re.search(r"/digital/iiif/([^/]+)/(\d+)", iiif_url)
                if match:
                    collection, item_id = match.groups()
                    return f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection}:{item_id}/full/200,/0/default.jpg"

                # Pattern 2: /iiif/collection:id/manifest.json or /iiif/collection:id/
                match = re.search(r"/iiif/([^/]+)/", iiif_url)
                if match:
                    collection_item = match.group(1)
                    return f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection_item}/full/200,/0/default.jpg"

            # For non-ContentDM IIIF URLs, use standard format
            return f"{iiif_url}/full/200,/0/default.jpg"

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
            if "contentdm.oclc.org" in manifest_url and "/iiif/" in manifest_url:
                # Extract collection:item from ContentDM manifest URL
                # Pattern: https://cdm16022.contentdm.oclc.org/iiif/p16022coll55:1755/manifest.json
                match = re.search(r"/iiif/([^/]+)/", manifest_url)
                if match:
                    collection_item = match.group(1)
                    # Convert to direct IIIF image URL
                    image_url = f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection_item}/full/400,/0/default.jpg"
                    self.logger.info(
                        f"✅ Directly converted ContentDM manifest to image URL: {image_url}"
                    )
                    return image_url

            # For other manifests, queue background resolution and return manifest URL
            # The Celery worker will resolve the manifest and extract the image URL
            self.logger.info(f"🚀 Queueing manifest resolution for {manifest_url}")
            self._queue_manifest_processing(manifest_url)
            return manifest_url

        # Check for ESRI services
        for esri_uri in (
            "urn:x-esri:serviceType:ArcGIS#ImageMapLayer",
            "urn:x-esri:serviceType:ArcGIS#TiledMapLayer",
            "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer",
        ):
            if viewer_endpoint := self._first_url(esri_uri, references=references):
                return f"{viewer_endpoint}/info/thumbnail/thumbnail.png"

        # Check for WMS
        if wms_endpoint := self._first_url(
            "http://www.opengis.net/def/serviceType/ogc/wms", references=references
        ):
            width = 200
            height = 200
            layers = self.metadata.get("gbl_wxsidentifier_s", "")
            return (
                f"{wms_endpoint}/reflect?"
                f"FORMAT=image/png&"
                f"TRANSPARENT=TRUE&"
                f"WIDTH={width}&"
                f"HEIGHT={height}&"
                f"LAYERS={layers}"
            )

        # Check for TMS
        if tms_endpoint := self._first_url(
            "http://www.opengis.net/def/serviceType/ogc/tms", references=references
        ):
            return f"{tms_endpoint}/reflect?format=application/vnd.google-earth.kml+xml"

        # Return None when no thumbnail source is found
        # This allows the frontend to show a default icon based on resource class
        # (gbl_resourceClass_sm)
        return None

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
            # LIGHTNING SPEED OPTIMIZATION: Skip validation, queue immediately
            # The Celery worker will handle validation and caching
            from app.tasks.worker import fetch_and_cache_image

            task = fetch_and_cache_image.delay(thumbnail_url)
            self.logger.info(f"Task queued for {doc_id}: {task.id}")

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
        try:
            image_key = f"image:{image_hash}"
            image_data = self.image_cache.get(image_key)
            if image_data:
                self.logger.debug(f"Serving cached image {image_hash}")
                return image_data
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving cached image: {e}")
            return None

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
