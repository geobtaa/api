#!/usr/bin/env python3
"""
Script to monitor spatial facet indexing progress.

This script shows the current status of spatial facet indexing jobs
and provides real-time progress updates.

Usage:
    python scripts/monitor_spatial_facet_progress.py [options]

Options:
    --watch: Continuously monitor progress (refresh every 30 seconds)
    --task-id: Monitor a specific Celery task ID
"""

import argparse
import logging
import os
import sys
import time

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from celery.result import AsyncResult

from app.services.spatial_facet_indexing_service import SpatialFacetIndexingService
from app.tasks.worker import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def get_indexing_stats():
    """Get current spatial facet indexing statistics."""
    try:
        import asyncio

        service = SpatialFacetIndexingService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(service.get_indexing_stats())
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error getting indexing stats: {e}")
        return {"error": str(e)}


def get_task_status(task_id: str):
    """Get status of a specific Celery task."""
    try:
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
        }
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return {"error": str(e)}


def print_stats(stats):
    """Print indexing statistics in a formatted way."""
    if "error" in stats:
        print(f"❌ Error: {stats['error']}")
        return

    print("=== Spatial Facet Indexing Progress ===")
    print(f"Total resources with dcat_bbox: {stats.get('total_resources_with_bbox', 0):,}")
    print(f"Indexed resources: {stats.get('indexed_resources', 0):,}")
    print(f"Resources with spatial facets: {stats.get('resources_with_facets', 0):,}")
    print(f"Recent updates (1 hour): {stats.get('recent_updates_1h', 0):,}")
    print(f"Indexing progress: {stats.get('indexing_progress', 0):.1f}%")

    remaining = stats.get("total_resources_with_bbox", 0) - stats.get("indexed_resources", 0)
    if remaining > 0:
        print(f"Remaining to index: {remaining:,}")
    else:
        print("🎉 All resources have been indexed!")


def print_task_status(task_status):
    """Print task status in a formatted way."""
    if "error" in task_status:
        print(f"❌ Error: {task_status['error']}")
        return

    print(f"=== Task Status: {task_status['task_id']} ===")
    print(f"Status: {task_status['status']}")
    print(f"Ready: {task_status['ready']}")

    if task_status["ready"]:
        if task_status["successful"]:
            print("✅ Task completed successfully")
            if task_status["result"]:
                result = task_status["result"]
                print(f"Total resources: {result.get('total_resources', 0):,}")
                print(f"Total batches: {result.get('total_batches', 0):,}")
                print(f"Batch size: {result.get('batch_size', 0)}")
                print(f"Task IDs: {len(result.get('task_ids', []))}")
        elif task_status["failed"]:
            print("❌ Task failed")
            if task_status["result"]:
                print(f"Error: {task_status['result']}")
        else:
            print("⚠️ Task completed with unknown status")
    else:
        print("⏳ Task is still running...")


def main():
    """Main function to handle command line arguments and monitor progress."""
    parser = argparse.ArgumentParser(
        description="Monitor spatial facet indexing progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current progress
  python scripts/monitor_spatial_facet_progress.py
  
  # Continuously monitor progress
  python scripts/monitor_spatial_facet_progress.py --watch
  
  # Monitor a specific task
  python scripts/monitor_spatial_facet_progress.py --task-id 006b9aae-8891-49fa-ad72-0bdfafab4048
        """,
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously monitor progress (refresh every 30 seconds)",
    )

    parser.add_argument("--task-id", type=str, help="Monitor a specific Celery task ID")

    args = parser.parse_args()

    try:
        if args.task_id:
            # Monitor specific task
            print(f"Monitoring task: {args.task_id}")
            if args.watch:
                while True:
                    print("\n" + "=" * 50)
                    task_status = get_task_status(args.task_id)
                    print_task_status(task_status)
                    if task_status.get("ready", False):
                        print("Task completed. Exiting...")
                        break
                    print("Refreshing in 30 seconds... (Ctrl+C to stop)")
                    time.sleep(30)
            else:
                task_status = get_task_status(args.task_id)
                print_task_status(task_status)
        else:
            # Monitor overall progress
            if args.watch:
                while True:
                    print("\n" + "=" * 50)
                    stats = get_indexing_stats()
                    print_stats(stats)
                    if stats.get("indexing_progress", 0) >= 100:
                        print("🎉 Indexing completed! Exiting...")
                        break
                    print("Refreshing in 30 seconds... (Ctrl+C to stop)")
                    time.sleep(30)
            else:
                stats = get_indexing_stats()
                print_stats(stats)

        return 0

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error monitoring progress: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
