from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from sqlalchemy import delete, or_, select

from db.database import database
from db.models import resource_relationships, resources

logger = logging.getLogger(__name__)


RELATIONSHIP_FAMILIES: Tuple[Tuple[str, str, str], ...] = (
    ("dct_relation_sm", "dct:relation", "dct:relation"),
    ("dct_isPartOf_sm", "dct:isPartOf", "dct:hasPart"),
    ("pcdm_memberOf_sm", "pcdm:memberOf", "pcdm:hasMember"),
    ("dct_source_sm", "dct:source", "dct:sourceOf"),
    ("dct_isVersionOf_sm", "dct:isVersionOf", "dct:hasVersion"),
    ("dct_replaces_sm", "dct:replaces", "dct:isReplacedBy"),
    ("dct_isReplacedBy_sm", "dct:isReplacedBy", "dct:replaces"),
)

ALL_RELATIONSHIP_PREDICATES: Tuple[str, ...] = tuple(
    sorted(
        {
            predicate
            for _, predicate, inverse in RELATIONSHIP_FAMILIES
            for predicate in (predicate, inverse)
        }
    )
)


def _normalize_resource_ids(resource_ids: Sequence[Any]) -> List[str]:
    normalized: List[str] = []
    seen: Set[str] = set()
    for resource_id in resource_ids:
        value = str(resource_id or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _normalize_related_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]

    related_ids: List[str] = []
    seen: Set[str] = set()
    for item in raw_values:
        candidate = str(item or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        related_ids.append(candidate)
    return related_ids


def _build_relationship_rows(
    rows_by_family: Dict[Tuple[str, str, str], Iterable[Dict[str, Any]]],
    tracked_ids: Sequence[Any],
) -> List[Dict[str, str]]:
    tracked = set(_normalize_resource_ids(tracked_ids))
    relationships: Set[Tuple[str, str, str]] = set()

    for (field_name, predicate, inverse_predicate), rows in rows_by_family.items():
        for row in rows:
            subject_id = str(row.get("id") or "").strip()
            if not subject_id:
                continue

            related_ids = _normalize_related_ids(row.get(field_name))
            for object_id in related_ids:
                if object_id == subject_id:
                    continue
                if subject_id not in tracked and object_id not in tracked:
                    continue
                relationships.add((subject_id, predicate, object_id))
                relationships.add((object_id, inverse_predicate, subject_id))

    return [
        {"subject_id": subject_id, "predicate": predicate, "object_id": object_id}
        for subject_id, predicate, object_id in sorted(relationships)
    ]


async def sync_relationships_for_resource_ids(resource_ids: Sequence[Any]) -> int:
    tracked_ids = _normalize_resource_ids(resource_ids)
    if not tracked_ids:
        return 0

    if not database.is_connected:
        await database.connect()

    await database.execute(
        delete(resource_relationships).where(
            resource_relationships.c.predicate.in_(ALL_RELATIONSHIP_PREDICATES),
            or_(
                resource_relationships.c.subject_id.in_(tracked_ids),
                resource_relationships.c.object_id.in_(tracked_ids),
            ),
        )
    )

    rows_by_family: Dict[Tuple[str, str, str], Iterable[Dict[str, Any]]] = {}
    for family in RELATIONSHIP_FAMILIES:
        field_name, _, _ = family
        field_column = resources.c[field_name]
        query = select(resources.c.id, field_column).where(
            or_(resources.c.id.in_(tracked_ids), field_column.op("&&")(tracked_ids))
        )
        family_rows = await database.fetch_all(query)
        rows_by_family[family] = [dict(row) for row in family_rows]

    relationship_rows = _build_relationship_rows(rows_by_family, tracked_ids)
    if not relationship_rows:
        logger.info(
            "Relationship sync complete for %d resources: no relationship rows to insert.",
            len(tracked_ids),
        )
        return 0

    await database.execute_many(query=resource_relationships.insert(), values=relationship_rows)
    logger.info(
        "Relationship sync complete for %d resources: inserted %d rows.",
        len(tracked_ids),
        len(relationship_rows),
    )
    return len(relationship_rows)


async def sync_relationships_for_batch(resource_rows: Sequence[Dict[str, Any]]) -> int:
    return await sync_relationships_for_resource_ids(
        [row.get("id") for row in resource_rows if row.get("id")]
    )
