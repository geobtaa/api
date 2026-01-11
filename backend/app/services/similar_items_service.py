import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.elasticsearch.search import find_similar_resources
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from db.models import resources

logger = logging.getLogger(__name__)


class SimilarItemsService:
    """Service for finding and formatting similar resources."""

    @staticmethod
    async def get_similar_items(
        resource_id: str, session: AsyncSession, limit: int = 12
    ) -> List[dict]:
        """
        Get similar items for a resource.

        Args:
            resource_id: The ID of the resource to find similar items for
            session: Database session for fetching resource data
            limit: Maximum number of similar items to return (default: 12)

        Returns:
            List of similar item dictionaries with id, title, temporal_coverage, and thumbnail_url
        """
        try:
            # Find similar resource IDs from Elasticsearch
            similar_ids = await find_similar_resources(resource_id, limit=limit)

            if not similar_ids:
                return []

            # Fetch resource data from database
            query = select(resources).where(resources.c.id.in_(similar_ids))
            result = await session.execute(query)
            rows = result.fetchall()

            # Build lookup dictionary
            resource_lookup = {}
            for row in rows:
                resource_dict = dict(row._mapping)
                resource_lookup[resource_dict["id"]] = resource_dict

            # Build similar items list in the order returned by Elasticsearch
            similar_items = []
            for similar_id in similar_ids:
                if similar_id not in resource_lookup:
                    logger.warning(
                        f"Similar resource {similar_id} found in Elasticsearch but not in database"
                    )
                    continue

                resource_dict = resource_lookup[similar_id]

                # Get title
                title = resource_dict.get("dct_title_s") or ""

                # Get temporal coverage
                temporal_coverage = resource_dict.get("dct_temporal_sm")
                if temporal_coverage is None:
                    temporal_coverage = []
                elif isinstance(temporal_coverage, str):
                    # Handle case where it's a single string
                    temporal_coverage = [temporal_coverage]
                elif not isinstance(temporal_coverage, list):
                    temporal_coverage = []

                # Get thumbnail URL using ImageService
                thumbnail_url = None
                try:
                    distribution_context = await fetch_distribution_context(similar_id)
                    image_service = ImageService(
                        resource_dict, distribution_context=distribution_context
                    )
                    thumbnail_url = image_service.get_thumbnail_url()
                except Exception as e:
                    logger.warning(
                        f"Error getting thumbnail for similar resource {similar_id}: {str(e)}"
                    )
                    # Continue without thumbnail

                similar_items.append(
                    {
                        "id": similar_id,
                        "title": title,
                        "temporal_coverage": temporal_coverage,
                        "thumbnail_url": thumbnail_url,
                    }
                )

            return similar_items

        except Exception as e:
            logger.error(f"Error getting similar items for {resource_id}: {str(e)}", exc_info=True)
            # Return empty list on error to avoid breaking resource processing
            return []
