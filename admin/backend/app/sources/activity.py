"""Protected Source history and staff-reported work, independent of Lifecycle."""

from sqlalchemy import func, select, update

from app.activity import activity
from app.identity.actors import actor_identity
from app.sources import service
from app.sources.models import commands
from app.sources.schemas import SourceActivityResponse

READ = "source-activity:read"
CREATE = "source-activity:create"


async def history(engine, actor, source_id, offset, limit):
    service.authorize(actor, READ)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await service.get_source(connection, actor, source_id)
            predicate = activity.c.source_id == source_id
            total = await connection.scalar(
                select(func.count()).select_from(activity).where(predicate)
            )
            rows = (
                (
                    await connection.execute(
                        select(activity)
                        .where(predicate)
                        .order_by(activity.c.occurred_at.desc(), activity.c.id.desc())
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
    return {"items": rows, "total": total, "offset": offset, "limit": limit}


async def record(engine, actor, source_id, command, key, software_version):
    service.authorize(actor, CREATE)
    async with engine.begin() as connection:
        source = await service.get_source(connection, actor, source_id, lock=True)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await service.command_receipt(
            connection,
            actor_id,
            f"activity:{source_id}",
            key,
            command.model_dump(mode="json"),
            SourceActivityResponse,
        )
        if replay is not None:
            return replay
        now = await connection.scalar(select(func.clock_timestamp()))
        if command.occurred_at is not None and command.occurred_at > now:
            raise service.SourceError(422, "future_activity", "Activity cannot occur in the future")
        row = await service.write_activity(
            connection,
            actor,
            actor_id,
            source_id,
            key,
            software_version,
            action=command.action,
            outcome=command.outcome,
            occurred_at=command.occurred_at or now,
            reason=command.reason,
            origin="geomg-staff",
            details={"source_version": source.lock_version, "recording": "staff_reported"},
        )
        result = SourceActivityResponse.model_validate(row)
        await connection.execute(
            update(commands).where(*criteria).values(response=result.model_dump(mode="json"))
        )
    return result
