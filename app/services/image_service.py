import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, Optional

import aiohttp
import redis
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class ImageService:
    """Service for handling different types of image assets."""

    def __init__(self, metadata: Dict[str, Any]):
        """
        Initialize the image service with document metadata.

        Args:
            metadata: Document metadata dictionary
        """
        self.metadata = metadata

        # Setup Redis connection
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.application_url = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")
        self.cache = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=os.getenv("REDIS_PASSWORD"),
            db=0,
            decode_responses=True,
        )
        self.cache_ttl = int(os.getenv("REDIS_TTL", 604800))  # 7 days in seconds

        # Setup binary Redis connection for images
        self.image_cache = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=os.getenv("REDIS_PASSWORD"),
            db=1,  # Use different DB for images
            decode_responses=False,
        )

        # Setup logging
        self.logger = logging.getLogger("ImageService")
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
            response = requests.get(manifest_url, timeout=2.0)
            response.raise_for_status()
            manifest_data = response.json()

            # Cache the manifest
            self.cache.setex(cache_key, self.cache_ttl, json.dumps(manifest_data))
            return manifest_data
        except Exception as e:
            self.logger.error(f"Error fetching manifest {manifest_url}: {e}")
            return None

    def get_iiif_manifest_thumbnail(self, manifest_url: str) -> Optional[str]:
        """
        Get thumbnail URL from IIIF Manifest.

        Args:
            manifest_url (str): URL to the IIIF manifest

        Returns:
            Optional[str]: Thumbnail URL or None if not found
        """
        manifest_json = self._get_manifest(manifest_url)
        if not manifest_json:
            return manifest_url

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
                items_path = (
                    manifest_json.get("items", [{}])[0].get("items", [{}])[0].get("items", [{}])[0]
                )

                # Try body.service.@id first (prefer constructing consistent size)
                body = items_path.get("body", {})
                body_service_id = (
                    body.get("service", {}).get("@id") if isinstance(body, dict) else None
                )
                if body_service_id:
                    return f"{body_service_id}/full/400,/0/default.jpg"

                # Next try body.id (prefer direct ID unmodified)
                if isinstance(body, dict) and body.get("id"):
                    self.logger.debug("Image: items body id")
                    return body["id"]

                # Try direct id
                elif items_path.get("id"):
                    self.logger.debug("Image: items id")
                    return items_path["id"]

            # Thumbnail - Try various thumbnail formats
            elif manifest_json.get("thumbnail"):
                # Already handled above, but keep for safety
                thumbnail = manifest_json["thumbnail"]
                if isinstance(thumbnail, dict):
                    candidate = thumbnail.get("@id") or thumbnail.get("id")
                else:
                    candidate = thumbnail
                return self._standardize_iiif_url(candidate) if candidate else None

            # Fallback to viewer endpoint
            self.logger.debug("Image: failed to find thumbnail")
            return manifest_url

        except Exception as e:
            self.logger.error(f"Error processing IIIF manifest: {e}")
            return manifest_url

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

            # Parse references if needed
            references = self.metadata.get("dct_references_s", {})
            if isinstance(references, str):
                try:
                    references = json.loads(references)
                except json.JSONDecodeError:
                    logger.error("Failed to parse references JSON")
                    return None

            if not isinstance(references, dict):
                return None

            # Determine the source thumbnail URL without making external calls
            thumbnail_url = self._get_thumbnail_source_url(references)

            if thumbnail_url:
                # For manifest URLs, we can't check cache yet since we don't know the resolved URL
                # For direct image URLs, standardize and check cache
                if not self._is_manifest_url(thumbnail_url):
                    # Standardize IIIF URLs to ensure consistent size
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
                        self.logger.warning(f"Redis unavailable while checking cache for {doc_id}: {e}")

                # LIGHTNING SPEED OPTIMIZATION: Skip validation, queue immediately
                # The Celery worker will handle validation and caching
                self.logger.info(f"🚀 Queueing image fetch for {doc_id}: {thumbnail_url}")
                self._queue_thumbnail_processing(thumbnail_url, doc_id)

                # Return placeholder image URL - this ensures fast response times
                return f"{self.application_url}/api/v1/thumbnails/placeholder"

            return None

        except Exception as e:
            logger.error(f"Error getting thumbnail URL: {str(e)}")
            return None

    def _get_thumbnail_source_url(self, references: Dict) -> Optional[str]:
        """
        Extract thumbnail source URL from references without making external calls.
        This method only does local string processing - no HTTP requests.
        """
        # Check for direct thumbnail URL first (support http and https keys)
        for thumb_key in ("http://schema.org/thumbnailUrl", "https://schema.org/thumbnailUrl"):
            if thumb_key in references:
                thumbnail_url = references[thumb_key]
                if isinstance(thumbnail_url, list) and thumbnail_url:
                    return thumbnail_url[0]
                return thumbnail_url

        # Check for IIIF thumbnail URL
        if any(k in references for k in ("http://iiif.io/api/image", "https://iiif.io/api/image")):
            iiif_key = (
                "http://iiif.io/api/image"
                if "http://iiif.io/api/image" in references
                else "https://iiif.io/api/image"
            )
            iiif_url = references[iiif_key]
            if isinstance(iiif_url, list) and iiif_url:
                iiif_url = iiif_url[0]

            # Transform ContentDM IIIF URLs
            if "contentdm.oclc.org" in iiif_url:
                # Extract collection and item ID from the URL
                match = re.search(r"/digital/iiif/([^/]+)/(\d+)", iiif_url)
                if match:
                    collection, item_id = match.groups()
                    # Construct the correct IIIF URL format
                    return f"https://cdm16022.contentdm.oclc.org/iiif/2/{collection}:{item_id}/full/200,/0/default.jpg"

            # For non-ContentDM IIIF URLs, use standard format
            return f"{iiif_url}/full/200,/0/default.jpg"

        # Check for IIIF Manifest - only extract URL, don't fetch manifest
        # Prefer explicit manifest relation keys (http and https)
        manifest_url = (
            references.get("http://iiif.io/api/presentation#manifest")
            or references.get("https://iiif.io/api/presentation#manifest")
            or references.get("https://iiif.io/api/presentation/2/context.json")
        )

        # If not found, scan values for common manifest endings
        if not manifest_url:
            for value in references.values():
                if isinstance(value, str) and (
                    value.endswith(
                        ("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json")
                    )
                    or "/manifest" in value
                ):
                    manifest_url = value
                    break

        if manifest_url:
            # For manifests, queue background resolution and return manifest URL
            # The Celery worker will resolve the manifest and extract the image URL
            self.logger.info(f"🚀 Queueing manifest resolution for {manifest_url}")
            self._queue_manifest_processing(manifest_url)
            return manifest_url

        # Check for ESRI services
        if "urn:x-esri:serviceType:ArcGIS#ImageMapLayer" in references:
            viewer_endpoint = references["urn:x-esri:serviceType:ArcGIS#ImageMapLayer"]
            return f"{viewer_endpoint}/info/thumbnail/thumbnail.png"
        if "urn:x-esri:serviceType:ArcGIS#TiledMapLayer" in references:
            viewer_endpoint = references["urn:x-esri:serviceType:ArcGIS#TiledMapLayer"]
            return f"{viewer_endpoint}/info/thumbnail/thumbnail.png"
        if "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer" in references:
            viewer_endpoint = references["urn:x-esri:serviceType:ArcGIS#DynamicMapLayer"]
            return f"{viewer_endpoint}/info/thumbnail/thumbnail.png"

        # Check for WMS
        if "http://www.opengis.net/def/serviceType/ogc/wms" in references:
            wms_endpoint = references["http://www.opengis.net/def/serviceType/ogc/wms"]
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
        if "http://www.opengis.net/def/serviceType/ogc/tms" in references:
            tms_endpoint = references["http://www.opengis.net/def/serviceType/ogc/tms"]
            return f"{tms_endpoint}/reflect?format=application/vnd.google-earth.kml+xml"

        return None

    def _is_manifest_url(self, url: str) -> bool:
        """Check if URL looks like a IIIF manifest URL."""
        if not url:
            return False
        return (
            url.endswith(("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json"))
            or "/manifest" in url
        )

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
