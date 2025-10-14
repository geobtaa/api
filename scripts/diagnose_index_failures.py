#!/usr/bin/env python3
"""
Diagnostic script to capture ACTUAL Elasticsearch rejection reasons.

This script:
1. Gets current ES document IDs
2. Finds resources missing from ES
3. Attempts to index a sample of missing ones
4. Captures and reports the REAL ES errors
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

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
    es = AsyncElasticsearch(os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"))

    await database.connect()

    try:
        # Get all DB resource IDs
        logger.info("Fetching all resource IDs from database...")
        db_rows = await database.fetch_all("SELECT id FROM resources ORDER BY id")
        db_ids = {row[0] for row in db_rows}
        logger.info(f"Database: {len(db_ids):,} resources")

        # Get all ES document IDs
        logger.info("Fetching all document IDs from Elasticsearch...")
        es_ids = set()
        response = await es.search(
            index=index_name,
            body={"query": {"match_all": {}}, "_source": False, "size": 1000},
            scroll="2m",
        )
        scroll_id = response.get("_scroll_id")
        hits = response["hits"]["hits"]
        es_ids.update(h["_id"] for h in hits)

        while hits:
            response = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = response.get("_scroll_id")
            hits = response["hits"]["hits"]
            es_ids.update(h["_id"] for h in hits)

        try:
            if scroll_id:
                await es.clear_scroll(scroll_id=scroll_id)
        except Exception:
            pass

        logger.info(f"Elasticsearch: {len(es_ids):,} documents")

        # Find missing
        missing_ids = sorted(db_ids - es_ids)
        logger.info(f"Missing from ES: {len(missing_ids):,} resources")

        if not missing_ids:
            logger.info("✓ All resources are indexed!")
            return

        # Test index a sample of missing IDs to get REAL errors
        sample_size = min(100, len(missing_ids))
        sample_ids = missing_ids[:sample_size]

        logger.info(f"\nAttempting to index {sample_size} missing resources to capture errors...")
        logger.info("=" * 80)

        error_categories = {}

        for i, resource_id in enumerate(sample_ids, 1):
            # Fetch the resource
            query = resources.select().where(resources.c.id == resource_id)
            row = await database.fetch_one(query)

            if not row:
                logger.warning(f"[{i}/{sample_size}] {resource_id}: NOT FOUND IN DB")
                continue

            resource_dict = dict(row)

            # Attempt to index with minimal processing (raw data)
            try:
                response = await es.index(
                    index=index_name,
                    id=resource_id,
                    document=resource_dict,
                    refresh=False,
                )
                logger.info(
                    f"[{i}/{sample_size}] {resource_id}: ✓ INDEXED ({response.get('result')})"
                )

            except Exception as e:
                error_str = str(e)

                # Categorize the error
                if "mapper_parsing_exception" in error_str:
                    category = "mapper_parsing_exception"
                elif "illegal_argument_exception" in error_str:
                    category = "illegal_argument_exception"
                elif "failed to parse field" in error_str.lower():
                    category = "parse_field_error"
                elif "geo" in error_str.lower():
                    category = "geo_error"
                elif "date" in error_str.lower():
                    category = "date_error"
                else:
                    category = "other"

                error_categories[category] = error_categories.get(category, 0) + 1

                # Log the full error for first few of each category
                if error_categories[category] <= 3:
                    logger.error(f"\n[{i}/{sample_size}] {resource_id}: ✗ FAILED")
                    logger.error(f"Category: {category}")
                    logger.error(f"Error: {error_str[:500]}")
                    logger.error(f"Title: {resource_dict.get('dct_title_s', 'N/A')[:100]}")
                    logger.error("-" * 80)
                else:
                    logger.error(f"[{i}/{sample_size}] {resource_id}: ✗ {category}")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("ERROR SUMMARY:")
        logger.info("=" * 80)
        for category, count in sorted(error_categories.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"{category}: {count} failures")

        logger.info("\n" + "=" * 80)
        logger.info(f"Total missing from ES: {len(missing_ids):,}")
        logger.info(f"Sample tested: {sample_size}")
        logger.info(f"Would fail: {sum(error_categories.values())}")
        logger.info(f"Would succeed: {sample_size - sum(error_categories.values())}")
        logger.info("=" * 80)

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
