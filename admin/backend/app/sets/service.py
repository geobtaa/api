"""Set commands commit identity, typed Activity and receipts together."""

import hashlib
import json
from contextlib import nullcontext
from uuid import UUID, uuid4

from sqlalchemy import func, insert, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.activity import activity
from app.auth import Actor
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources.models import resources
from app.sets.models import commands, sets
from app.sets.schemas import SetCreate, SetResponse, SetUpdate
from app.sources.service import get_source

READ = "sets:read"
HISTORY = "set-activity:read"
SOURCE_READ = "sources:read"
SOURCE_USE = "sources:use"
CREATE = "sets:create"
UPDATE = "sets:update"


class SetError(DomainError):
    """Use the shared structured domain-error response."""


def authorize(actor: Actor, *permissions: str):
    # Explicit Set and Source grants; Lifecycle membership is not Set authority.
    if actor.kind != "user" or not {READ, SOURCE_READ, *permissions}.issubset(actor.permissions):
        raise SetError(403, "permission_denied", "Human staff Set permission required")


def serialize(row):
    return SetResponse.model_validate(
        {key: value for key, value in row.items() if key in SetResponse.model_fields}
    )


def visible(actor: Actor):
    return sets.c.set_id.in_(actor.set_ids) if actor.set_ids is not None else true()


def set_query():
    count = (
        select(func.count())
        .select_from(resources)
        .where(resources.c.set_id == sets.c.set_id)
        .correlate(sets)
        .scalar_subquery()
    )
    return select(sets, count.label("resource_count"))


async def get_set(connection, actor, set_id, *, lock=False):
    authorize(actor)
    query = set_query().where(sets.c.set_id == set_id, visible(actor))
    if lock:
        query = query.with_for_update()
    row = (await connection.execute(query)).mappings().first()
    if row is None:
        raise SetError(404, "not_found", "Set not found or inaccessible")
    return serialize(row)


async def list_sets(engine, actor, q, offset, limit, source_id=None, status=None):
    authorize(actor)
    if status == "retired":
        authorize(actor, "sets:retired-read")
    predicate = or_(
        sets.c.title.icontains(q, autoescape=True),
        sets.c.set_id.icontains(q, autoescape=True),
        sets.c.legacy_code.icontains(q, autoescape=True),
    ) & visible(actor)
    predicate &= sets.c.status == status if status else sets.c.status != "retired"
    if source_id is not None:
        predicate = predicate & (sets.c.source_id == source_id)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            total = await connection.scalar(select(func.count()).select_from(sets).where(predicate))
            rows = (
                (
                    await connection.execute(
                        set_query()
                        .where(predicate)
                        .order_by(func.lower(sets.c.title), sets.c.set_id)
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
    """Claim a Set command or replay it after the caller rechecks current access."""
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
            raise SetError(
                409, "idempotency_conflict", "Request key already used for different changes"
            )
        return criteria, response_model.model_validate(receipt["response"])
    return criteria, None


async def write_activity(
    connection,
    actor,
    actor_id,
    set_id,
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
        set_id=set_id,
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
    command: SetCreate | SetUpdate,
    key: UUID,
    software_version: str,
    set_id: str | None = None,
    *,
    connection=None,
):
    authorize(actor, *((CREATE, SOURCE_USE) if set_id is None else (UPDATE,)))
    if set_id is None and actor.set_ids is not None:
        raise SetError(403, "permission_denied", "Creating a Set requires unrestricted Set scope")
    # Excluding the generated ID makes retries of an omitted-ID create replayable.
    payload = command.model_dump(mode="json", exclude_unset=True)
    operation = "create" if set_id is None else f"update:{set_id}"
    # CSV batches supply their outer transaction so all rows and evidence commit together.
    async with engine.begin() if connection is None else nullcontext(connection) as connection:
        previous = None if set_id is None else await get_set(connection, actor, set_id, lock=True)
        if previous is None:
            await get_source(connection, actor, command.source_id)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await command_receipt(
            connection, actor_id, operation, key, payload, SetResponse
        )
        if replay is not None:
            return replay
        if "workflow_catalog_id" in payload:
            from app.workflows.catalog import require_catalog

            await require_catalog(connection, payload["workflow_catalog_id"])
            payload["workflow"] = payload["workflow_catalog_id"] or ""
        elif "workflow" in payload and previous is not None:
            # Raw legacy labels cannot retain an unrelated catalog reference.
            payload["workflow_catalog_id"] = None
        if previous is None:
            set_id = command.set_id
            try:
                create_values = command.model_dump()
                if "workflow_catalog_id" in payload:
                    create_values["workflow"] = payload["workflow"]
                await connection.execute(
                    insert(sets).values(
                        **create_values,
                        created_by_actor_id=actor_id,
                        updated_by_actor_id=actor_id,
                    )
                )
            except IntegrityError as exc:
                if getattr(exc.orig, "sqlstate", None) == "23505":
                    raise SetError(409, "duplicate_set_id", "Set ID already exists") from exc
                raise
        else:
            if previous.status == "retired":
                raise SetError(409, "retired", "Restore this Set before editing")
            values = dict(payload)
            expected = values.pop("lock_version")
            changed = await connection.scalar(
                update(sets)
                .where(sets.c.set_id == set_id, sets.c.lock_version == expected)
                .values(
                    **values,
                    lock_version=sets.c.lock_version + 1,
                    updated_at=func.clock_timestamp(),
                    updated_by_actor_id=actor_id,
                )
                .returning(sets.c.set_id)
            )
            if changed is None:
                raise SetError(409, "stale_version", "Set changed; reload before saving")
        result = await get_set(connection, actor, set_id)
        await write_activity(
            connection,
            actor,
            actor_id,
            set_id,
            key,
            software_version,
            action="set.created" if previous is None else "set.updated",
            details={
                "fields": sorted(set(payload) - {"lock_version", "set_id"}),
                "previous_version": previous.lock_version if previous else None,
                "lock_version": result.lock_version,
            },
        )
        await connection.execute(
            update(commands).where(*criteria).values(response=result.model_dump(mode="json"))
        )
    return result


async def history(engine, actor, set_id, offset, limit):
    authorize(actor, HISTORY)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await get_set(connection, actor, set_id)
            predicate = activity.c.set_id == set_id
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
