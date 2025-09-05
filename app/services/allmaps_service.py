import logging
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import resource_allmaps

logger = logging.getLogger(__name__)


class AllmapsService:
    """Service for handling Allmaps data and annotations."""

    def __init__(self, resource: Dict):
        """Initialize the service with a resource dictionary."""
        self.resource = resource
        # Handle both direct id and nested id in attributes
        self.resource_id = str(resource.get("id") or resource.get("attributes", {}).get("id"))
        if not self.resource_id:
            logger.warning(f"No resource ID found in resource data: {resource}")
        else:
            logger.info(f"Initialized AllmapsService for resource {self.resource_id}")

    async def get_allmaps_attributes(self, session: AsyncSession) -> Dict:
        """Get Allmaps attributes for the resource.

        Args:
            session: SQLAlchemy async database session

        Returns:
            Dict containing Allmaps attributes if found, empty dict otherwise
        """
        if not self.resource_id:
            logger.warning("Cannot get Allmaps attributes: No resource ID available")
            return {}

        try:
            # Query the resource_allmaps table
            query = select(resource_allmaps).where(
                resource_allmaps.c.resource_id == self.resource_id
            )
            logger.info(f"Executing query for resource {self.resource_id}: {query}")

            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                logger.info(f"No Allmaps data found for resource {self.resource_id}")
                return {}

            # Convert to dict and extract relevant fields
            allmaps_dict = dict(row._mapping)
            logger.info(f"Found Allmaps data for resource {self.resource_id}: {allmaps_dict}")

            attributes = {
                "allmaps_id": allmaps_dict.get("allmaps_id"),
                "allmaps_annotated": allmaps_dict.get("annotated"),
                "allmaps_manifest_uri": allmaps_dict.get("iiif_manifest_uri"),
            }
            logger.info(f"Returning Allmaps attributes: {attributes}")
            return attributes

        except Exception as e:
            logger.error(
                f"Error getting Allmaps attributes for resource {self.resource_id}: {e}",
                exc_info=True,
            )
            return {}
