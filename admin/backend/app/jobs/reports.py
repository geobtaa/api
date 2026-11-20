"""Bounded report serialization and protected artifact byte streaming."""

import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, update

from app.jobs.models import artifact_chunks, artifacts, items

CHUNK_BYTES = 65536


async def write_report(connection, job_id, counts):
    artifact_id = uuid4()
    await connection.execute(
        insert(artifacts).values(
            artifact_id=artifact_id,
            job_id=job_id,
            checksum="0" * 64,
            byte_count=0,
            expires_at=func.clock_timestamp() + timedelta(days=365),
        )
    )
    digest = hashlib.sha256()
    size, position = 0, 0
    buffer = bytearray()

    async def append(data, flush=False):
        nonlocal size, position
        digest.update(data)
        size += len(data)
        buffer.extend(data)
        while len(buffer) >= CHUNK_BYTES or (flush and buffer):
            chunk = bytes(buffer[:CHUNK_BYTES])
            del buffer[:CHUNK_BYTES]
            position += 1
            await connection.execute(
                insert(artifact_chunks).values(
                    artifact_id=artifact_id,
                    position=position,
                    content=chunk,
                )
            )

    def encode(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    await append(
        b'{"job_id":' + encode(str(job_id)) + b',"totals":' + encode(counts) + b',"items":['
    )
    query = (
        select(
            items.c.position,
            items.c.resource_id,
            items.c.resource_version,
            items.c.disposition,
            items.c.details,
        )
        .where(items.c.job_id == job_id)
        .order_by(items.c.position)
    )
    first = True
    async with connection.stream(query.execution_options(yield_per=100)) as result:
        async for row in result.mappings():
            await append((b"" if first else b",") + encode(dict(row)))
            first = False
    await append(b"]}", flush=True)
    await connection.execute(
        update(artifacts)
        .where(artifacts.c.artifact_id == artifact_id)
        .values(
            checksum=digest.hexdigest(),
            byte_count=size,
        )
    )


async def stream_report(engine, actor, job_id, artifact_id):
    from app.jobs.service import readable

    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await readable(connection, actor, job_id, {"jobs:artifacts:read"})
            query = (
                select(artifact_chunks.c.content)
                .where(artifact_chunks.c.artifact_id == artifact_id)
                .order_by(artifact_chunks.c.position)
            )
            async with connection.stream(query.execution_options(yield_per=1)) as result:
                async for content in result.scalars():
                    yield bytes(content)


async def expire(connection):
    expired = select(artifacts.c.artifact_id).where(
        artifacts.c.expires_at <= func.clock_timestamp(), artifacts.c.expired_at.is_(None)
    )
    await connection.execute(
        delete(artifact_chunks).where(artifact_chunks.c.artifact_id.in_(expired))
    )
    return await connection.execute(
        update(artifacts)
        .where(artifacts.c.artifact_id.in_(expired))
        .values(content=None, expired_at=func.clock_timestamp())
    )
