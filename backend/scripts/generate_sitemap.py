#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.sitemap_service import close_store, generate_and_store
from db.database import database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def _main() -> int:
    await database.connect()
    try:
        result, stored = await generate_and_store()
        payload = result.manifest(stored=stored)
        logger.info("Generated sitemap payload: %s", json.dumps(payload, sort_keys=True))
        print(json.dumps(payload, sort_keys=True))
        return 0 if stored else 1
    finally:
        await database.disconnect()
        await close_store()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
