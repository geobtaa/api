"""
Service layer for admin operations.
Provides abstraction for cache management, reindexing, and resource processing.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select

from app.elasticsearch.index import reindex_resources
from app.services.cache_service import ENDPOINT_CACHE, CacheService, invalidate_cache_with_prefix
from app.tasks.entities import generate_geo_entities
from app.tasks.summarization import generate_resource_summary
from db.database import database
from db.models import resources

logger = logging.getLogger(__name__)


class CacheManagementService:
    """Service for managing cache operations."""

    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service or CacheService()

    async def clear_cache_by_type(self, cache_type: Optional[str] = None) -> Dict[str, Any]:
        """Clear cache by type or all cache if not specified."""
        try:
            if cache_type == "search" or cache_type is None or cache_type == "all":
                await invalidate_cache_with_prefix("app.api.v1.endpoints:search")

            if cache_type == "resource" or cache_type is None or cache_type == "all":
                await invalidate_cache_with_prefix("app.api.v1.endpoints:get_resource")

            if cache_type == "suggest" or cache_type is None or cache_type == "all":
                await invalidate_cache_with_prefix("app.api.v1.endpoints:suggest")

            if cache_type == "all" or cache_type is None:
                await self.cache_service.flush_all()

            return {"message": f"Cache cleared successfully: {cache_type or 'all'}"}
        except Exception as e:
            raise CacheManagementError(f"Failed to clear cache: {str(e)}") from e


class ReindexingService:
    """Service for managing reindexing operations."""

    async def check_spatial_facet_readiness(self) -> Dict[str, Any]:
        """Check if spatial facets are ready for reindexing."""
        try:
            from app.services.spatial_facet_indexing_service import SpatialFacetIndexingService

            service = SpatialFacetIndexingService()
            stats = await service.get_indexing_stats()

            if "error" in stats:
                return {"ready": False, "stats": stats}

            total_resources = stats.get("total_resources_with_bbox", 0)
            indexed_resources = stats.get("indexed_resources", 0)
            progress = stats.get("indexing_progress", 0)

            # Consider ready if at least 50% are indexed or if we have a reasonable number
            ready = progress >= 50 or indexed_resources >= 1000

            return {
                "ready": ready,
                "progress": progress,
                "indexed_resources": indexed_resources,
                "total_resources": total_resources,
                "stats": stats,
            }
        except Exception as e:
            logger.error(f"Error checking spatial facet readiness: {e}")
            return {"ready": False, "error": str(e)}

    async def reindex_all_resources(self) -> Dict[str, Any]:
        """Trigger reindexing of all items in Elasticsearch."""
        try:
            # Check spatial facet readiness
            spatial_readiness = await self.check_spatial_facet_readiness()

            # When reindexing, invalidate all search and suggest caches
            if ENDPOINT_CACHE:
                logger.info("Invalidating search and suggest caches")
                await invalidate_cache_with_prefix("app.api.v1.endpoints:search")
                await invalidate_cache_with_prefix("app.api.v1.endpoints:suggest")

            result = await reindex_resources()

            # Include spatial facet status in response
            return {
                "status": "success",
                "message": "Reindexing completed",
                "details": result,
                "spatial_facets": spatial_readiness,
            }
        except Exception as e:
            logger.error(f"Reindexing failed: {str(e)}", exc_info=True)
            raise ReindexingError(f"Reindexing failed: {str(e)}") from e


class ResourceProcessingService:
    """Service for processing resource operations."""

    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service or CacheService()

    async def get_resource_by_id(self, resource_id: str) -> Dict[str, Any]:
        """Fetch a resource by ID from the database."""
        try:
            async with database.transaction():
                query = select(resources).where(resources.c.id == resource_id)
                result = await database.fetch_one(query)

                if not result:
                    raise ResourceNotFoundError(f"Resource {resource_id} not found")

                # Convert to dict and handle datetime serialization
                resource = dict(result)
                for key, value in resource.items():
                    if isinstance(value, datetime):
                        resource[key] = value.isoformat()

                logger.info(f"Retrieved resource {resource_id}")
                logger.debug(f"Raw resource data: {json.dumps(resource, indent=2)}")

                return resource
        except ResourceNotFoundError:
            raise
        except Exception as e:
            raise ResourceProcessingError(
                f"Failed to fetch resource {resource_id}: {str(e)}"
            ) from e

    def parse_resource_references(
        self, resource: Dict[str, Any], resource_id: str
    ) -> Dict[str, Any]:
        """Parse resource references from dct_references_s field."""
        references = resource.get("dct_references_s", {})
        logger.info(f"Raw references for resource {resource_id}: {references}")

        if isinstance(references, str):
            try:
                references = json.loads(references)
                logger.info(
                    f"Parsed references for resource {resource_id}: "
                    f"{json.dumps(references, indent=2)}"
                )
            except json.JSONDecodeError:
                logger.error(
                    f"Failed to parse references JSON for resource {resource_id}: {references}"
                )
                references = {}

        return references

    def determine_asset_info(
        self, resource: Dict[str, Any], references: Dict[str, Any], resource_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Determine asset path and type from resource references."""
        asset_path = None
        asset_type = None

        # Define asset type mappings
        asset_type_mappings = {
            "http://schema.org/downloadUrl": "download",
            "http://iiif.io/api/image": "iiif_image",
            "http://iiif.io/api/presentation#manifest": "iiif_manifest",
            "https://github.com/cogeotiff/cog-spec": "cog",
            "https://github.com/protomaps/PMTiles": "pmtiles",
        }

        # Check for each reference type
        for ref_type, asset_type_name in asset_type_mappings.items():
            if ref_type in references:
                ref_value = references[ref_type]
                logger.info(
                    f"Found reference type {ref_type} with value {ref_value} "
                    f"for resource {resource_id}"
                )

                # Handle both string and array values
                if isinstance(ref_value, list) and ref_value:
                    # For arrays, take the first item for now
                    asset_path = ref_value[0]
                    asset_type = asset_type_name
                    logger.info(
                        f"Using first item from array: asset_path={asset_path}, "
                        f"asset_type={asset_type}"
                    )
                    break
                elif isinstance(ref_value, str) and ref_value:
                    asset_path = ref_value
                    asset_type = asset_type_name
                    logger.info(
                        f"Using string value: asset_path={asset_path}, asset_type={asset_type}"
                    )
                    break

        # If no specific asset type was found, use the resource format as fallback
        if not asset_type:
            asset_type = resource.get("dc_format_s")
            logger.info(f"No specific asset type found, using format fallback: {asset_type}")

        logger.info(
            f"Final asset determination for resource {resource_id}: "
            f"path={asset_path}, type={asset_type}"
        )
        return asset_path, asset_type

    async def start_summarization_task(
        self,
        resource_id: str,
        resource: Dict[str, Any],
        asset_path: Optional[str],
        asset_type: Optional[str],
    ) -> str:
        """Start the summarization task for a resource."""
        try:
            # Trigger the summarization task
            summary_task = generate_resource_summary.delay(
                resource_id=resource_id,
                metadata=resource,
                asset_path=asset_path,
                asset_type=asset_type,
            )
            logger.info(f"Started summary task {summary_task.id} for resource {resource_id}")

            # Invalidate the resource cache since we'll be updating it
            invalidate_cache_with_prefix(f"resource:{resource_id}")

            return summary_task.id
        except Exception as e:
            raise ResourceProcessingError(
                f"Failed to start summarization task for resource {resource_id}: {str(e)}"
            ) from e

    async def start_geo_entities_task(self, resource_id: str, resource: Dict[str, Any]) -> str:
        """Start the geographic entity identification task for a resource."""
        try:
            # Trigger the geographic entity identification task
            geo_entities_task = generate_geo_entities.delay(
                resource_id=resource_id, metadata=resource
            )
            logger.info(
                f"Started geographic entity identification task {geo_entities_task.id} "
                f"for resource {resource_id}"
            )

            # Invalidate the resource cache since we'll be updating it
            invalidate_cache_with_prefix(f"resource:{resource_id}")

            return geo_entities_task.id
        except Exception as e:
            raise ResourceProcessingError(
                f"Failed to start geo entities task for resource {resource_id}: {str(e)}"
            ) from e


class AdminService:
    """Main service for admin operations."""

    def __init__(
        self,
        cache_management_service: Optional[CacheManagementService] = None,
        reindexing_service: Optional[ReindexingService] = None,
        resource_processing_service: Optional[ResourceProcessingService] = None,
    ):
        self.cache_management_service = cache_management_service or CacheManagementService()
        self.reindexing_service = reindexing_service or ReindexingService()
        self.resource_processing_service = (
            resource_processing_service or ResourceProcessingService()
        )

    async def clear_cache(self, cache_type: Optional[str] = None) -> Dict[str, Any]:
        """Clear cache by type."""
        return await self.cache_management_service.clear_cache_by_type(cache_type)

    async def reindex_resources(self) -> Dict[str, Any]:
        """Reindex all resources."""
        return await self.reindexing_service.reindex_all_resources()

    async def summarize_resource(self, resource_id: str) -> Dict[str, Any]:
        """Start summarization for a resource."""
        # Get resource
        resource = await self.resource_processing_service.get_resource_by_id(resource_id)

        # Parse references
        references = self.resource_processing_service.parse_resource_references(
            resource, resource_id
        )

        # Determine asset info
        asset_path, asset_type = self.resource_processing_service.determine_asset_info(
            resource, references, resource_id
        )

        # Start task
        task_id = await self.resource_processing_service.start_summarization_task(
            resource_id, resource, asset_path, asset_type
        )

        return {
            "status": "success",
            "message": "Summary generation started",
            "task_id": task_id,
        }

    async def identify_geo_entities(self, resource_id: str) -> Dict[str, Any]:
        """Start geographic entity identification for a resource."""
        # Get resource
        resource = await self.resource_processing_service.get_resource_by_id(resource_id)

        # Start task
        task_id = await self.resource_processing_service.start_geo_entities_task(
            resource_id, resource
        )

        return {
            "status": "success",
            "message": "Geographic entity identification started",
            "task_id": task_id,
        }


# Custom exceptions
class CacheManagementError(Exception):
    """Raised when cache management operations fail."""

    pass


class ReindexingError(Exception):
    """Raised when reindexing operations fail."""

    pass


class ResourceProcessingError(Exception):
    """Raised when resource processing operations fail."""

    pass


class ResourceNotFoundError(Exception):
    """Raised when a resource is not found."""

    pass
