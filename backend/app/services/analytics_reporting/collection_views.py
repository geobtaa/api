"""Rank collections by views of their member resources in sealed monthly catalogs."""

from collections import Counter

from .metadata import content_metadata


def collection_views(documents, title_fallbacks=None):
    counts = Counter()
    titles = dict(title_fallbacks or {})
    months = set()
    for document in sorted(documents, key=lambda item: item["month"]):
        if document["month"] in months:
            raise ValueError(f"Duplicate month: {document['month']}")
        months.add(document["month"])
        catalog = document.get("catalog") or {}
        for identifier, record in catalog.items():
            title = content_metadata(record).get("title")
            if title and title.strip() and title != identifier:
                titles[identifier] = title
        for row in document["daily"]:
            dimensions = row["dimensions"]
            if (
                dimensions["source"] != "analytics_events"
                or dimensions.get("event") != "resource_view"
            ):
                continue
            metadata = content_metadata(catalog.get(dimensions.get("resource")) or {})
            collections = (metadata.get("attributes") or {}).get("collections") or []
            for identifier in set(collections):
                counts[identifier] += row["metrics"]["count"]
    return [
        dict(id=identifier, title=titles.get(identifier, identifier), views=views)
        for identifier, views in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if views > 0
    ]
