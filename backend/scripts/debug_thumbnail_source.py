#!/usr/bin/env python3
"""
Debug thumbnail source for a resource. Prints what source URL is used and why.

Usage:
  python scripts/debug_thumbnail_source.py 10b-55087-01
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(resource_id: str):
    from app.api.v1.utils import sanitize_for_json
    from app.services.distribution_repository import (
        async_session_factory,
        fetch_distribution_context,
    )
    from app.services.image_service import ImageService
    from db.models import resources

    async with async_session_factory() as session:
        result = await session.execute(select(resources).where(resources.c.id == resource_id))
        row = result.fetchone()
        if not row:
            print(f"Resource not found: {resource_id}")
            return
        resource_dict = sanitize_for_json(dict(row._mapping))

    b1g = resource_dict.get("b1g_image_ss")
    print(f"b1g_image_ss raw value: {repr(b1g)} (type: {type(b1g).__name__})")

    distribution_context = await fetch_distribution_context(resource_id)
    image_service = ImageService(resource_dict, distribution_context=distribution_context)
    source_url = image_service._get_thumbnail_source_url()

    print(f"Thumbnail source URL: {source_url}")
    if source_url and b1g:
        print("(b1g_image_ss was used)")
    elif source_url:
        print("(fallback source used - b1g_image_ss absent or invalid)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_thumbnail_source.py RESOURCE_ID")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
