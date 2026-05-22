import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.elasticsearch.search import find_similar_resources
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from db.models import resource_assets, resources

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
                    # Prefer bridge-provided thumbnail-capable asset (same logic
                    # as resource-view meta.ui.thumbnail_url).
                    bridge_thumb_stmt = (
                        select(resource_assets.c.file_url)
                        .where(
                            resource_assets.c.resource_id == similar_id,
                            resource_assets.c.thumbnail.is_(True),
                            resource_assets.c.file_url.is_not(None),
                        )
                        .order_by(
                            resource_assets.c.position.asc(),
                            resource_assets.c.id.asc(),
                        )
                        .limit(1)
                    )
                    thumb_row = await session.execute(bridge_thumb_stmt)
                    bridge_file_url = thumb_row.scalar_one_or_none()
                    if isinstance(bridge_file_url, str):
                        bridge_file_url = bridge_file_url.strip()
                        if bridge_file_url:
                            thumbnail_url = bridge_file_url

                    # Fallback to existing endpoint-based thumbnail behavior.
                    if not thumbnail_url:
                        distribution_context = await fetch_distribution_context(
                            similar_id,
                            session=session,
                        )
                        image_service = ImageService(
                            resource_dict,
                            distribution_context=distribution_context,
                        )
                        thumbnail_url = image_service.get_thumbnail_url()
                except Exception as e:
                    logger.warning(
                        f"Error getting thumbnail for similar resource {similar_id}: {str(e)}"
                    )
                    # Continue without thumbnail

                # Index year (DB: gbl_indexYear_im array of ints; support downcased column)
                index_year_raw = resource_dict.get("gbl_indexYear_im") or resource_dict.get(
                    "gbl_indexyear_im"
                )
                gbl_indexYear_im = (
                    [index_year_raw] if isinstance(index_year_raw, int) else (index_year_raw or [])
                )
                if not isinstance(gbl_indexYear_im, list):
                    gbl_indexYear_im = []

                # Resource class (DB: gbl_resourceClass_sm array of strings)
                resource_class_raw = resource_dict.get("gbl_resourceClass_sm") or resource_dict.get(
                    "gbl_resourceclass_sm"
                )
                gbl_resourceClass_sm = (
                    [resource_class_raw]
                    if isinstance(resource_class_raw, str)
                    else (resource_class_raw or [])
                )
                if not isinstance(gbl_resourceClass_sm, list):
                    gbl_resourceClass_sm = []

                similar_items.append(
                    {
                        "id": similar_id,
                        "title": title,
                        "temporal_coverage": temporal_coverage,
                        "thumbnail_url": thumbnail_url,
                        "gbl_indexYear_im": gbl_indexYear_im,
                        "gbl_resourceClass_sm": gbl_resourceClass_sm,
                    }
                )

            return similar_items

        except Exception as e:
            logger.error(f"Error getting similar items for {resource_id}: {str(e)}", exc_info=True)
            # Return empty list on error to avoid breaking resource processing
            return []
