import logging
from typing import Dict

from db.database import database

logger = logging.getLogger(__name__)


class RelationshipService:
    """Service for handling resource relationships."""

    @staticmethod
    async def get_resource_relationships(resource_id: str) -> Dict:
        """Get all relationships for a resource."""
        try:
            logger.info(f"Fetching relationships for resource: {resource_id}")

            # Get outgoing relationships (where resource is subject)
            relationships_query = """
                SELECT predicate, object_id, dct_title_s
                FROM resource_relationships
                JOIN resources 
                ON resources.id = resource_relationships.object_id
                WHERE subject_id = :resource_id
                ORDER BY dct_title_s ASC
            """
            db_relationships = await database.fetch_all(
                relationships_query, {"resource_id": resource_id}
            )
            logger.info(f"Found {len(db_relationships)} relationships")
            logger.info(f"Relationships: {db_relationships}")

            relationships = {}

            # Process outgoing relationships
            for rel in db_relationships:
                if rel["predicate"] not in relationships:
                    relationships[rel["predicate"]] = []
                relationships[rel["predicate"]].append(
                    {
                        "resource_id": rel["object_id"],
                        "resource_title": rel["dct_title_s"],
                        "link": f"/resources/{rel['object_id']}",  # Using relative URL
                    }
                )
                logger.debug(f"Added relationship: {rel['predicate']} -> {rel['object_id']}")

            logger.info(f"Final relationships structure: {relationships}")
            return relationships

        except Exception as e:
            logger.error(f"Error getting relationships: {e}", exc_info=True)
            return {}
