#!/usr/bin/env python3
"""
Reindex all resources from PostgreSQL to Elasticsearch with the fixed bulk indexing logic.
"""

import asyncio
import logging
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from app.elasticsearch.index import reindex_resources
from db.database import database

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main():
    """Main reindex function."""
    try:
        logger.info("=" * 70)
        logger.info("Starting full reindex of all resources")
        logger.info("=" * 70)

        # Connect to database
        await database.connect()
        logger.info("Connected to database")

        # Run the reindex
        result = await reindex_resources()

        logger.info("=" * 70)
        logger.info("Reindex complete!")
        logger.info(f"Result: {result}")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Reindex failed: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        try:
            await database.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
