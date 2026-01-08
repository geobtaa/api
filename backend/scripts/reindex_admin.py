#!/usr/bin/env python3
"""
Reindex via the *same code path* as the /admin/reindex endpoint.

This intentionally calls:
  app.elasticsearch.index.reindex_resources()

Unlike backend/scripts/reindex.py (the resilient reindexer), this uses the
endpoint's implementation and defaults (i.e., indexes all resources without a
published-only filter).
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Add backend/ to import path (scripts/ is under backend/scripts/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.elasticsearch.client import es  # noqa: E402
from app.elasticsearch.index import reindex_resources  # noqa: E402
from db.database import database  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        await database.connect()
        result = await reindex_resources()
        logger.info("Reindex complete: %s", result)
    finally:
        try:
            await database.disconnect()
        except Exception:
            pass
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())

