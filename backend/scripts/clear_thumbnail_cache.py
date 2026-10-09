#!/usr/bin/env python3
"""
Clear cached thumbnail for a resource so it can be regenerated.

Invalidates the current source-to-thumbnail mapping in durable storage and Redis.
Existing immutable image bytes remain available. For routine refresh, prefer
prime_thumbnail_cache.py --force so the old image remains usable until success.

Usage:
  python scripts/clear_thumbnail_cache.py b1g_PJxxfKgpqpUT
  python scripts/clear_thumbnail_cache.py b1g_abc123 b1g_def456  # multiple
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def clear_thumbnail_for_resource(resource_id: str) -> bool:
    """Clear thumbnail cache for one resource. Returns True if keys were deleted."""
    from app.api.v1.utils import _get_thumbnail_asset_url, sanitize_for_json
    from app.services.distribution_repository import (
        async_session_factory,
        fetch_distribution_context,
    )
    from app.services.image_service import ImageService
    from app.services.thumbnail_capture import invalidate_thumbnail
    from db.models import resources

    async with async_session_factory() as session:
        result = await session.execute(select(resources).where(resources.c.id == resource_id))
        row = result.fetchone()
        if not row:
            logger.warning(f"Resource not found: {resource_id}")
            return False

        resource_dict = sanitize_for_json(dict(row._mapping))

    distribution_context = await fetch_distribution_context(resource_id)
    image_service = ImageService(resource_dict, distribution_context=distribution_context)
    image_service._queue_manifest_processing = lambda _url: None
    source_url = image_service.resolve_thumbnail_source_url(
        thumbnail_asset_url=await _get_thumbnail_asset_url(resource_id)
    )

    if not source_url:
        logger.warning(f"No thumbnail source for {resource_id}")
        return False

    return await asyncio.to_thread(
        invalidate_thumbnail, resource_id, source_url, cache=image_service.image_cache
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/clear_thumbnail_cache.py RESOURCE_ID [RESOURCE_ID ...]")
        sys.exit(1)

    resource_ids = sys.argv[1:]
    cleared = 0
    for rid in resource_ids:
        try:
            if asyncio.run(clear_thumbnail_for_resource(rid)):
                cleared += 1
        except Exception as e:
            logger.error(f"Failed for {rid}: {e}")
            raise

    print(f"Cleared cache for {cleared}/{len(resource_ids)} resource(s)")


if __name__ == "__main__":
    main()
