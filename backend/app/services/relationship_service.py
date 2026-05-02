import logging
from collections.abc import Iterable
from typing import Dict

from sqlalchemy import select

from db.database import database
from db.models import resource_relationships, resources

logger = logging.getLogger(__name__)


class RelationshipService:
    """Service for handling resource relationships."""

    @staticmethod
    async def get_resource_relationships(resource_id: str) -> Dict:
        """Get all relationships for a resource."""
        relationships_by_id = await RelationshipService.get_resource_relationships_map(
            [resource_id]
        )
        return relationships_by_id.get(resource_id, {})

    @staticmethod
    async def get_resource_relationships_map(resource_ids: Iterable[str]) -> Dict[str, Dict]:
        """Get outgoing relationships for many resources in one query."""
        ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
        if not ids:
            return {}

        try:
            logger.info("Fetching relationships for resources: %s", ids)
            if not database.is_connected:
                await database.connect()

            relationships_query = (
                select(
                    resource_relationships.c.subject_id,
                    resource_relationships.c.predicate,
                    resource_relationships.c.object_id,
                    resources.c.dct_title_s,
                )
                .select_from(
                    resource_relationships.join(
                        resources,
                        resources.c.id == resource_relationships.c.object_id,
                    )
                )
                .where(resource_relationships.c.subject_id.in_(ids))
                .order_by(
                    resource_relationships.c.subject_id.asc(),
                    resources.c.dct_title_s.asc(),
                )
            )
            db_relationships = await database.fetch_all(relationships_query)
            logger.info("Found %s relationships", len(db_relationships))

            relationships_by_id: Dict[str, Dict] = {}

            for rel in db_relationships:
                subject_id = str(rel["subject_id"])
                relationships = relationships_by_id.setdefault(subject_id, {})
                if rel["predicate"] not in relationships:
                    relationships[rel["predicate"]] = []
                relationships[rel["predicate"]].append(
                    {
                        "resource_id": rel["object_id"],
                        "resource_title": rel["dct_title_s"],
                        "link": f"/resources/{rel['object_id']}",  # Using relative URL
                    }
                )
                logger.debug(
                    "Added relationship for %s: %s -> %s",
                    subject_id,
                    rel["predicate"],
                    rel["object_id"],
                )

            return relationships_by_id

        except Exception as e:
            logger.error(f"Error getting relationships: {e}", exc_info=True)
            return {}
