#!/usr/bin/env python3
"""
Simple bulk indexing script using raw database values.
With ignore_malformed=true in mappings, this should index all resources.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from db.database import database
from db.models import resources

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main():
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_data_api")
    chunk_size = 500

    logger.info("=" * 70)
    logger.info(f"Bulk indexing all resources to {index_name}")
    logger.info("=" * 70)

    await database.connect()
    es = AsyncElasticsearch(os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"))

    try:
        # Delete existing index
        if await es.indices.exists(index=index_name):
            logger.info(f"Deleting existing index {index_name}")
            await es.indices.delete(index=index_name)

        # Create index with updated mapping
        from app.elasticsearch.client import init_elasticsearch

        await init_elasticsearch()

        # Fetch all resources
        logger.info("Fetching all resources from database...")
        all_rows = await database.fetch_all(resources.select())
        total = len(all_rows)
        logger.info(f"Fetched {total:,} resources")

        # Prepare bulk actions with array normalization
        def actions():
            for row in all_rows:
                doc = dict(row)

                # Fix array fields: normalize strings to arrays AND fix character-split arrays
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
                    if field in doc:
                        val = doc[field]
                        # If it's a string, wrap in array
                        if isinstance(val, str):
                            doc[field] = [val]
                        # If it's an array of single characters, join them
                        elif (
                            isinstance(val, list)
                            and val
                            and all(isinstance(v, str) and len(v) == 1 for v in val)
                        ):
                            doc[field] = ["".join(val)]

                yield {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": doc["id"],
                    "_source": doc,
                }

        # Bulk index
        logger.info(f"Bulk indexing with chunk_size={chunk_size}...")
        success, errors = await async_bulk(
            es,
            actions(),
            chunk_size=chunk_size,
            raise_on_error=False,
            refresh=True,
        )

        logger.info("=" * 70)
        logger.info("Bulk indexing complete!")
        logger.info(f"Successful: {success:,}")
        logger.info(f"Errors: {len(errors):,}")

        if errors:
            logger.warning("\nFirst 10 errors:")
            for i, err in enumerate(errors[:10], 1):
                logger.warning(f"{i}. {err}")

        # Verify count
        es_count = (await es.count(index=index_name)).get("count", 0)
        logger.info(f"\nElasticsearch count: {es_count:,}")
        logger.info(f"Database count: {total:,}")
        logger.info(f"Missing: {total - es_count:,}")
        logger.info("=" * 70)

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
