"""Resolve direct, public collection titles without changing source metadata."""

from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import or_, select

from db.database import database
from db.models import resources

RELATION_FIELDS = ("pcdm_memberOf_sm", "dct_isPartOf_sm")


def parent_ids(row: dict) -> set[str]:
    result = set()
    for field in RELATION_FIELDS:
        values = row.get(field) or []
        if isinstance(values, str):
            values = [values]
        result.update(str(value).strip() for value in values if value and str(value).strip())
    result.discard(str(row.get("id", "")))
    return result


async def collection_titles_for_rows(rows: Iterable[dict]) -> dict[str, list[str]]:
    rows = list(rows)
    ids = sorted(set().union(*(parent_ids(row) for row in rows))) if rows else []
    parents = {}
    for offset in range(0, len(ids), 1000):
        found = await database.fetch_all(
            select(
                resources.c.id,
                resources.c.dct_title_s,
                resources.c.gbl_resourceClass_sm,
                resources.c.publication_state,
                resources.c.gbl_suppressed_b,
            ).where(resources.c.id.in_(ids[offset : offset + 1000]))
        )
        for record in found:
            parent = dict(record)
            if (
                parent.get("publication_state") == "published"
                and not parent.get("gbl_suppressed_b")
                and "Collections" in (parent.get("gbl_resourceClass_sm") or [])
                and (parent.get("dct_title_s") or "").strip()
            ):
                parents[str(parent["id"])] = parent["dct_title_s"].strip()
    return {
        str(row["id"]): sorted({parents[pid] for pid in parent_ids(row) if pid in parents})
        for row in rows
    }


async def direct_member_ids(changed_ids: list[str]) -> list[str]:
    """Works after parent deletion; does not depend on derived relationship rows."""
    result = set()
    for offset in range(0, len(changed_ids), 1000):
        batch = changed_ids[offset : offset + 1000]
        found = await database.fetch_all(
            select(resources.c.id).where(
                or_(*(resources.c[field].op("&&")(batch) for field in RELATION_FIELDS))
            )
        )
        result.update(str(row["id"]) for row in found)
    return sorted(result - set(changed_ids))


async def advance_search_revision(es, index: str, *, ready: bool = False) -> None:
    """Invalidate generation-keyed caches after refreshed writes."""
    response = await es.indices.get_mapping(index=index)
    entries = response.body if hasattr(response, "body") else response
    for name, entry in entries.items():
        meta = dict(entry.get("mappings", {}).get("_meta", {}))
        meta["search_revision"] = uuid4().hex
        if ready:
            meta.update(search_relevance="v2", search_relevance_ready=True)
        await es.indices.put_mapping(index=name, body={"_meta": meta})
