from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from app.services.distribution_repository import DistributionContext, build_distribution_context
from app.services.distribution_repository import ResourceDistributionRecord as _Record

_DEFAULT_TIMESTAMP = datetime.now(timezone.utc)


def make_distribution_record(
    resource_id: str,
    distribution_uri: str,
    url: str,
    *,
    label: Optional[str] = None,
    distribution_type_id: int = 1,
    distribution_type_name: Optional[str] = None,
    position: int = 0,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
) -> _Record:
    """Create a ResourceDistributionRecord for tests."""

    timestamp = created_at or _DEFAULT_TIMESTAMP
    updated = updated_at or timestamp

    return _Record(
        id=distribution_type_id * 1000 + position,
        resource_id=resource_id,
        distribution_type_id=distribution_type_id,
        distribution_type_name=distribution_type_name or distribution_uri,
        distribution_uri=distribution_uri,
        url=url,
        label=label,
        position=position,
        created_at=timestamp,
        updated_at=updated,
        import_distribution_id=None,
        distribution_note=None,
        has_label=bool(label),
    )


def make_distribution_context(resource_id: str, records: Iterable[_Record]) -> DistributionContext:
    """Create a DistributionContext populated with the provided records."""
    return build_distribution_context(resource_id, list(records))
