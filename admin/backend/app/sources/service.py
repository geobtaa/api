"""Source commands commit identity, typed Activity and receipts together."""

import hashlib
import json
from contextlib import nullcontext
from uuid import UUID, uuid4

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.activity import activity
from app.auth import Actor
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.sources.models import commands, sources
from app.sources.schemas import SourceCreate, SourceResponse, SourceUpdate

READ = "sources:read"
CREATE = "sources:create"
UPDATE = "sources:update"


class SourceError(DomainError):
    """Use the shared structured domain-error response."""


def authorize(actor: Actor, *permissions: str):
    # Explicit global Source grants; Lifecycle grants neither confer nor limit them.
    if actor.kind != "user" or not {READ, *permissions}.issubset(actor.permissions):
        raise SourceError(403, "permission_denied", "Human staff Source permission required")


def serialize(row):
    return SourceResponse.model_validate(
        {key: value for key, value in row.items() if key in SourceResponse.model_fields}
    )


async def get_source(connection, actor, source_id, *, lock=False):
    authorize(actor)
    query = select(sources).where(sources.c.source_id == source_id)
    if lock:
        query = query.with_for_update()
    row = (await connection.execute(query)).mappings().first()
    if row is None:
        raise SourceError(404, "not_found", "Source not found")
    return serialize(row)


async def list_sources(engine, actor, q, offset, limit):
    authorize(actor)
    predicate = or_(
        sources.c.title.icontains(q, autoescape=True),
        sources.c.source_id.icontains(q, autoescape=True),
        sources.c.legacy_code.icontains(q, autoescape=True),
    )
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            total = await connection.scalar(
                select(func.count()).select_from(sources).where(predicate)
            )
            rows = (
                (
                    await connection.execute(
                        select(sources)
                        .where(predicate)
                        .order_by(func.lower(sources.c.title), sources.c.source_id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
    return {
        "items": [serialize(row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


async def command_receipt(connection, actor_id, operation, key, payload, response_model):
    """Claim a Source command or replay it after the caller rechecks current access."""
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    criteria = (
        commands.c.actor_id == actor_id,
        commands.c.operation == operation,
        commands.c.idempotency_key == key,
    )
    inserted = await connection.scalar(
        pg_insert(commands)
        .values(actor_id=actor_id, operation=operation, idempotency_key=key, request_hash=digest)
        .on_conflict_do_nothing()
        .returning(commands.c.idempotency_key)
    )
    if inserted is None:
        receipt = (await connection.execute(select(commands).where(*criteria))).mappings().one()
        if receipt["request_hash"] != digest:
            raise SourceError(
                409, "idempotency_conflict", "Request key already used for different changes"
            )
        return criteria, response_model.model_validate(receipt["response"])
    return criteria, None


async def write_activity(
    connection,
    actor,
    actor_id,
    source_id,
    key,
    software_version,
    *,
    action,
    details,
    outcome="succeeded",
    occurred_at=None,
    reason=None,
    origin="geomg-admin",
):
    """Append typed evidence inside the caller's transaction; never commit independently."""
    values = dict(
        id=uuid4(),
        source_id=source_id,
        actor_id=actor_id,
        actor_display_name=actor.display_name,
        action=action,
        outcome=outcome,
        software_version=software_version,
        correlation_id=uuid4(),
        idempotency_key=key,
        details=details,
        recorded_at=func.clock_timestamp(),
        reason=reason,
        origin=origin,
    )
    if occurred_at is not None:
        values["occurred_at"] = occurred_at
    return (
        (await connection.execute(insert(activity).values(**values).returning(activity)))
        .mappings()
        .one()
    )


async def mutate(
    engine,
    actor,
    command: SourceCreate | SourceUpdate,
    key: UUID,
    software_version: str,
    source_id: str | None = None,
    *,
    connection=None,
):
    authorize(actor, CREATE if source_id is None else UPDATE)
    # Excluding the generated ID makes retries of an omitted-ID create replayable.
    payload = command.model_dump(mode="json", exclude_unset=True)
    operation = "create" if source_id is None else f"update:{source_id}"
    # CSV batches supply their outer transaction so all rows and evidence commit together.
    async with engine.begin() if connection is None else nullcontext(connection) as connection:
        previous = (
            None if source_id is None else await get_source(connection, actor, source_id, lock=True)
        )
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await command_receipt(
            connection, actor_id, operation, key, payload, SourceResponse
        )
        if replay is not None:
            return replay
        if previous is None:
            source_id = command.source_id
            try:
                await connection.execute(
                    insert(sources).values(
                        **command.model_dump(),
                        created_by_actor_id=actor_id,
                        updated_by_actor_id=actor_id,
                    )
                )
            except IntegrityError as exc:
                if getattr(exc.orig, "sqlstate", None) == "23505":
                    raise SourceError(
                        409, "duplicate_source_id", "Source ID already exists"
                    ) from exc
                raise
        else:
            values = dict(payload)
            expected = values.pop("lock_version")
            changed = await connection.scalar(
                update(sources)
                .where(sources.c.source_id == source_id, sources.c.lock_version == expected)
                .values(
                    **values,
                    lock_version=sources.c.lock_version + 1,
                    updated_at=func.clock_timestamp(),
                    updated_by_actor_id=actor_id,
                )
                .returning(sources.c.source_id)
            )
            if changed is None:
                raise SourceError(409, "stale_version", "Source changed; reload before saving")
        result = await get_source(connection, actor, source_id)
        await write_activity(
            connection,
            actor,
            actor_id,
            source_id,
            key,
            software_version,
            action="source.created" if previous is None else "source.updated",
            details={
                "fields": sorted(set(payload) - {"lock_version", "source_id"}),
                "previous_version": previous.lock_version if previous else None,
                "lock_version": result.lock_version,
            },
        )
        await connection.execute(
            update(commands).where(*criteria).values(response=result.model_dump(mode="json"))
        )
    return result
