"""PostgreSQL-native CSV formatting with bounded network backpressure."""

import asyncio
from contextlib import suppress

from sqlalchemy import ARRAY, Boolean, Text, case, cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from app.resources import csv_format, search
from app.resources.models import distributions, resources
from app.sets.models import sets


def query(actor, names, q, set_id, filters, ids):
    link = func.jsonb_build_object(
        "distribution_type_id",
        distributions.c.distribution_type_id,
        "url",
        distributions.c.url,
        "label",
        distributions.c.label,
    )
    links = (
        select(
            func.jsonb_agg(aggregate_order_by(link, distributions.c.position, distributions.c.id))
        )
        .where(distributions.c.resource_id == resources.c.id)
        .correlate(resources)
        .scalar_subquery()
    )
    columns = []
    friendly = "ID" in names
    for label in names:
        name = csv_format.field_name(label)
        if name == "_csv_encoding":
            value = literal("geomg-v1" if friendly else "apostrophe-v1")
        elif name == "distributions":
            value = func.coalesce(cast(links, Text), "[]")
        else:
            column = sets.c.source_id if name == "source_id" else resources.c[name]
            if friendly and isinstance(column.type, ARRAY):
                joined = func.array_to_string(column, "|")
                # JSON is a lossless fallback for values ambiguous in v1's pipe notation.
                flattened = func.array_to_string(column, "")
                value = case(
                    (
                        or_(
                            func.cardinality(column) == 0,
                            flattened.contains("|", autoescape=True),
                            joined.startswith("[", autoescape=True),
                            joined.op("~")(r"(^|\|)\s*(\||$)"),
                        ),
                        cast(func.to_jsonb(column), Text),
                    ),
                    else_=joined,
                )
                value = safe_text(value)
            elif isinstance(column.type, (ARRAY, Boolean)):
                value = cast(func.to_jsonb(column), Text)
            else:
                value = safe_text(cast(column, Text))
        columns.append(value.label(label))
    return (
        select(*columns)
        .join_from(resources, sets, resources.c.set_id == sets.c.set_id, isouter=True)
        .where(search.predicate(actor, q, set_id, filters, ids))
        .order_by(resources.c.id)
    )


def safe_text(value):
    return case(
        (
            func.left(value, 1).in_(["=", "+", "-", "@", "\t", "\r", "\n", "'"]),
            literal("'") + value,
        ),
        else_=value,
    )


async def stream(engine, statement):
    queue = asyncio.Queue(maxsize=8)

    async def produce():
        try:
            async with engine.connect() as connection:
                compiled = statement.compile(
                    dialect=connection.dialect, compile_kwargs={"render_postcompile": True}
                )
                arguments = [compiled.params[name] for name in compiled.positiontup]
                raw = await connection.get_raw_connection()
                # The adapter owns connection lifetime; COPY itself is a single snapshot.
                try:
                    await raw.driver_connection.copy_from_query(
                        str(compiled),
                        *arguments,
                        output=queue.put,
                        format="csv",
                        header=True,
                        encoding="UTF8",
                    )
                except asyncio.CancelledError:
                    # A cancelled COPY can leave asyncpg mid-protocol. Never pool it.
                    await connection.invalidate()
                    raise

        except Exception as exc:
            await queue.put(exc)
        await queue.put(None)

    task = asyncio.create_task(produce())
    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                raise chunk
            yield bytes(chunk)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
