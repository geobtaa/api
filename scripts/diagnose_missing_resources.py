#!/usr/bin/env python3
"""
Diagnose why resources are missing from Elasticsearch index.
"""

import asyncio
import logging
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from app.elasticsearch.client import es
from db.database import database
from db.models import resources

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
    """Check discrepancy between database and index."""
    try:
        await database.connect()
        
        # Get count from database
        db_count_query = "SELECT COUNT(*) FROM resources"
        db_result = await database.fetch_one(db_count_query)
        db_count = db_result[0]
        
        # Get count from Elasticsearch
        index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_data_api")
        es_count_result = await es.count(index=index_name)
        es_count = es_count_result.get("count", 0)
        
        logger.info("=" * 70)
        logger.info(f"Database resources: {db_count:,}")
        logger.info(f"Elasticsearch docs: {es_count:,}")
        logger.info(f"Missing from index: {db_count - es_count:,}")
        logger.info("=" * 70)
        
        # Get all resource IDs from database
        logger.info("Fetching all resource IDs from database...")
        db_ids_query = "SELECT id FROM resources ORDER BY id"
        db_rows = await database.fetch_all(db_ids_query)
        db_ids = {row['id'] for row in db_rows}
        logger.info(f"Found {len(db_ids):,} unique IDs in database")
        
        # Get all document IDs from Elasticsearch
        logger.info("Fetching all document IDs from Elasticsearch...")
        es_ids = set()
        
        # Use scroll API to get all IDs
        response = await es.search(
            index=index_name,
            body={
                "query": {"match_all": {}},
                "_source": False,
                "size": 1000
            },
            scroll="2m"
        )
        
        scroll_id = response.get('_scroll_id')
        hits = response['hits']['hits']
        
        for hit in hits:
            es_ids.add(hit['_id'])
        
        while len(hits) > 0:
            response = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = response.get('_scroll_id')
            hits = response['hits']['hits']
            
            for hit in hits:
                es_ids.add(hit['_id'])
            
            if len(hits) > 0:
                logger.info(f"Fetched {len(es_ids):,} IDs so far...")
        
        # Clear scroll
        await es.clear_scroll(scroll_id=scroll_id)
        
        logger.info(f"Found {len(es_ids):,} unique IDs in Elasticsearch")
        
        # Find missing IDs
        missing_ids = db_ids - es_ids
        
        if missing_ids:
            logger.info("=" * 70)
            logger.info(f"Found {len(missing_ids):,} resources missing from index")
            logger.info("=" * 70)
            
            # Write missing IDs to a file for downstream triage
            out_path = os.getenv("MISSING_IDS_FILE", "logs/missing_resource_ids.txt")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as fh:
                for rid in sorted(missing_ids):
                    fh.write(f"{rid}\n")
            logger.info(f"Wrote missing IDs to {out_path}")

            # Sample some missing IDs to investigate
            sample_size = min(10, len(missing_ids))
            sample_ids = list(missing_ids)[:sample_size]
            
            logger.info(f"Sample of missing resource IDs: {sample_ids}")
            
            # Check if these have any special characteristics
            for missing_id in sample_ids:
                query = resources.select().where(resources.c.id == missing_id)
                resource = await database.fetch_one(query)
                if resource:
                    resource_dict = dict(resource)
                    logger.info(f"\nResource ID {missing_id}:")
                    logger.info(f"  Title: {resource_dict.get('dct_title_s', 'N/A')}")
                    logger.info(f"  Provider: {resource_dict.get('schema_provider_s', 'N/A')}")
                    logger.info(f"  Has geometry: {bool(resource_dict.get('locn_geometry'))}")
        else:
            logger.info("No missing resources found - all are indexed!")
            
    except Exception as e:
        logger.error(f"Diagnostic failed: {str(e)}", exc_info=True)
        sys.exit(1)
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

