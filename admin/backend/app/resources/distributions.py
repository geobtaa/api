"""Reconcile ordered links while retaining the identities of surviving rows."""

from sqlalchemy import delete, tuple_
from sqlalchemy.dialects.postgresql import insert

from app.resources.models import distributions


async def save_links(conn, rid, links):
    key = (distributions.c.distribution_type_id, distributions.c.url)
    targets = [(link["distribution_type_id"], link["url"]) for link in links]
    removed = delete(distributions).where(distributions.c.resource_id == rid)
    if targets:
        removed = removed.where(tuple_(*key).not_in(targets))
    await conn.execute(removed)
    # Staff edits supply no upstream ID. Preserve the stored provenance on update.
    for with_origin in (False, True):
        rows = [
            {**link, "resource_id": rid} for link in links if ("import_id" in link) == with_origin
        ]
        if rows:
            stmt = insert(distributions)
            changes = {"label": stmt.excluded.label, "position": stmt.excluded.position}
            if with_origin:
                changes[distributions.c.import_id] = stmt.excluded.import_id
            await conn.execute(
                stmt.on_conflict_do_update(
                    index_elements=[distributions.c.resource_id, *key], set_=changes
                ),
                rows,
            )
