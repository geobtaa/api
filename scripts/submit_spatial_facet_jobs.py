#!/usr/bin/env python3
"""
Script to submit spatial facet indexing jobs to Celery.

This script submits all resources with dcat_bbox to the Celery queue for
background processing of spatial facets.

Usage:
    python scripts/submit_spatial_facet_jobs.py [options]

Options:
    --batch-size: Number of resources per batch (default: 100)
    --max-workers: Maximum number of concurrent workers (default: 4)
    --dry-run: Show what would be submitted without actually submitting
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.tasks.spatial_facets import index_all_spatial_facets

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
        description="Submit spatial facet indexing jobs to Celery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit jobs with default settings
  python scripts/submit_spatial_facet_jobs.py
  
  # Submit with custom batch size
  python scripts/submit_spatial_facet_jobs.py --batch-size 50
  
  # Dry run to see what would be submitted
  python scripts/submit_spatial_facet_jobs.py --dry-run
        """
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of resources per batch (default: 100)"
    )
    
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of concurrent workers (default: 4)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be submitted without actually submitting"
    )
    
    args = parser.parse_args()
    
    try:
        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No jobs will be submitted")
            logger.info(f"Would submit jobs with batch_size={args.batch_size}, max_workers={args.max_workers}")
            return 0
        
        logger.info("Submitting spatial facet indexing jobs to Celery...")
        logger.info(f"Batch size: {args.batch_size}")
        logger.info(f"Max workers: {args.max_workers}")
        
        # Submit the job
        result = index_all_spatial_facets.delay(args.batch_size, args.max_workers)
        
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
