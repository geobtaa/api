#!/usr/bin/env python3
"""
Script to index spatial facets for all resources with dcat_bbox.

This script processes all resources in the database that have a dcat_bbox value,
computes their spatial facets (country, region, county), and stores the results
in the resource_spatial_facets table for fast faceting in search results.

Usage:
    python scripts/index_spatial_facets.py [options]

Options:
    --dry-run: Show what would be processed without making changes
    --batch-size: Number of resources to process in each batch (default: 100)
    --stats: Show current indexing statistics
    --reindex-resource: Reindex a specific resource by ID
"""

import argparse
import asyncio
import logging
import os
import sys

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from app.services.spatial_facet_indexing_service import SpatialFacetIndexingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def show_stats():
    """Show current indexing statistics."""
    logger.info("Getting spatial facet indexing statistics...")

    service = SpatialFacetIndexingService()
    stats = await service.get_indexing_stats()

    if "error" in stats:
        logger.error(f"Error getting stats: {stats['error']}")
        return 1

    logger.info("=== Spatial Facet Indexing Statistics ===")
    logger.info(f"Total resources with dcat_bbox: {stats['total_resources_with_bbox']:,}")
    logger.info(f"Indexed resources: {stats['indexed_resources']:,}")
    logger.info(f"Resources with spatial facets: {stats['resources_with_facets']:,}")
    logger.info(f"Recent updates (1 hour): {stats['recent_updates_1h']:,}")
    logger.info(f"Indexing progress: {stats['indexing_progress']:.1f}%")

    if stats["indexed_resources"] < stats["total_resources_with_bbox"]:
        remaining = stats["total_resources_with_bbox"] - stats["indexed_resources"]
        logger.info(f"Remaining to index: {remaining:,}")

    return 0


async def reindex_resource(resource_id: str):
    """Reindex spatial facets for a specific resource."""
    logger.info(f"Reindexing spatial facets for resource: {resource_id}")

    service = SpatialFacetIndexingService()
    result = await service.reindex_resource(resource_id)

    if "error" in result:
        logger.error(f"Error reindexing resource: {result['error']}")
        return 1

    logger.info("✅ Successfully reindexed resource")
    logger.info(f"Resource ID: {result['resource_id']}")
    logger.info(f"Spatial facets: {result['spatial_facets']}")

    return 0


async def index_all_resources(dry_run: bool = False, batch_size: int = 100):
    """Index spatial facets for all resources."""
    logger.info("Starting spatial facet indexing...")

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made to the database")

    service = SpatialFacetIndexingService(batch_size=batch_size)

    # Show initial stats
    initial_stats = await service.get_indexing_stats()
    if "error" not in initial_stats:
        logger.info(
            f"Initial state: {initial_stats['indexed_resources']:,}/{initial_stats['total_resources_with_bbox']:,} resources indexed"
        )

    # Run the indexing
    start_time = asyncio.get_event_loop().time()
    stats = await service.index_all_resources(dry_run=dry_run)
    end_time = asyncio.get_event_loop().time()

    # Show results
    logger.info("=== Spatial Facet Indexing Results ===")
    logger.info(f"Total resources found: {stats['total_resources']:,}")
    logger.info(f"Resources processed: {stats['processed']:,}")
    logger.info(f"Successfully indexed: {stats['successful']:,}")
    logger.info(f"Failed: {stats['failed']:,}")
    logger.info(f"Skipped (already indexed): {stats['skipped']:,}")
    logger.info(f"Total processing time: {stats['processing_time']:.2f} seconds")

    if stats["errors"]:
        logger.warning(f"Errors encountered: {len(stats['errors'])}")
        for error in stats["errors"][:10]:  # Show first 10 errors
            logger.warning(f"  - {error}")
        if len(stats["errors"]) > 10:
            logger.warning(f"  ... and {len(stats['errors']) - 10} more errors")

    # Show final stats
    if not dry_run:
        final_stats = await service.get_indexing_stats()
        if "error" not in final_stats:
            logger.info(
                f"Final state: {final_stats['indexed_resources']:,}/{final_stats['total_resources_with_bbox']:,} resources indexed"
            )
            logger.info(f"Indexing progress: {final_stats['indexing_progress']:.1f}%")

    if stats["failed"] > 0:
        logger.warning(f"⚠️  {stats['failed']} resources failed to process")
        return 1
    elif stats["successful"] > 0:
        logger.info("✅ Spatial facet indexing completed successfully!")
        return 0
    else:
        logger.info("ℹ️  No resources needed indexing")
        return 0


def main():
    """Main function to handle command line arguments and run the appropriate action."""
    parser = argparse.ArgumentParser(
        description="Index spatial facets for resources with dcat_bbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current indexing statistics
  python scripts/index_spatial_facets.py --stats
  
  # Dry run to see what would be processed
  python scripts/index_spatial_facets.py --dry-run
  
  # Index all resources with default batch size
  python scripts/index_spatial_facets.py
  
  # Index with custom batch size
  python scripts/index_spatial_facets.py --batch-size 50
  
  # Reindex a specific resource
  python scripts/index_spatial_facets.py --reindex-resource "p16022coll230:1750"
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed without making changes"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of resources to process in each batch (default: 100)",
    )

    parser.add_argument("--stats", action="store_true", help="Show current indexing statistics")

    parser.add_argument("--reindex-resource", type=str, help="Reindex a specific resource by ID")

    args = parser.parse_args()

    try:
        if args.stats:
            return asyncio.run(show_stats())
        elif args.reindex_resource:
            return asyncio.run(reindex_resource(args.reindex_resource))
        else:
            return asyncio.run(index_all_resources(args.dry_run, args.batch_size))

    except KeyboardInterrupt:
        logger.info("Indexing interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
