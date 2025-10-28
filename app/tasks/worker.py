import hashlib
import logging
import os
from typing import Optional

import redis
import requests
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.getenv("LOG_PATH", "logs"), "app.log"), mode="a", encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)

# Setup Celery
celery_app = Celery(
    "tasks",
    broker=f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/0",
    backend=f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/0",
)

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
def fetch_and_cache_image(self, url: str) -> bool:
    """
    Fetch image from URL and store in Redis.
    Returns True if successful, False otherwise.
    """
    logger.info(f"Starting task to fetch image: {url}")
    try:
        # Generate consistent key for image (always based on original URL)
        image_key = f"image:{hashlib.sha256(url.encode()).hexdigest()}"

        # Check if already cached, but tolerate Redis outages
        redis_available = True
        try:
            if redis_client.exists(image_key):
                logger.info(f"Image already cached: {url}")
                return True
        except Exception as redis_err:
            redis_available = False
            logger.warning(f"Redis unavailable during exists() for {url}: {redis_err}")

        # Determine the actual image URL; handle IIIF manifests by resolving to a thumbnail
        resolved_url = _resolve_image_url(url)
        logger.info(f"Fetching image: {resolved_url}")
        response = requests.get(resolved_url, timeout=15)
        response.raise_for_status()

        # Cache image if Redis is available; otherwise, skip caching without retry storms
        if redis_available:
            try:
                ttl = int(os.getenv("REDIS_TTL", 604800))  # 7 days default
                redis_client.setex(image_key, ttl, response.content)
                logger.info(f"Successfully cached image: {url}")
                return True
            except Exception as redis_err:
                logger.warning(f"Failed to cache image due to Redis error for {url}: {redis_err}")
                return False
        else:
            logger.warning(f"Skipping cache store for {url}: Redis unavailable")
            return False
    except requests.RequestException as http_err:
        logger.error(f"HTTP error caching image {url}: {http_err}")
        self.retry(exc=http_err, countdown=60, max_retries=3)
        return False
    except Exception as e:
        logger.error(f"Unexpected error caching image {url}: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)
        return False


def _looks_like_manifest_url(url: str) -> bool:
    """Heuristic to detect IIIF manifest URLs by path patterns."""
    lowered = url.lower()
    return (
        "/iiif/manifest" in lowered
        or "/iiif3/manifest" in lowered
        or "presentation" in lowered
        and lowered.endswith((".json", "/manifest"))
        or lowered.endswith("/manifest")
        or lowered.endswith("manifest.json")
    )


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
