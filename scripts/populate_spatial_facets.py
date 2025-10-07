#!/usr/bin/env python3
"""
Populate Spatial Facets

This script submits all resources with dcat_bbox to the Celery queue for
background processing of spatial facets (country, region, county).

Usage:
    python scripts/populate_spatial_facets.py [options]

Options:
    --batch-size: Number of resources per batch (default: 100)
    --max-workers: Maximum number of concurrent workers (default: 4)
    --dry-run: Show what would be submitted without actually submitting
"""

import argparse
import logging
import os
import sys

from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery to connect to Docker Redis
celery_app = Celery(
    "tasks",
    broker=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/0",
    backend=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/0",
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main():
    """Main function to handle command line arguments and submit jobs."""
    parser = argparse.ArgumentParser(
        description="Populate spatial facets for resources with bounding boxes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit jobs with default settings
  python scripts/populate_spatial_facets.py
  
  # Submit with custom batch size
  python scripts/populate_spatial_facets.py --batch-size 50
  
  # Dry run to see what would be submitted
  python scripts/populate_spatial_facets.py --dry-run
        """,
    )

    parser.add_argument(
        "--batch-size", type=int, default=100, help="Number of resources per batch (default: 100)"
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of concurrent workers (default: 4)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be submitted without actually submitting",
    )

    args = parser.parse_args()

    try:
        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No jobs will be submitted")
            logger.info(
                f"Would submit jobs with batch_size={args.batch_size}, "
                f"max_workers={args.max_workers}"
            )
            return 0

        logger.info("Submitting spatial facet indexing jobs to Celery...")
        logger.info(f"Batch size: {args.batch_size}")
        logger.info(f"Max workers: {args.max_workers}")

        # Submit the job using send_task
        result = celery_app.send_task(
            "index_all_spatial_facets", args=[args.batch_size, args.max_workers]
        )

        logger.info("✅ Successfully submitted spatial facet indexing job!")
        logger.info(f"Task ID: {result.id}")
        logger.info("You can monitor progress using Flower or Celery monitoring tools")

        return 0

    except KeyboardInterrupt:
        logger.info("Job submission interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error submitting jobs: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
