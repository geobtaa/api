from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import Select, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from db.config import DATABASE_URL
from db.models import distribution_types, resource_distributions

# Use a non-pooling engine to avoid sharing connections with other async DB clients
# (e.g., the `databases` library) which can lead to "another operation is in progress".
engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@dataclass(frozen=True)
class ResourceDistributionRecord:
    """
    Canonical representation of a distribution row joined with its type metadata.

    Using a dataclass keeps consumers decoupled from raw SQLAlchemy rows while providing a
    convenient structure for serialization.
    """

    id: int
    resource_id: str
    distribution_type_id: int
    distribution_type_name: str
    distribution_uri: str
    url: str
    label: Optional[str]
    position: int
    created_at: datetime
    updated_at: datetime
    import_distribution_id: Optional[str]
    distribution_note: Optional[str]
    has_label: bool


async def fetch_resource_distributions(
    resource_id: str, *, session: Optional[AsyncSession] = None
) -> List[ResourceDistributionRecord]:
    """
    Fetch all distribution rows for a single resource.

    Args:
        resource_id: The BTAA resource identifier.
        session: Optional AsyncSession to reuse an existing transaction context.

    Returns:
        List of ResourceDistributionRecord ordered by position then creation timestamp.
    """

    distributions_map = await fetch_distributions_for_resources([resource_id], session=session)
    return distributions_map.get(resource_id, [])


async def fetch_distributions_for_resources(
    resource_ids: Sequence[str], *, session: Optional[AsyncSession] = None
) -> Dict[str, List[ResourceDistributionRecord]]:
    """
    Fetch distributions for many resources in a single query.

    Args:
        resource_ids: Iterable of resource IDs to fetch.
        session: Optional AsyncSession to reuse an existing transaction context.

    Returns:
        Dictionary mapping resource_id to ordered lists of ResourceDistributionRecord.
    """

    if not resource_ids:
        return {}

    stmt = _build_distribution_select().where(
        resource_distributions.c.resource_id.in_(resource_ids)
    )

    owns_session = session is None

    if owns_session:
        async with async_session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(stmt)
                    rows = result.fetchall()
            except Exception:
                # Gracefully degrade to no distributions if DB access fails
                return {}
    else:
        try:
            async with session.begin():
                result = await session.execute(stmt)
                rows = result.fetchall()
        except Exception:
            # Gracefully degrade to no distributions if DB access fails
            return {}

    distribution_map: Dict[str, List[ResourceDistributionRecord]] = {}

    for row in _rows_to_records(rows):
        distribution_map.setdefault(row.resource_id, []).append(row)

    return distribution_map


async def fetch_distribution_context_map(
    resource_ids: Sequence[str], *, session: Optional[AsyncSession] = None
) -> Dict[str, DistributionContext]:
    distributions = await fetch_distributions_for_resources(resource_ids, session=session)
    return {
        resource_id: build_distribution_context(resource_id, records)
        for resource_id, records in distributions.items()
    }


async def fetch_distribution_context(
    resource_id: str, *, session: Optional[AsyncSession] = None
) -> DistributionContext:
    context_map = await fetch_distribution_context_map([resource_id], session=session)
    return context_map.get(resource_id, build_distribution_context(resource_id, []))


@dataclass(frozen=True)
class DistributionContext:
    resource_id: str
    records: List[ResourceDistributionRecord]
    by_uri: Dict[str, List[ResourceDistributionRecord]]
    by_name: Dict[str, List[ResourceDistributionRecord]]
    reference_payload: Dict[str, List[Dict[str, str]]]
    legacy_reference_payload: Dict[str, object]


def build_distribution_context(
    resource_id: str, records: Sequence[ResourceDistributionRecord]
) -> DistributionContext:
    records_list = list(records)
    return DistributionContext(
        resource_id=resource_id,
        records=records_list,
        by_uri=to_uri_map(records_list),
        by_name=to_name_map(records_list),
        reference_payload=to_reference_payload(records_list),
        legacy_reference_payload=to_legacy_reference_payload(records_list),
    )


def to_uri_map(
    distributions: Sequence[ResourceDistributionRecord],
) -> Dict[str, List[ResourceDistributionRecord]]:
    """
    Group distributions by their distribution URI for convenience.

    Consumers that formerly relied on the `dct_references_s` JSON dictionary can inspect
    this structure to find URLs that match specific distribution URIs.
    """

    grouped: Dict[str, List[ResourceDistributionRecord]] = {}
    for record in distributions:
        grouped.setdefault(record.distribution_uri, []).append(record)
    return grouped


def to_name_map(
    distributions: Sequence[ResourceDistributionRecord],
) -> Dict[str, List[ResourceDistributionRecord]]:
    """
    Group distributions by their human-readable distribution type name.

    Useful for UI-centric logic (e.g., “downloads”, “wms”, “iiif_manifest”).
    """

    grouped: Dict[str, List[ResourceDistributionRecord]] = {}
    for record in distributions:
        grouped.setdefault(record.distribution_type_name, []).append(record)
    return grouped


def to_reference_payload(
    distributions: Sequence[ResourceDistributionRecord],
) -> Dict[str, List[Dict[str, str]]]:
    """
    Convert distribution rows into a normalized structure similar to the legacy
    `dct_references_s` payload, but strictly typed.

    Returns:
        Mapping of distribution URI to arrays of dictionaries containing at minimum `url`
        and optionally `label`.
    """

    payload: Dict[str, List[Dict[str, str]]] = {}
    for record in distributions:
        entry = {"url": record.url}
        if record.label:
            entry["label"] = record.label

        payload.setdefault(record.distribution_uri, []).append(entry)

    return payload


def to_legacy_reference_payload(
    distributions: Sequence[ResourceDistributionRecord],
) -> Dict[str, object]:
    """
    Reconstruct legacy-style payloads where single entries collapse to scalars and
    downloads with labels remain dictionaries. This eases the transition for existing
    service logic that expects the historical `dct_references_s` schema.
    """

    grouped: Dict[str, List[object]] = {}

    for record in distributions:
        if record.has_label or record.label:
            entry: object = {"url": record.url}
            if record.label:
                entry["label"] = record.label  # type: ignore[index]
        else:
            entry = record.url

        grouped.setdefault(record.distribution_uri, []).append(entry)

    legacy: Dict[str, object] = {}
    for uri, values in grouped.items():
        if len(values) == 1:
            legacy[uri] = values[0]
        else:
            legacy[uri] = values

    return legacy


def _build_distribution_select() -> Select:
    return (
        select(
            resource_distributions.c.id,
            resource_distributions.c.resource_id,
            resource_distributions.c.distribution_type_id,
            distribution_types.c.name.label("distribution_type_name"),
            distribution_types.c.distribution_uri,
            resource_distributions.c.url,
            resource_distributions.c.label,
            resource_distributions.c.position,
            resource_distributions.c.created_at,
            resource_distributions.c.updated_at,
            resource_distributions.c.import_distribution_id,
            distribution_types.c.note.label("distribution_note"),
            distribution_types.c.label.label("has_label"),
        )
        .select_from(
            resource_distributions.join(
                distribution_types,
                resource_distributions.c.distribution_type_id == distribution_types.c.id,
            )
        )
        .order_by(
            resource_distributions.c.resource_id,
            resource_distributions.c.position,
            resource_distributions.c.created_at,
        )
    )


def _rows_to_records(rows: Iterable[Row]) -> Iterable[ResourceDistributionRecord]:
    for row in rows:
        mapping = row._mapping  # SQLAlchemy RowMapping
        yield ResourceDistributionRecord(
            id=mapping["id"],
            resource_id=mapping["resource_id"],
            distribution_type_id=mapping["distribution_type_id"],
            distribution_type_name=mapping["distribution_type_name"],
            distribution_uri=mapping["distribution_uri"],
            url=mapping["url"],
            label=mapping["label"],
            position=mapping["position"] if mapping["position"] is not None else 0,
            created_at=mapping["created_at"],
            updated_at=mapping["updated_at"],
            import_distribution_id=mapping["import_distribution_id"],
            distribution_note=mapping["distribution_note"],
            has_label=bool(mapping["has_label"]),
        )
