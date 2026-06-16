from __future__ import annotations

from typing import Any, Iterable

from app.services.relationship_sync import RELATIONSHIP_FAMILIES

RELATIONSHIP_FIELD_NAMES: tuple[str, ...] = tuple(
    field_name for field_name, _predicate, _inverse_predicate in RELATIONSHIP_FAMILIES
)


def _append_clean_id(resource_ids: list[str], value: Any) -> None:
    cleaned = str(value or "").strip()
    if cleaned:
        resource_ids.append(cleaned)


def _append_values(resource_ids: list[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_clean_id(resource_ids, item)
        return
    _append_clean_id(resource_ids, value)


def resource_ids_for_bridge_records(
    records: Iterable[dict[str, Any]],
    *,
    include_related: bool = False,
) -> list[str]:
    resource_ids: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        _append_clean_id(resource_ids, record.get("id"))
        if include_related:
            for field_name in RELATIONSHIP_FIELD_NAMES:
                _append_values(resource_ids, record.get(field_name))
    return resource_ids
