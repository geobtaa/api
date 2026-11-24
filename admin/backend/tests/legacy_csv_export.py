"""Frozen pre-COPY implementation for the export performance regression."""

import json

from sqlalchemy import or_, select

from app.csv_exchange import csv_line, safe_cell
from app.resources.csv_io import columns
from app.resources.models import distributions, resources
from app.sets.models import sets
from app.sets.service import visible


async def legacy_export(engine, actor, q="", set_id=None, ids=None):
    """Yield bounded chunks under a consistent, server-side PostgreSQL snapshot."""
    names = columns(actor)
    yield csv_line(names)
    predicate = visible(actor)
    if q:
        predicate &= or_(
            resources.c.id.icontains(q, autoescape=True),
            resources.c.dct_title_s.icontains(q, autoescape=True),
        )
    if set_id:
        predicate &= resources.c.set_id == set_id
    if ids:
        predicate &= resources.c.id.in_(ids)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            cursor = await connection.stream(
                select(resources, sets.c.source_id)
                .join(sets, resources.c.set_id == sets.c.set_id)
                .where(predicate)
                .order_by(resources.c.id)
            )
            async for chunk in cursor.mappings().partitions(100):
                links = (
                    (
                        await connection.execute(
                            select(distributions)
                            .where(distributions.c.resource_id.in_([r["id"] for r in chunk]))
                            .order_by(distributions.c.position, distributions.c.id)
                        )
                    )
                    .mappings()
                    .all()
                )
                for row in chunk:
                    values = {name: row.get(name) for name in names}
                    values["_csv_encoding"] = "apostrophe-v1"
                    values["distributions"] = [
                        {name: link[name] for name in ["distribution_type_id", "url", "label"]}
                        for link in links
                        if link["resource_id"] == row["id"]
                    ]
                    yield csv_line(
                        [
                            ""
                            if values[name] is None
                            else json.dumps(values[name], ensure_ascii=False)
                            if isinstance(values[name], (list, bool))
                            else safe_cell(str(values[name]))
                            for name in names
                        ]
                    )
