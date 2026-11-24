"""Resolve stable actor identity without coupling callers to a catalog entity."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth import Actor
from app.persistence import actors


async def actor_identity(connection: AsyncConnection, actor: Actor) -> UUID:
    await connection.execute(
        pg_insert(actors)
        .values(
            id=uuid4(), subject_key=actor.actor_id, kind=actor.kind, display_name=actor.display_name
        )
        .on_conflict_do_nothing(index_elements=[actors.c.kind, actors.c.subject_key])
    )
    return await connection.scalar(
        select(actors.c.id).where(
            actors.c.kind == actor.kind, actors.c.subject_key == actor.actor_id
        )
    )
