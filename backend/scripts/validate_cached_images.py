#!/usr/bin/env python3
"""
Script to validate cached thumbnail images and remove invalid entries.

This script checks all cached images in Redis and removes entries that are not valid images.
"""

import io
import logging
import os
import sys

import redis
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def is_valid_image(content: bytes) -> bool:
    """Check if content is a valid image."""
    if not content or len(content) < 4:
        return False

    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        return True
    except Exception:
        return False


def validate_cached_images(dry_run: bool = True):
    """Validate all cached images and optionally remove invalid ones."""
    # Setup Redis connection
    # Try to detect if we're running in Docker or locally
    # If IS_DOCKER is set, use 'redis' as host (Docker network)
    # Otherwise, try localhost first, then fall back to 'redis'
    is_docker = os.getenv("IS_DOCKER", "").lower() in ("true", "1", "yes")

    if is_docker:
        redis_host = os.getenv("REDIS_HOST", "redis")
    else:
        # Try localhost first (for Docker port mapping)
        redis_host = os.getenv("REDIS_HOST", "localhost")

    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD")

    logger.info(f"Connecting to Redis at {redis_host}:{redis_port} (Docker mode: {is_docker})")

    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=1,  # Image cache DB
            decode_responses=False,
            socket_connect_timeout=5,
        )
        # Test connection
        redis_client.ping()
    except redis.exceptions.ConnectionError as e:
        if not is_docker and redis_host == "localhost":
            # Try connecting to Docker Redis if localhost fails
            logger.warning(f"Failed to connect to localhost: {e}")
            logger.info("Attempting to connect via Docker...")
            try:
                redis_host = "redis"
                redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=1,
                    decode_responses=False,
                    socket_connect_timeout=5,
                )
                redis_client.ping()
                logger.info("Connected via Docker network hostname 'redis'")
            except redis.exceptions.ConnectionError:
                logger.error(
                    "❌ Cannot connect to Redis. Options:\n"
                    "1. Run inside Docker: docker-compose exec api "
                    "python scripts/validate_cached_images.py\n"
                    "2. Or ensure Redis is accessible at localhost:6379 "
                    "(check docker-compose.yml port mapping)\n"
                    "3. Or set REDIS_HOST and REDIS_PORT environment variables"
                )
                raise
        else:
            logger.error(f"❌ Cannot connect to Redis at {redis_host}:{redis_port}: {e}")
            logger.error(
                "\n💡 Try running inside Docker:\n"
                "   docker-compose exec api python scripts/validate_cached_images.py"
            )
            raise

    logger.info("Scanning Redis for cached images...")

    # Scan all keys that start with "image:"
    cursor = 0
    total_checked = 0
    invalid_count = 0
    valid_count = 0

    while True:
        cursor, keys = redis_client.scan(cursor, match="image:*", count=100)

        for key in keys:
            total_checked += 1
            key_str = key.decode() if isinstance(key, bytes) else key
            image_hash = key_str.split(":", 1)[1] if ":" in key_str else key_str

            try:
                image_data = redis_client.get(key)

                if not image_data:
                    logger.warning(f"Empty cache entry: {key_str}")
                    if not dry_run:
                        redis_client.delete(key)
                        logger.info(f"Deleted empty entry: {key_str}")
                    invalid_count += 1
                    continue

                if is_valid_image(image_data):
                    valid_count += 1
                    if total_checked % 100 == 0:
                        logger.info(
                            f"Checked {total_checked} images... "
                            f"({valid_count} valid, {invalid_count} invalid)"
                        )
                else:
                    invalid_count += 1
                    logger.warning(
                        f"❌ Invalid image: {key_str} (hash: {image_hash}, "
                        f"size: {len(image_data)} bytes, "
                        f"first_bytes: {image_data[:100]!r})"
                    )

                    if not dry_run:
                        # Also delete the associated type key if it exists
                        type_key = f"image_type:{image_hash}"
                        redis_client.delete(key, type_key)
                        logger.info(f"Deleted invalid entry: {key_str} and {type_key}")

            except Exception as e:
                logger.error(f"Error checking {key_str}: {e}")
                invalid_count += 1

        if cursor == 0:
            break

    logger.info(
        f"\n=== Validation Complete ==="
        f"\nTotal checked: {total_checked}"
        f"\nValid images: {valid_count}"
        f"\nInvalid entries: {invalid_count}"
    )

    if dry_run:
        logger.info("\nThis was a dry run. Run with --fix to remove invalid entries.")
    else:
        logger.info(f"\nRemoved {invalid_count} invalid entries from cache.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate cached thumbnail images",
        epilog="""
Examples:
  # Run inside Docker (recommended):
  docker-compose exec api python scripts/validate_cached_images.py
  
  # Run inside Docker and fix invalid entries:
  docker-compose exec api python scripts/validate_cached_images.py --fix
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually remove invalid entries (default is dry run)",
    )

    args = parser.parse_args()

    try:
        validate_cached_images(dry_run=not args.fix)
    except redis.exceptions.ConnectionError:
        logger.error("\n💡 Redis connection failed. Try running inside Docker:")
        logger.error("   docker-compose exec api python scripts/validate_cached_images.py")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
