#!/usr/bin/env python
"""
Clear Redis cache by type using tag-based invalidation.

Use this when HTTP access to the admin cache-clear endpoint is not available
(e.g. from kamal app exec where the container cannot reach the public API URL).
The script connects directly to Redis and invalidates cache entries by tag.

Cache types: search, resource, suggest, map, all

Usage:
    python scripts/clear_cache_by_type.py [cache_type]
    python scripts/clear_cache_by_type.py search
    python scripts/clear_cache_by_type.py all
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description="Clear cache by type (search, resource, suggest, map, all)"
    )
    parser.add_argument(
        "cache_type",
        nargs="?",
        default="search",
        choices=["search", "resource", "suggest", "map", "all"],
        help="Cache type to clear (default: search)",
    )
    args = parser.parse_args()

    from app.services.admin_service import CacheManagementService

    service = CacheManagementService()
    result = await service.clear_cache_by_type(args.cache_type)
    logger.info(result.get("message", "Cache cleared"))


if __name__ == "__main__":
    asyncio.run(main())
