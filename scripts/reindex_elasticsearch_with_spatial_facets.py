#!/usr/bin/env python3
"""
Script to reindex Elasticsearch with spatial facet fields.

This script reindexes all resources in Elasticsearch to include the new
spatial facet fields (geo_country, geo_region, geo_county) that are
computed from the resource_spatial_facets table.

Usage:
    python scripts/reindex_elasticsearch_with_spatial_facets.py [options]

Options:
    --dry-run: Show what would be reindexed without actually doing it
    --batch-size: Number of resources to process in each batch (default: 1000)
    --force: Force reindexing even if spatial facets are not ready
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def check_spatial_facet_readiness():
    """Check if spatial facets are ready for reindexing."""
    try:
        # Import here to avoid circular imports
        from app.services.spatial_facet_indexing_service import SpatialFacetIndexingService
        
        service = SpatialFacetIndexingService()
        stats = await service.get_indexing_stats()
        
        if "error" in stats:
            logger.error(f"Error getting spatial facet stats: {stats['error']}")
            return False, stats
        
        total_resources = stats.get('total_resources_with_bbox', 0)
        indexed_resources = stats.get('indexed_resources', 0)
        
        if total_resources == 0:
            logger.warning("No resources with dcat_bbox found")
            return False, stats
        
        progress = stats.get('indexing_progress', 0)
        
        logger.info(f"Spatial facet indexing progress: {progress:.1f}% ({indexed_resources:,}/{total_resources:,})")
        
        # Consider ready if at least 50% are indexed or if we have a reasonable number
        if progress >= 50 or indexed_resources >= 1000:
            logger.info("✅ Spatial facets are ready for Elasticsearch reindexing")
            return True, stats
        else:
            logger.warning("⚠️ Spatial facets are not ready yet. Consider waiting for more indexing to complete.")
            return False, stats
            
    except Exception as e:
        logger.error(f"Error checking spatial facet readiness: {e}")
        return False, {"error": str(e)}


async def main():
    """Main function to handle command line arguments and reindex Elasticsearch."""
    parser = argparse.ArgumentParser(
        description="Reindex Elasticsearch with spatial facet fields",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check spatial facet readiness
  python scripts/reindex_elasticsearch_with_spatial_facets.py --dry-run
  
  # Force reindexing even if spatial facets are not ready
  python scripts/reindex_elasticsearch_with_spatial_facets.py --force
  
  # Reindex with custom batch size
  python scripts/reindex_elasticsearch_with_spatial_facets.py --batch-size 500
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be reindexed without actually doing it"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of resources to process in each batch (default: 1000)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reindexing even if spatial facets are not ready"
    )
    
    args = parser.parse_args()
    
    try:
        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No reindexing will be performed")
        
        # Check spatial facet readiness
        is_ready, stats = await check_spatial_facet_readiness()
        
        if not is_ready and not args.force:
            logger.error("❌ Spatial facets are not ready for reindexing")
            logger.error("Use --force to override this check, or wait for more spatial facet indexing to complete")
            return 1
        
        if not args.force and not is_ready:
            logger.warning("⚠️ Proceeding with reindexing despite spatial facets not being fully ready")
        
        if args.dry_run:
            logger.info("✅ Dry run completed - spatial facets are ready for reindexing")
            logger.info(f"Would reindex with batch size: {args.batch_size}")
            return 0
        
        logger.info("Starting Elasticsearch reindexing with spatial facet fields...")
        logger.info(f"Batch size: {args.batch_size}")
        
        # Initialize database connection
        from db.database import database
        await database.connect()
        
        try:
            # Perform the reindexing
            from app.elasticsearch.index import reindex_resources
            result = await reindex_resources()
        finally:
            # Clean up database connection
            await database.disconnect()
        
        logger.info("✅ Elasticsearch reindexing completed successfully!")
        logger.info(f"Result: {result}")
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("Reindexing interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error during reindexing: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))