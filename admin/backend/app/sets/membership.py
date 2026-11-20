"""Explicit representative and current Resource association commands."""

import hashlib
import json
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.activity import activity
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.jobs.models import items, jobs
from app.resources.intake_models import drafts
from app.resources.models import resources
from app.resources.search import resource_visible
from app.sets.models import commands, sets
from app.sets.schemas import SetID
from app.sets.service import get_set, visible


class Reasoned(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value):
        if not value.strip():
            raise ValueError("Reason must be nonblank")
        return value.strip()


class Representative(Reasoned):
    resource_id: str | None = Field(min_length=1, max_length=512)
    lock_version: int = Field(gt=0)


class Association(Reasoned):
    model_config = ConfigDict(extra="forbid")
    source_set_id: SetID | None = Field(
        description="Current managing Set, or null for an unassigned draft"
    )
    target_set_id: SetID
    resource_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    confirmed: bool


class AssociationResponse(BaseModel):
    resource_id: str
    set_id: SetID
    lock_version: int
    source_id: str


async def receipt(connection, actor_id, operation, key, payload):
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    criteria = [
        commands.c.actor_id == actor_id,
        commands.c.operation == operation,
        commands.c.idempotency_key == key,
    ]
    await connection.execute(
        pg_insert(commands)
        .values(actor_id=actor_id, operation=operation, idempotency_key=key, request_hash=digest)
        .on_conflict_do_nothing()
    )
    old = (
        (await connection.execute(select(commands).where(*criteria).with_for_update()))
        .mappings()
        .one()
    )
    if old["request_hash"] != digest:
        raise DomainError(409, "idempotency_conflict", "Command key already used")
    return criteria, old["response"]


def has_permission(actor, permission):
    return actor.kind == "user" and {
        permission,
        "resources:read",
        "sets:read",
        "sources:read",
    }.issubset(actor.permissions)


def authorize(actor, permission):
    if not has_permission(actor, permission):
        raise DomainError(403, "permission_denied", "Permission denied")


async def representative(engine, actor, set_id, command, key, software_version):
    authorize(actor, "sets:update")
    async with engine.begin() as connection:
        row = (
            (
                await connection.execute(
                    select(sets).where(sets.c.set_id == set_id, visible(actor)).with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(404, "not_found", "Set not found")
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await receipt(
            connection,
            actor_id,
            f"representative:{set_id}",
            key,
            command.model_dump(mode="json"),
        )
        if replay is not None:
            return replay
        if row["status"] == "retired" or row["lock_version"] != command.lock_version:
            raise DomainError(409, "stale_version", "Set changed or retired. Reload before editing")
        if command.resource_id is not None:
            resource = await connection.scalar(
                select(resources.c.id)
                .join(sets, sets.c.set_id == resources.c.set_id)
                .where(resources.c.id == command.resource_id, visible(actor))
                .with_for_update(read=True, of=resources)
            )
            if resource is None:
                raise DomainError(
                    422, "invalid_representative", "Choose an accessible managed Resource"
                )
        if command.resource_id == row["represented_by_id"]:
            raise DomainError(422, "no_changes", "Representative is unchanged")
        await connection.execute(
            update(sets)
            .where(sets.c.set_id == set_id)
            .values(
                represented_by_id=command.resource_id,
                lock_version=sets.c.lock_version + 1,
                updated_at=func.clock_timestamp(),
                updated_by_actor_id=actor_id,
            )
        )
        await connection.execute(
            insert(activity).values(
                id=uuid4(),
                set_id=set_id,
                actor_id=actor_id,
                actor_display_name=actor.display_name,
                action="set.representative_changed",
                software_version=software_version,
                correlation_id=uuid4(),
                idempotency_key=key,
                reason=command.reason,
                resource_id=command.resource_id,
                details={
                    "previous_resource_id": row["represented_by_id"],
                    "resource_id": command.resource_id,
                },
            )
        )
        result = (await get_set(connection, actor, set_id)).model_dump(
            mode="json", exclude_computed_fields=True
        )
        await connection.execute(update(commands).where(*criteria).values(response=result))
        return result


async def complete_intake_assignments(connection, identifiers):
    """Remove assigned catalog drafts from the queue using their original import receipts."""
    await connection.execute(
        update(drafts)
        .where(drafts.c.catalog_id.in_(identifiers), drafts.c.assigned_import.is_(None))
        .values(
            assigned_import=select(resources.c.import_id.cast(drafts.c.assigned_import.type))
            .where(resources.c.id == drafts.c.catalog_id)
            .scalar_subquery()
        )
    )


async def associate(engine, actor, resource_id, command, key, software_version):
    authorize(actor, "resources:associate")
    if not command.confirmed or not command.reason.strip():
        raise DomainError(
            422, "confirmation_required", "Review the association and supply a reason"
        )
    required_ids = {command.target_set_id}
    if command.source_set_id is not None:
        required_ids.add(command.source_set_id)
    async with engine.begin() as connection:
        roots = (
            (
                await connection.execute(
                    select(sets)
                    .where(sets.c.set_id.in_(required_ids), visible(actor))
                    .order_by(sets.c.set_id)
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        if len(roots) != len(required_ids):
            raise DomainError(404, "not_found", "Set not found")
        row = (
            (
                await connection.execute(
                    select(resources)
                    .outerjoin(sets, sets.c.set_id == resources.c.set_id)
                    .where(resources.c.id == resource_id, resource_visible(actor))
                    .with_for_update(of=resources)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(404, "not_found", "Resource not found")
        actor_id = await actor_identity(connection, actor)
        # Replays also require access to the original unassigned draft.
        if (
            command.source_set_id is None
            and row["created_by_actor_id"] != actor_id
            and "resources:intake-manage" not in actor.permissions
        ):
            raise DomainError(404, "not_found", "Resource not found")
        criteria, replay = await receipt(
            connection, actor_id, f"association:{resource_id}", key, command.model_dump(mode="json")
        )
        if replay is not None:
            return replay
        if (
            row["lock_version"] != command.resource_version
            or row["set_id"] != command.source_set_id
        ):
            raise DomainError(409, "stale_version", "Resource association changed. Preview again")
        if command.source_set_id == command.target_set_id:
            raise DomainError(422, "no_changes", "Resource already belongs to this Set")
        if command.source_set_id is None and row["publication_state"] != "draft":
            raise DomainError(
                409, "read_only", "Only an unassigned draft can receive its first Set"
            )
        if any(root["status"] == "retired" for root in roots):
            raise DomainError(409, "retired", "Restore retired Sets before reassignment")
        conflicting = await connection.scalar(
            select(func.count())
            .select_from(items.join(jobs))
            .where(items.c.resource_id == resource_id, jobs.c.state.in_(["queued", "running"]))
        )
        if conflicting:
            raise DomainError(
                409, "active_jobs", "Finish or cancel active work before reassignment"
            )
        await connection.execute(
            update(resources)
            .where(resources.c.id == resource_id)
            .values(
                set_id=command.target_set_id,
                lock_version=resources.c.lock_version + 1,
                updated_at=func.clock_timestamp(),
            )
        )
        if command.source_set_id is None and row["import_id"] is not None:
            await complete_intake_assignments(connection, [resource_id])
        sources = {root["set_id"]: root["source_id"] for root in roots}
        correlation_id = uuid4()
        result = {
            "resource_id": resource_id,
            "set_id": str(command.target_set_id),
            "source_id": sources[command.target_set_id],
            "lock_version": command.resource_version + 1,
        }
        for set_id in required_ids:
            await connection.execute(
                insert(activity).values(
                    id=uuid4(),
                    set_id=set_id,
                    actor_id=actor_id,
                    actor_display_name=actor.display_name,
                    action="resource.associated",
                    software_version=software_version,
                    correlation_id=correlation_id,
                    idempotency_key=key,
                    reason=command.reason,
                    resource_id=resource_id,
                    details={
                        "source_set_id": command.source_set_id,
                        "target_set_id": str(command.target_set_id),
                        "previous_source_id": sources.get(command.source_set_id),
                        **result,
                    },
                )
            )
        await connection.execute(update(commands).where(*criteria).values(response=result))
        return result
