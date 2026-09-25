"""Rebuild collection-filter rankings from complete preserved daily dimensions."""

import re
from collections import Counter

COLLECTION_CONTROL = re.compile(
    r"^(?:include_filters|exclude_filters|f|fq)\[(pcdm_memberOf_sm|dct_isPartOf_sm|b1g_localCollectionLabel_sm)\](?:\[\])?$"
)


def collection_searches(documents):
    """Count a search once per collection, including legacy and exclusion controls."""
    counts = Counter()
    titles = {}
    months = set()
    for document in sorted(documents, key=lambda item: item["month"]):
        month = document["month"]
        if month in months:
            raise ValueError(f"Duplicate month: {month}")
        months.add(month)
        for identifier, record in document.get("catalog", {}).items():
            titles[identifier] = record.get("title") or identifier
        for row in document["daily"]:
            dimensions = row["dimensions"]
            if dimensions["source"] != "analytics_searches":
                continue
            used = set()
            for control, values in dimensions.get("context", {}).items():
                match = COLLECTION_CONTROL.fullmatch(control)
                if not match:
                    continue
                kind = "local" if match[1] == "b1g_localCollectionLabel_sm" else "record"
                for value in values if isinstance(values, list) else [values]:
                    if isinstance(value, str) and value.strip():
                        used.add((kind, value))
            for key in used:
                counts[key] += row["metrics"]["count"]
    rows = []
    for (kind, value), count in counts.items():
        row = {
            "title": titles.get(value, value) if kind == "record" else value,
            "searches": count,
            "kind": "Collection record" if kind == "record" else "Local collection",
        }
        if kind == "record":
            row["id"] = value
        else:
            row["filterField"] = "b1g_localCollectionLabel_sm"
        rows.append(row)
    return sorted(rows, key=lambda row: (-row["searches"], row.get("id", row["title"])))
