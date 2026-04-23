"""
Celery tasks for generating static maps from resource bounding boxes.

This module contains background tasks for generating static map images
from dcat_bbox values using py-staticmaps.
"""

import asyncio
import logging
from typing import Any, List

from celery import Task, shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.static_map_service import StaticMapService
from db.config import DATABASE_URL
from db.models import resources

logger = logging.getLogger(__name__)


async def generate_map_for_resource(resource_id: str, geometry: Any) -> bool:
    """
    Generate a static map for a single resource.

    Args:
        resource_id: The resource ID
        geometry: Geometry in various formats (GeoJSON dict, WKT string, ENVELOPE string, etc.)

    Returns:
        bool: True if the map was generated successfully, False otherwise
    """
    try:
        service = StaticMapService()
        source_signature = service.geometry_signature(geometry)

        # Check if map already exists in Redis
        if service.map_exists(resource_id, source_signature=source_signature):
            logger.debug(f"Static map already exists for resource {resource_id}")
            return True

        # Generate the map (stores in Redis)
        map_bytes = service.generate_map(
            resource_id,
            geometry,
            source_signature=source_signature,
        )
        if map_bytes:
            logger.info(f"Successfully generated static map for resource {resource_id}")
            return True
        else:
            logger.warning(f"Failed to generate static map for resource {resource_id}")
            return False

    except Exception as e:
        logger.error(f"Error generating static map for resource {resource_id}: {e}", exc_info=True)
        return False


@shared_task(bind=True, name="generate_static_map")
def generate_static_map(self: Task, resource_id: str) -> dict:
    """
    Celery task to generate a static map for a single resource.

    Args:
        resource_id: The resource ID

    Returns:
        dict: Result with success status
    """
    try:
        # Run the async function
        return asyncio.run(_generate_static_map_async(resource_id))
    except Exception as e:
        logger.error(f"Error in Celery task for resource {resource_id}: {e}", exc_info=True)
        return {"resource_id": resource_id, "success": False, "error": str(e)}


async def _generate_static_map_async(resource_id: str) -> dict:
    """Async helper function for generate_static_map task."""
    # Create a new engine and session for this task
    task_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async_session_factory = sessionmaker(
            task_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            # Fetch the resource to get its geometry (prefer locn_geometry over dcat_bbox)
            query = select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox).where(
                resources.c.id == resource_id
            )
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                logger.warning(f"Resource {resource_id} not found")
                return {"resource_id": resource_id, "success": False, "error": "Resource not found"}

            # Prefer locn_geometry over dcat_bbox
            geometry = row.locn_geometry or row.dcat_bbox
            if not geometry:
                logger.warning(
                    f"Resource {resource_id} has no geometry (locn_geometry or dcat_bbox)"
                )
                return {
                    "resource_id": resource_id,
                    "success": False,
                    "error": "No geometry available",
                }

            # Generate the map
            success = await generate_map_for_resource(resource_id, geometry)
            return {
                "resource_id": resource_id,
                "success": success,
            }

    finally:
        await task_engine.dispose()


@shared_task(bind=True, name="generate_static_maps_batch")
def generate_static_maps_batch(self: Task, resource_ids: List[str]) -> dict:
    """
    Celery task to generate static maps for multiple resources in batch.

    Args:
        resource_ids: List of resource IDs to process

    Returns:
        dict: Summary of processing results
    """
    try:
        return asyncio.run(_generate_static_maps_batch_async(resource_ids))
    except Exception as e:
        logger.error(f"Error in batch static map generation task: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "message": "Failed to process batch",
        }


async def _generate_static_maps_batch_async(resource_ids: List[str]) -> dict:
    """Async helper function for generate_static_maps_batch task."""
    # Create a new engine and session for this task
    task_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async_session_factory = sessionmaker(
            task_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            # Fetch all resources with their geometries (prefer locn_geometry over dcat_bbox)
            query = select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox).where(
                resources.c.id.in_(resource_ids)
            )
            result = await session.execute(query)
            rows = result.fetchall()

            processed = 0
            successful = 0
            failed = 0

            for row in rows:
                resource_id = row.id
                # Prefer locn_geometry over dcat_bbox
                geometry = row.locn_geometry or row.dcat_bbox

                if not geometry:
                    logger.debug(f"Resource {resource_id} has no geometry, skipping")
                    continue

                processed += 1
                success = await generate_map_for_resource(resource_id, geometry)
                if success:
                    successful += 1
                else:
                    failed += 1

            logger.info(
                f"Batch processing complete: {processed} processed, "
                f"{successful} successful, {failed} failed"
            )

            return {
                "status": "completed",
                "total_requested": len(resource_ids),
                "processed": processed,
                "successful": successful,
                "failed": failed,
            }

    finally:
        await task_engine.dispose()


@shared_task(bind=True, name="generate_static_maps_collection")
def generate_static_maps_collection(self: Task, batch_size: int = 100) -> dict:
    """
    Celery task to generate static maps for all resources with dcat_bbox.

    Args:
        batch_size: Number of resources to process per batch (not used in current implementation)

    Returns:
        dict: Summary of submitted jobs
    """
    try:
        return asyncio.run(_generate_static_maps_collection_async())
    except Exception as e:
        logger.error(f"Error in generate_static_maps_collection task: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "message": "Failed to submit static map generation jobs",
        }


async def _generate_static_maps_collection_async() -> dict:
    """Async helper function for generate_static_maps_collection task."""
    # Create a new engine and session for this task
    task_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async_session_factory = sessionmaker(
            task_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            # Get all resources with geometry (locn_geometry or dcat_bbox)
            query = select(resources.c.id).where(
                (resources.c.locn_geometry.isnot(None)) | (resources.c.dcat_bbox.isnot(None))
            )
            result = await session.execute(query)
            resource_list = result.fetchall()
            total = len(resource_list)

            logger.info(f"Found {total} resources with geometry")

            if total == 0:
                return {
                    "status": "completed",
                    "total_resources": 0,
                    "jobs_submitted": 0,
                    "message": "No resources with geometry found",
                }

            # Submit jobs for each resource
            jobs_submitted = 0
            for resource in resource_list:
                try:
                    generate_static_map.delay(resource.id)
                    jobs_submitted += 1
                except Exception as e:
                    logger.error(f"Error submitting job for resource {resource.id}: {e}")
                    continue

            logger.info(f"Submitted {jobs_submitted} static map generation jobs to queue")

            return {
                "status": "completed",
                "total_resources": total,
                "jobs_submitted": jobs_submitted,
                "message": f"Successfully submitted {jobs_submitted} jobs for processing",
            }

    finally:
        await task_engine.dispose()
