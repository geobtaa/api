#!/usr/bin/env python3
"""
Diagnostic script to find resources that failed to index into Elasticsearch.
"""
import asyncio
import logging
import os
import sys
from collections import defaultdict

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from app.elasticsearch.client import es, init_elasticsearch
from app.elasticsearch.index import process_resource
from db.database import database
from db.models import resources

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def get_db_resource_ids():
    """Get all resource IDs from the database."""
    query = "SELECT id FROM resources ORDER BY id"
    rows = await database.fetch_all(query)
    return {row["id"] for row in rows}


async def get_es_resource_ids():
    """Get all resource IDs from Elasticsearch."""
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_ogm_api")
    
    es_ids = set()
    
    # Use scroll API to get all document IDs
    response = await es.search(
        index=index_name,
        query={"match_all": {}},
        _source=False,
        size=10000,
        scroll="5m"
    )
    
    scroll_id = response["_scroll_id"]
    hits = response["hits"]["hits"]
    
    for hit in hits:
        es_ids.add(hit["_id"])
    
    # Continue scrolling
    while hits:
        response = await es.scroll(scroll_id=scroll_id, scroll="5m")
        scroll_id = response["_scroll_id"]
        hits = response["hits"]["hits"]
        
        for hit in hits:
            es_ids.add(hit["_id"])
    
    # Clear the scroll
    try:
        await es.clear_scroll(scroll_id=scroll_id)
    except:
        pass
    
    return es_ids


async def test_index_single_resource(resource_id):
    """Try to index a single resource and capture the error."""
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_ogm_api")
    
    try:
        # Fetch the resource from DB
        query = resources.select().where(resources.c.id == resource_id)
        resource = await database.fetch_one(query)
        
        if not resource:
            return {"error": "Resource not found in database"}
        
        # Process the resource
        processed = await process_resource(dict(resource))
        
        # Try to index it
        response = await es.index(
            index=index_name,
            id=resource_id,
            document=processed,
            refresh=False
        )
        
        return {"status": "success", "result": response}
        
    except Exception as e:
        error_info = {
            "error": str(e),
            "type": type(e).__name__
        }
        
        # Try to get more details from Elasticsearch errors
        if hasattr(e, "info"):
            error_info["info"] = e.info
        if hasattr(e, "status_code"):
            error_info["status_code"] = e.status_code
        
        return error_info


async def analyze_failed_resources(failed_ids, sample_size=10):
    """Analyze a sample of failed resources to find common patterns."""
    logger.info(f"Analyzing {min(sample_size, len(failed_ids))} failed resources...")
    
    error_types = defaultdict(list)
    
    # Test a sample of failed resources
    for resource_id in list(failed_ids)[:sample_size]:
        logger.info(f"Testing resource: {resource_id}")
        result = await test_index_single_resource(resource_id)
        
        if "error" in result:
            error_type = result.get("type", "Unknown")
            error_msg = result.get("error", "Unknown error")
            error_types[error_type].append({
                "id": resource_id,
                "error": error_msg,
                "info": result.get("info")
            })
            logger.error(f"  ❌ {resource_id}: {error_type} - {error_msg}")
        else:
            logger.info(f"  ✅ {resource_id}: Successfully indexed in test")
    
    return error_types


async def main():
    """Main diagnostic function."""
    try:
        # Connect to database
        await database.connect()
        logger.info("Connected to database")
        
        # Initialize Elasticsearch
        await init_elasticsearch()
        logger.info("Connected to Elasticsearch")
        
        # Get resource IDs from both systems
        logger.info("Fetching resource IDs from database...")
        db_ids = await get_db_resource_ids()
        logger.info(f"Found {len(db_ids)} resources in database")
        
        logger.info("Fetching resource IDs from Elasticsearch...")
        es_ids = await get_es_resource_ids()
        logger.info(f"Found {len(es_ids)} resources in Elasticsearch")
        
        # Find missing resources
        missing_ids = db_ids - es_ids
        logger.info(f"\n{'='*60}")
        logger.info(f"MISSING RESOURCES: {len(missing_ids)}")
        logger.info(f"Database: {len(db_ids)}")
        logger.info(f"Elasticsearch: {len(es_ids)}")
        logger.info(f"Missing: {len(missing_ids)} ({len(missing_ids)/len(db_ids)*100:.1f}%)")
        logger.info(f"{'='*60}\n")
        
        if missing_ids:
            # Show first 20 missing IDs
            sample_ids = list(missing_ids)[:20]
            logger.info("First 20 missing resource IDs:")
            for resource_id in sample_ids:
                logger.info(f"  - {resource_id}")
            
            # Analyze failures
            logger.info("\nAnalyzing failed resources...")
            error_types = await analyze_failed_resources(missing_ids, sample_size=20)
            
            # Summary of error types
            if error_types:
                logger.info(f"\n{'='*60}")
                logger.info("ERROR SUMMARY")
                logger.info(f"{'='*60}")
                for error_type, errors in error_types.items():
                    logger.info(f"\n{error_type}: {len(errors)} occurrences")
                    # Show first error of this type
                    if errors:
                        first_error = errors[0]
                        logger.info(f"  Example ID: {first_error['id']}")
                        logger.info(f"  Error: {first_error['error']}")
                        if first_error.get('info'):
                            logger.info(f"  Details: {first_error['info']}")
        else:
            logger.info("✅ All database resources are indexed in Elasticsearch!")
        
    except Exception as e:
        logger.error(f"Diagnostic failed: {str(e)}", exc_info=True)
    finally:
        # Cleanup
        await database.disconnect()
        await es.close()


if __name__ == "__main__":
    asyncio.run(main())

