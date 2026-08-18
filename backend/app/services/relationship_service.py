import logging
from collections.abc import Iterable
from typing import Any, Dict
from urllib.parse import quote

from sqlalchemy import func, select

from db.database import database
from db.models import resource_relationships, resources

logger = logging.getLogger(__name__)

RELATIONSHIP_BROWSE_FACET_FIELDS = {
    "dct:hasPart": "dct_isPartOf_sm",
    "hasPart": "dct_isPartOf_sm",
    "pcdm:hasMember": "pcdm_memberOf_sm",
    "hasMember": "pcdm_memberOf_sm",
    "dct:isSourceOf": "dct_source_sm",
    "isSourceOf": "dct_source_sm",
}
RELATIONSHIP_PREDICATE_ALIASES = {
    "dct:sourceOf": "dct:isSourceOf",
    "sourceOf": "isSourceOf",
}
PUBLICATION_STATE_PUBLISHED = "published"


def _canonical_relationship_predicate(predicate: Any) -> str:
    value = str(predicate)
    return RELATIONSHIP_PREDICATE_ALIASES.get(value, value)


def _relationship_browse_link(resource_id: str, predicate: str) -> str | None:
    facet_field = RELATIONSHIP_BROWSE_FACET_FIELDS.get(_canonical_relationship_predicate(predicate))
    if not facet_field:
        return None
    return f"/search?include_filters[{facet_field}][]={quote(str(resource_id), safe='')}"


def _record_get(record: Any, key: str, default: Any = None) -> Any:
    try:
        return record[key]
    except (KeyError, TypeError):
        return default


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
    def _relationship_query(resource_ids: list[str], limit_per_predicate: int | None = None):
        base_select = (
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
            .where(
                resources.c.publication_state == PUBLICATION_STATE_PUBLISHED,
                resources.c.gbl_suppressed_b.is_not(True),
            )
        )

        if limit_per_predicate is None:
            return base_select.where(
                resource_relationships.c.subject_id.in_(resource_ids)
            ).order_by(
                resource_relationships.c.subject_id.asc(),
                resources.c.dct_title_s.asc(),
            )

        ranked_relationships = base_select.add_columns(
            func.count()
            .over(
                partition_by=(
                    resource_relationships.c.subject_id,
                    resource_relationships.c.predicate,
                )
            )
            .label("total_count"),
            func.row_number()
            .over(
                partition_by=(
                    resource_relationships.c.subject_id,
                    resource_relationships.c.predicate,
                ),
                order_by=(
                    resources.c.dct_title_s.asc(),
                    resource_relationships.c.object_id.asc(),
                ),
            )
            .label("relationship_rank"),
        ).where(resource_relationships.c.subject_id.in_(resource_ids))

        ranked = ranked_relationships.subquery()
        return (
            select(
                ranked.c.subject_id,
                ranked.c.predicate,
                ranked.c.object_id,
                ranked.c.dct_title_s,
                ranked.c.total_count,
            )
            .where(ranked.c.relationship_rank <= limit_per_predicate)
            .order_by(
                ranked.c.subject_id.asc(),
                ranked.c.predicate.asc(),
                ranked.c.relationship_rank.asc(),
            )
        )

    @staticmethod
    async def _fetch_relationship_rows(
        resource_ids: Iterable[str],
        *,
        limit_per_predicate: int | None = None,
    ) -> list[Any]:
        ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
        if not ids:
            return []

        try:
            logger.info("Fetching relationships for resources: %s", ids)
            if not database.is_connected:
                await database.connect()

            relationships_query = RelationshipService._relationship_query(
                ids,
                limit_per_predicate=limit_per_predicate,
            )
            db_relationships = await database.fetch_all(relationships_query)
            logger.info("Found %s relationships", len(db_relationships))
            return db_relationships

        except Exception as e:
            logger.error(f"Error getting relationships: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_resource_relationships_map(
        resource_ids: Iterable[str],
        *,
        limit_per_predicate: int | None = None,
    ) -> Dict[str, Dict]:
        """Get outgoing relationships for many resources in one query."""
        db_relationships = await RelationshipService._fetch_relationship_rows(
            resource_ids,
            limit_per_predicate=limit_per_predicate,
        )

        relationships_by_id: Dict[str, Dict] = {}
        seen_relationships: set[tuple[str, str, str]] = set()

        for rel in db_relationships:
            subject_id = str(rel["subject_id"])
            predicate = _canonical_relationship_predicate(rel["predicate"])
            object_id = str(rel["object_id"])
            relationship_key = (subject_id, predicate, object_id)
            if relationship_key in seen_relationships:
                continue
            seen_relationships.add(relationship_key)

            relationships = relationships_by_id.setdefault(subject_id, {})
            if predicate not in relationships:
                relationships[predicate] = []
            relationships[predicate].append(
                {
                    "resource_id": rel["object_id"],
                    "resource_title": rel["dct_title_s"],
                    "link": f"/resources/{rel['object_id']}",  # Using relative URL
                }
            )
            logger.debug(
                "Added relationship for %s: %s -> %s",
                subject_id,
                predicate,
                rel["object_id"],
            )

        return relationships_by_id

    @staticmethod
    async def get_resource_relationship_summaries_map(
        resource_ids: Iterable[str],
        *,
        limit_per_predicate: int = 5,
    ) -> Dict[str, Dict[str, Any]]:
        """Get limited relationship previews plus total counts for search results."""
        db_relationships = await RelationshipService._fetch_relationship_rows(
            resource_ids,
            limit_per_predicate=limit_per_predicate,
        )

        summaries_by_id: Dict[str, Dict[str, Any]] = {}
        seen_relationships: set[tuple[str, str, str]] = set()

        for rel in db_relationships:
            subject_id = str(rel["subject_id"])
            predicate = _canonical_relationship_predicate(rel["predicate"])
            object_id = str(rel["object_id"])
            summary = summaries_by_id.setdefault(
                subject_id,
                {
                    "relationships": {},
                    "counts": {},
                    "browse_links": {},
                },
            )
            relationships = summary["relationships"].setdefault(predicate, [])
            relationship_key = (subject_id, predicate, object_id)
            if relationship_key not in seen_relationships:
                seen_relationships.add(relationship_key)
                relationships.append(
                    {
                        "resource_id": rel["object_id"],
                        "resource_title": rel["dct_title_s"],
                        "link": f"/resources/{rel['object_id']}",
                    }
                )

            total_count = _record_get(rel, "total_count", len(relationships))
            summary["counts"][predicate] = max(
                summary["counts"].get(predicate, 0), int(total_count)
            )

            browse_link = _relationship_browse_link(subject_id, predicate)
            if browse_link:
                summary["browse_links"][predicate] = browse_link

        return summaries_by_id
