from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class FilterSet:
    include: dict[str, list[str]]
    exclude: dict[str, list[str]]


def parse_filter_values(values: list[str] | None) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = defaultdict(list)
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"Invalid filter '{raw}'. Use FIELD=VALUE.")
        field, raw_value = raw.split("=", 1)
        field = field.strip()
        if not field or not raw_value.strip():
            raise ValueError(f"Invalid filter '{raw}'. Use FIELD=VALUE.")
        for value in raw_value.split(","):
            clean = value.strip()
            if clean:
                parsed[field].append(clean)
    return dict(parsed)


def parse_filters(include: list[str] | None, exclude: list[str] | None) -> FilterSet:
    return FilterSet(include=parse_filter_values(include), exclude=parse_filter_values(exclude))


def apply_filter_params(params: dict[str, object], filters: FilterSet) -> dict[str, object]:
    serialized = dict(params)
    for prefix, filter_map in (
        ("include_filters", filters.include),
        ("exclude_filters", filters.exclude),
    ):
        for field, values in filter_map.items():
            serialized[f"{prefix}[{field}][]"] = values
    return serialized
