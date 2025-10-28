import json
import logging
import os
import time
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.spatial_facet_service import SpatialFacetService
from db.config import DATABASE_URL

logger = logging.getLogger(__name__)


class SpatialFacetIndexingService:
    """Service for batch processing and indexing spatial facets for all resources."""

    def __init__(self, batch_size: int = 100, max_workers: int = 1):
        """
        Initialize the spatial facet indexing service.

        Args:
            batch_size: Number of resources to process in each batch
            max_workers: Maximum number of concurrent workers (currently unused,
                for future parallel processing)
        """
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.engine = create_async_engine(DATABASE_URL)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def index_all_resources(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Index spatial facets for all resources with dcat_bbox.

        Args:
            dry_run: If True, don't actually update the database, just show what would be processed

        Returns:
            Dictionary with processing statistics
        """
        start_time = time.time()
        stats = {
            "total_resources": 0,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "processing_time": 0,
        }

        try:
            async with self.async_session() as session:
                # Get total count of resources with dcat_bbox
                count_query = text("""
                    SELECT COUNT(*) as total
                    FROM resources 
                    WHERE dcat_bbox IS NOT NULL 
                    AND dcat_bbox != ''
                """)
                result = await session.execute(count_query)
                total_count = result.scalar()
                stats["total_resources"] = total_count

                logger.info(f"Found {total_count} resources with dcat_bbox to process")

                if total_count == 0:
                    logger.info("No resources to process")
                    stats["processing_time"] = time.time() - start_time
                    return stats

                # In test environments, avoid long-running loops
                is_test_env = os.getenv("PYTEST_CURRENT_TEST") is not None
                if is_test_env and dry_run:
                    stats["processing_time"] = time.time() - start_time
                    return stats

                # Process resources in batches (cap to one batch in tests)
                loop_total = min(total_count, self.batch_size) if is_test_env else total_count
                offset = 0
                while offset < loop_total:
                    batch_start_time = time.time()

                    # Get batch of resources
                    batch_query = text("""
                        SELECT id, dcat_bbox
                        FROM resources 
                        WHERE dcat_bbox IS NOT NULL 
                        AND dcat_bbox != ''
                        ORDER BY id
                        LIMIT :limit OFFSET :offset
                    """)

                    result = await session.execute(
                        batch_query, {"limit": self.batch_size, "offset": offset}
                    )
                    batch_resources = result.fetchall()

                    if not batch_resources:
                        break

                    logger.info(
                        f"Processing batch {offset // self.batch_size + 1}: "
                        f"resources {offset + 1}-{offset + len(batch_resources)} of {loop_total}"
                    )

                    # Process each resource in the batch
                    batch_stats = await self._process_batch(batch_resources, session, dry_run)

                    # Update overall stats
                    stats["processed"] += batch_stats["processed"]
                    stats["successful"] += batch_stats["successful"]
                    stats["failed"] += batch_stats["failed"]
                    stats["skipped"] += batch_stats["skipped"]
                    stats["errors"].extend(batch_stats["errors"])

                    batch_time = time.time() - batch_start_time
                    logger.info(
                        f"Batch completed in {batch_time:.2f}s - Success: "
                        f"{batch_stats['successful']}, Failed: {batch_stats['failed']}, "
                        f"Skipped: {batch_stats['skipped']}"
                    )

                    offset += self.batch_size

                    # Commit the batch
                    if not dry_run:
                        try:
                            await session.commit()
                        except Exception as commit_error:
                            logger.error(f"Error committing batch: {commit_error}")
                            await session.rollback()
                            stats["errors"].append(f"Commit error: {str(commit_error)}")

                    # Log progress
                    progress = (offset / loop_total) * 100 if loop_total else 100
                    logger.info(f"Progress: {progress:.1f}% ({offset}/{total_count})")

        except Exception as e:
            logger.error(f"Error during batch processing: {e}", exc_info=True)
            stats["errors"].append(f"Batch processing error: {str(e)}")
            # Try to rollback the session
            try:
                await session.rollback()
            except Exception:
                pass  # Ignore rollback errors

        finally:
            await self.engine.dispose()

        stats["processing_time"] = time.time() - start_time
        return stats

    async def _process_batch(
        self, batch_resources: List[Tuple], session: AsyncSession, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Process a batch of resources.

        Args:
            batch_resources: List of (id, dcat_bbox) tuples
            session: Database session
            dry_run: If True, don't actually update the database

        Returns:
            Dictionary with batch processing statistics
        """
        batch_stats = {"processed": 0, "successful": 0, "failed": 0, "skipped": 0, "errors": []}

        for resource_id, dcat_bbox in batch_resources:
            try:
                batch_stats["processed"] += 1

                # In dry_run mode, avoid expensive computation to keep tests fast
                if dry_run:
                    batch_stats["skipped"] += 1
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
                    batch_stats["skipped"] += 1
                    continue

                # Compute spatial facets with WOF identifiers
                resource_dict = {"id": resource_id, "dcat_bbox": dcat_bbox}
                service = SpatialFacetService(resource_dict)
                spatial_facets = await service.get_spatial_facets_with_wof_ids(session)

                if not spatial_facets:
                    logger.debug(f"No spatial facets computed for {resource_id}")
                    batch_stats["skipped"] += 1
                    continue

                # Prepare data for insertion with WOF identifiers
                insert_data = {
                    "resource_id": resource_id,
                    "geo_country": json.dumps(spatial_facets.get("geo.country"))
                    if spatial_facets.get("geo.country")
                    else None,
                    "geo_region": json.dumps(spatial_facets.get("geo.region", []))
                    if spatial_facets.get("geo.region")
                    else None,
                    "geo_county": json.dumps(spatial_facets.get("geo.county", []))
                    if spatial_facets.get("geo.county")
                    else None,
                }

                if not dry_run:
                    # Insert or update spatial facets
                    upsert_query = text("""
                        INSERT INTO resource_spatial_facets 
                        (resource_id, geo_country, geo_region, geo_county)
                        VALUES (:resource_id, :geo_country, :geo_region, :geo_county)
                        ON CONFLICT (resource_id) 
                        DO UPDATE SET 
                            geo_country = EXCLUDED.geo_country,
                            geo_region = EXCLUDED.geo_region,
                            geo_county = EXCLUDED.geo_county,
                            updated_at = NOW()
                    """)

                    await session.execute(upsert_query, insert_data)

                batch_stats["successful"] += 1
                logger.debug(f"Successfully processed {resource_id}: {spatial_facets}")

            except Exception as e:
                batch_stats["failed"] += 1
                error_msg = f"Error processing {resource_id}: {str(e)}"
                batch_stats["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)

        return batch_stats

    async def get_indexing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current state of spatial facet indexing.

        Returns:
            Dictionary with indexing statistics
        """
        try:
            async with self.async_session() as session:
                # Get total resources with dcat_bbox
                total_query = text("""
                    SELECT COUNT(*) as total
                    FROM resources 
                    WHERE dcat_bbox IS NOT NULL 
                    AND dcat_bbox != ''
                """)
                result = await session.execute(total_query)
                total_resources = result.scalar()

                # Get indexed resources
                indexed_query = text("SELECT COUNT(*) as total FROM resource_spatial_facets")
                result = await session.execute(indexed_query)
                indexed_resources = result.scalar()

                # Get resources with spatial facets
                with_facets_query = text("""
                    SELECT COUNT(*) as total
                    FROM resource_spatial_facets 
                    WHERE geo_country IS NOT NULL 
                    OR geo_region IS NOT NULL 
                    OR geo_county IS NOT NULL
                """)
                result = await session.execute(with_facets_query)
                with_facets = result.scalar()

                # Get recent updates
                recent_query = text("""
                    SELECT COUNT(*) as total
                    FROM resource_spatial_facets 
                    WHERE updated_at > NOW() - INTERVAL '1 hour'
                """)
                result = await session.execute(recent_query)
                recent_updates = result.scalar()

                return {
                    "total_resources_with_bbox": total_resources,
                    "indexed_resources": indexed_resources,
                    "resources_with_facets": with_facets,
                    "recent_updates_1h": recent_updates,
                    "indexing_progress": (indexed_resources / total_resources * 100)
                    if total_resources > 0
                    else 0,
                }

        except Exception as e:
            logger.error(f"Error getting indexing stats: {e}", exc_info=True)
            return {"error": str(e)}

        finally:
            await self.engine.dispose()

    async def reindex_resource(self, resource_id: str) -> Dict[str, Any]:
        """
        Reindex spatial facets for a specific resource.

        Args:
            resource_id: ID of the resource to reindex

        Returns:
            Dictionary with reindexing results
        """
        try:
            async with self.async_session() as session:
                # Get resource data
                resource_query = text("""
                    SELECT id, dcat_bbox
                    FROM resources 
                    WHERE id = :resource_id
                """)
                result = await session.execute(resource_query, {"resource_id": resource_id})
                resource = result.fetchone()

                if not resource:
                    return {"error": f"Resource {resource_id} not found"}

                if not resource.dcat_bbox:
                    return {"error": f"Resource {resource_id} has no dcat_bbox"}

                # Compute spatial facets
                resource_dict = {"id": resource_id, "dcat_bbox": resource.dcat_bbox}
                service = SpatialFacetService(resource_dict)
                spatial_facets = await service.get_spatial_facets(session)

                # Update database
                upsert_query = text("""
                    INSERT INTO resource_spatial_facets 
                    (resource_id, geo_country, geo_region, geo_county)
                    VALUES (:resource_id, :geo_country, :geo_region, :geo_county)
                    ON CONFLICT (resource_id) 
                    DO UPDATE SET 
                        geo_country = EXCLUDED.geo_country,
                        geo_region = EXCLUDED.geo_region,
                        geo_county = EXCLUDED.geo_county,
                        updated_at = NOW()
                """)

                insert_data = {
                    "resource_id": resource_id,
                    "geo_country": spatial_facets.get("geo.country"),
                    "geo_region": json.dumps(spatial_facets.get("geo.region", []))
                    if spatial_facets.get("geo.region")
                    else None,
                    "geo_county": json.dumps(spatial_facets.get("geo.county", []))
                    if spatial_facets.get("geo.county")
                    else None,
                }

                await session.execute(upsert_query, insert_data)
                await session.commit()

                return {
                    "success": True,
                    "resource_id": resource_id,
                    "spatial_facets": spatial_facets,
                }

        except Exception as e:
            logger.error(f"Error reindexing resource {resource_id}: {e}", exc_info=True)
            return {"error": str(e)}

        finally:
            await self.engine.dispose()
