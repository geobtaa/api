#!/usr/bin/env python3
"""
Fix character-split arrays in the resources table.

Some array fields like gbl_resourceClass_sm contain {C,o,l,l,e,c,t,i,o,n,s}
instead of {Collections}. This script detects and fixes them.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from db.database import database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main():
    await database.connect()

    try:
        array_fields = [
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "dct_language_sm",
            "dct_creator_sm",
            "dct_publisher_sm",
            "dct_subject_sm",
            "dcat_theme_sm",
            "dcat_keyword_sm",
            "dct_spatial_sm",
        ]

        for field in array_fields:
            logger.info(f"Fixing {field}...")

            # Update query: if array has elements and all are single characters, join them
            # Use quoted identifiers for case-sensitive column names
            query = f"""
                UPDATE resources
                SET "{field}" = ARRAY[array_to_string("{field}", '')]
                WHERE "{field}" IS NOT NULL
                  AND array_length("{field}", 1) > 1
                  AND (
                    SELECT bool_and(length(elem) = 1)
                    FROM unnest("{field}") AS elem
                  ) = true;
            """

            result = await database.execute(query)
            logger.info(f"  Updated {result} rows")

        logger.info("=" * 70)
        logger.info("✓ Character-split array fix complete!")
        logger.info("=" * 70)

    finally:
        try:
            await database.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
