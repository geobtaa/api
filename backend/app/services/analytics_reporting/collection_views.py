"""Rank collections by views of their member resources in sealed monthly catalogs."""

from collections import Counter, defaultdict

from .metadata import content_metadata


def collection_views(documents, title_fallbacks=None):
    return _rank_collections(documents, title_fallbacks)["all"]


def member_collection_views(documents, title_fallbacks=None):
    """Rank views using each month's eligible contribution-stream membership."""
    from .pipeline import CODE_LABELS

    return _rank_collections(documents, title_fallbacks, CODE_LABELS)


def _rank_collections(documents, title_fallbacks, member_labels=None):
    counts = defaultdict(Counter)
    codes = {name: code for code, name in (member_labels or {}).items()}
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
            record = catalog.get(dimensions.get("resource")) or {}
            groups = ["all"]
            if member_labels is not None:
                code = codes.get(record.get("code"))
                if not record.get("eligible", True) or code is None:
                    continue
                groups.append(code)
            metadata = content_metadata(record)
            collections = (metadata.get("attributes") or {}).get("collections") or []
            for identifier in set(collections):
                for group in groups:
                    counts[group][identifier] += row["metrics"]["count"]
    return {
        group: [
            dict(id=identifier, title=titles.get(identifier, identifier), views=views)
            for identifier, views in sorted(
                counts[group].items(), key=lambda item: (-item[1], item[0])
            )
            if views > 0
        ]
        for group in ["all", *(member_labels or {})]
    }
