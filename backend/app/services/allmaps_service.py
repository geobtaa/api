import logging
from collections.abc import Iterable
from typing import Dict
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import resource_allmaps

logger = logging.getLogger(__name__)


def _build_allmaps_attributes(row_mapping) -> Dict:
    manifest_uri = row_mapping.get("iiif_manifest_uri")
    annotated = row_mapping.get("annotated")

    attributes = {
        "allmaps_id": row_mapping.get("allmaps_id"),
        "allmaps_annotated": annotated,
        "allmaps_manifest_uri": manifest_uri,
    }

    if manifest_uri and annotated:
        attributes["allmaps_annotation_url"] = (
            f"https://annotations.allmaps.org/?url={quote(manifest_uri, safe='')}"
        )

    return attributes


async def fetch_allmaps_attributes_map(
    resource_ids: Iterable[str], session: AsyncSession
) -> Dict[str, Dict]:
    """Fetch Allmaps attributes for many resources in one query."""
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    try:
        query = select(resource_allmaps).where(resource_allmaps.c.resource_id.in_(ids))
        result = await session.execute(query)
        rows = result.fetchall()
    except Exception as e:
        logger.error("Error getting Allmaps attributes for resources %s: %s", ids, e, exc_info=True)
        return {}

    attributes_by_id: Dict[str, Dict] = {}
    for row in rows:
        mapping = row._mapping
        resource_id = str(mapping.get("resource_id") or "")
        if not resource_id:
            continue
        attributes_by_id[resource_id] = _build_allmaps_attributes(mapping)

    return attributes_by_id


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
            logger.info("Fetching Allmaps attributes for resource %s", self.resource_id)
            attributes = (await fetch_allmaps_attributes_map([self.resource_id], session)).get(
                self.resource_id,
                {},
            )
            if not attributes:
                logger.info("No Allmaps data found for resource %s", self.resource_id)
                return {}

            logger.info("Returning Allmaps attributes: %s", attributes)
            return attributes

        except Exception as e:
            logger.error(
                f"Error getting Allmaps attributes for resource {self.resource_id}: {e}",
                exc_info=True,
            )
            return {}
