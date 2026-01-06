import asyncio
import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.spatial_facet_service import SpatialFacetService
from app.tasks.worker import celery_app
from db.config import DATABASE_URL

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="index_spatial_facets_batch")
def index_spatial_facets_batch(
    self, resource_ids: List[str], batch_id: str = None
) -> Dict[str, Any]:
    """
    Index spatial facets for a batch of resources.

    Args:
        resource_ids: List of resource IDs to process
        batch_id: Optional batch identifier for tracking

    Returns:
        Dictionary with processing results
    """
    logger.info(
        f"Starting spatial facet indexing batch {batch_id} with {len(resource_ids)} resources"
    )

    try:
        # Run the async indexing in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_index_batch_async(resource_ids, batch_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error in spatial facet indexing batch {batch_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "batch_id": batch_id,
            "error": str(e),
            "processed": 0,
            "successful": 0,
            "failed": len(resource_ids),
        }


async def _index_batch_async(resource_ids: List[str], batch_id: str = None) -> Dict[str, Any]:
    """
    Async implementation of batch spatial facet indexing.

    Args:
        resource_ids: List of resource IDs to process
        batch_id: Optional batch identifier for tracking

    Returns:
        Dictionary with processing results
    """
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

    stats = {
        "status": "success",
        "batch_id": batch_id,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    # Create session factory once for the batch (reuse engine, create new sessions)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        for resource_id in resource_ids:
            # Create a new session for each resource to avoid transaction errors
            async with async_session_factory() as session:
                try:
                    stats["processed"] += 1

                    # Get resource data
                    resource_query = text("""
                        SELECT id, dcat_bbox
                        FROM resources 
                        WHERE id = :resource_id
                    """)
                    result = await session.execute(resource_query, {"resource_id": resource_id})
                    resource = result.fetchone()

                    if not resource:
                        logger.warning(f"Resource {resource_id} not found")
                        stats["failed"] += 1
                        stats["errors"].append(f"Resource {resource_id} not found")
                        continue

                    if not resource.dcat_bbox:
                        logger.debug(f"Resource {resource_id} has no dcat_bbox")
                        stats["skipped"] += 1
                        continue

                    # Check if spatial facets already exist
                    existing_query = text(
                        "SELECT resource_id FROM resource_spatial_facets "
                        "WHERE resource_id = :resource_id"
                    )
                    existing_result = await session.execute(
                        existing_query, {"resource_id": resource_id}
                    )
                    existing = existing_result.fetchone()

                    if existing:
                        logger.debug(f"Skipping {resource_id} - spatial facets already exist")
                        stats["skipped"] += 1
                        continue

                    # Compute spatial facets
                    resource_dict = {"id": resource_id, "dcat_bbox": resource.dcat_bbox}
                    service = SpatialFacetService(resource_dict)
                    spatial_facets = await service.get_spatial_facets(session)

                    if not spatial_facets:
                        logger.debug(f"No spatial facets computed for {resource_id}")
                        stats["skipped"] += 1
                        continue

                    # Store spatial facets
                    import json

                    upsert_query = text("""
                        INSERT INTO resource_spatial_facets 
                        (resource_id, geo_global, geo_country, geo_region, geo_county)
                        VALUES (:resource_id, :geo_global, :geo_country, :geo_region, :geo_county)
                        ON CONFLICT (resource_id) 
                        DO UPDATE SET 
                            geo_global = EXCLUDED.geo_global,
                            geo_country = EXCLUDED.geo_country,
                            geo_region = EXCLUDED.geo_region,
                            geo_county = EXCLUDED.geo_county,
                            updated_at = NOW()
                    """)

                    insert_data = {
                        "resource_id": resource_id,
                        "geo_global": spatial_facets.get("geo.global", False),
                        "geo_country": json.dumps(spatial_facets.get("geo.country"))
                        if spatial_facets.get("geo.country")
                        else None,
                        "geo_region": json.dumps(spatial_facets.get("geo.region"))
                        if spatial_facets.get("geo.region")
                        else None,
                        "geo_county": json.dumps(spatial_facets.get("geo.county"))
                        if spatial_facets.get("geo.county")
                        else None,
                    }

                    await session.execute(upsert_query, insert_data)
                    await session.commit()
                    stats["successful"] += 1

                    logger.debug(f"Successfully indexed spatial facets for {resource_id}")

                except Exception as e:
                    await session.rollback()
                    stats["failed"] += 1
                    error_msg = f"Error processing {resource_id}: {str(e)}"
                    stats["errors"].append(error_msg)
                    logger.error(error_msg, exc_info=True)

    except Exception as e:
        logger.error(f"Error in batch processing: {e}", exc_info=True)
        stats["status"] = "error"
        stats["errors"].append(f"Batch processing error: {str(e)}")

    finally:
        await engine.dispose()

    logger.info(
        f"Completed spatial facet indexing batch {batch_id}: "
        f"{stats['successful']} successful, {stats['failed']} failed, "
        f"{stats['skipped']} skipped"
    )
    return stats


@celery_app.task(bind=True, name="index_all_spatial_facets")
def index_all_spatial_facets(self, batch_size: int = 100, max_workers: int = 4) -> Dict[str, Any]:
    """
    Index spatial facets for all resources with dcat_bbox using Celery workers.

    Args:
        batch_size: Number of resources per batch
        max_workers: Maximum number of concurrent workers

    Returns:
        Dictionary with job information and task IDs
    """
    logger.info(
        f"Starting spatial facet indexing for all resources "
        f"(batch_size={batch_size}, max_workers={max_workers})"
    )

    try:
        # Run the async setup in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_setup_batch_jobs_async(batch_size, max_workers))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error setting up spatial facet indexing jobs: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "total_resources": 0,
            "total_batches": 0,
            "task_ids": [],
        }


async def _setup_batch_jobs_async(batch_size: int, max_workers: int) -> Dict[str, Any]:
    """
    Setup batch jobs for spatial facet indexing.

    Args:
        batch_size: Number of resources per batch
        max_workers: Maximum number of concurrent workers

    Returns:
        Dictionary with job information
    """
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # Get all resources with dcat_bbox
            query = text("""
                SELECT id
                FROM resources 
                WHERE dcat_bbox IS NOT NULL 
                AND dcat_bbox != ''
                ORDER BY id
            """)
            result = await session.execute(query)
            all_resources = [row[0] for row in result.fetchall()]

            total_resources = len(all_resources)
            logger.info(f"Found {total_resources} resources with dcat_bbox to process")

            if total_resources == 0:
                return {
                    "status": "success",
                    "message": "No resources to process",
                    "total_resources": 0,
                    "total_batches": 0,
                    "task_ids": [],
                }

            # Create batches
            batches = []
            for i in range(0, total_resources, batch_size):
                batch_resources = all_resources[i : i + batch_size]
                batch_id = f"spatial_facets_batch_{i // batch_size + 1}"
                batches.append((batch_id, batch_resources))

            total_batches = len(batches)
            logger.info(f"Created {total_batches} batches of {batch_size} resources each")

            # Submit batches to Celery
            task_ids = []
            for batch_id, batch_resources in batches:
                task = index_spatial_facets_batch.delay(batch_resources, batch_id)
                task_ids.append(task.id)
                logger.info(f"Submitted batch {batch_id} as task {task.id}")

            return {
                "status": "success",
                "message": f"Submitted {total_batches} batches for processing",
                "total_resources": total_resources,
                "total_batches": total_batches,
                "batch_size": batch_size,
                "max_workers": max_workers,
                "task_ids": task_ids,
            }

    except Exception as e:
        logger.error(f"Error setting up batch jobs: {e}", exc_info=True)
        raise

    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="reindex_spatial_facets_resource")
def reindex_spatial_facets_resource(self, resource_id: str) -> Dict[str, Any]:
    """
    Reindex spatial facets for a specific resource.

    Args:
        resource_id: ID of the resource to reindex

    Returns:
        Dictionary with reindexing results
    """
    logger.info(f"Reindexing spatial facets for resource: {resource_id}")

    try:
        # Run the async reindexing in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_reindex_resource_async(resource_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error reindexing resource {resource_id}: {e}", exc_info=True)
        return {"status": "error", "resource_id": resource_id, "error": str(e)}


async def _reindex_resource_async(resource_id: str) -> Dict[str, Any]:
    """
    Async implementation of resource reindexing.

    Args:
        resource_id: ID of the resource to reindex

    Returns:
        Dictionary with reindexing results
    """
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # Get resource data
            resource_query = text("""
                SELECT id, dcat_bbox
                FROM resources 
                WHERE id = :resource_id
            """)
            result = await session.execute(resource_query, {"resource_id": resource_id})
            resource = result.fetchone()

            if not resource:
                return {
                    "status": "error",
                    "resource_id": resource_id,
                    "error": "Resource not found",
                }

            if not resource.dcat_bbox:
                return {
                    "status": "error",
                    "resource_id": resource_id,
                    "error": "Resource has no dcat_bbox",
                }

            # Compute spatial facets
            resource_dict = {"id": resource_id, "dcat_bbox": resource.dcat_bbox}
            service = SpatialFacetService(resource_dict)
            spatial_facets = await service.get_spatial_facets(session)

            # Update database
            import json

            upsert_query = text("""
                INSERT INTO resource_spatial_facets 
                (resource_id, geo_global, geo_country, geo_region, geo_county)
                VALUES (:resource_id, :geo_global, :geo_country, :geo_region, :geo_county)
                ON CONFLICT (resource_id) 
                DO UPDATE SET 
                    geo_global = EXCLUDED.geo_global,
                    geo_country = EXCLUDED.geo_country,
                    geo_region = EXCLUDED.geo_region,
                    geo_county = EXCLUDED.geo_county,
                    updated_at = NOW()
            """)

            insert_data = {
                "resource_id": resource_id,
                "geo_global": spatial_facets.get("geo.global", False),
                "geo_country": json.dumps(spatial_facets.get("geo.country"))
                if spatial_facets.get("geo.country")
                else None,
                "geo_region": json.dumps(spatial_facets.get("geo.region"))
                if spatial_facets.get("geo.region")
                else None,
                "geo_county": json.dumps(spatial_facets.get("geo.county"))
                if spatial_facets.get("geo.county")
                else None,
            }

            await session.execute(upsert_query, insert_data)
            await session.commit()

            return {
                "status": "success",
                "resource_id": resource_id,
                "spatial_facets": spatial_facets,
            }

    except Exception as e:
        logger.error(f"Error reindexing resource {resource_id}: {e}", exc_info=True)
        return {"status": "error", "resource_id": resource_id, "error": str(e)}

    finally:
        await engine.dispose()
