"""Set-based selection snapshots, shared search predicates and current scope checks."""

import hashlib
import json
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain import DomainError
from app.identity.actors import actor_identity
from app.persistence import actors
from app.resources.editor import can_bulk_edit
from app.resources.models import resources
from app.resources.search import parse_filters, predicate, resource_visible
from app.resources.selection_models import selection_items, selections
from app.sets.models import sets
from app.sets.schemas import SetID
from app.sets.service import visible


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(default="", max_length=200)
    set_id: SetID | None = None
    filters: dict = Field(default_factory=dict)
    ids: list[str] | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def bounded_query(self):
        if len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False).encode()) > 1_000_000:
            raise ValueError("Selection query configuration must be at most 1 MB")
        return self


def require_reader(actor):
    if actor.kind != "user" or "resources:read" not in actor.permissions:
        raise DomainError(403, "permission_denied", "Permission denied")


async def readable(connection, actor, selection_id):
    require_reader(actor)
    actor_id = await connection.scalar(
        select(actors.c.id).where(
            actors.c.kind == actor.kind, actors.c.subject_key == actor.actor_id
        )
    )
    selection = (
        (
            await connection.execute(
                select(selections).where(
                    selections.c.selection_id == selection_id, selections.c.actor_id == actor_id
                )
            )
        )
        .mappings()
        .first()
    )
    if selection is None:
        raise DomainError(404, "not_found", "Selection not found")
    # Original scope is protected even after a Resource moves; current scope is also checked.
    accessible_sets = select(sets.c.set_id).where(visible(actor))
    outside_original_scope = selection_items.c.set_id.is_not(
        None
    ) & selection_items.c.set_id.not_in(accessible_sets)
    if "resources:intake-manage" not in actor.permissions:
        owned = select(resources.c.id).where(resources.c.created_by_actor_id == actor_id)
        outside_original_scope |= selection_items.c.set_id.is_(
            None
        ) & selection_items.c.resource_id.not_in(owned)
    inaccessible = await connection.scalar(
        select(func.count())
        .select_from(selection_items)
        .where(
            selection_items.c.selection_id == selection_id,
            outside_original_scope,
        )
    )
    current = (
        select(resources.c.id)
        .outerjoin(sets, sets.c.set_id == resources.c.set_id)
        .where(resource_visible(actor), resources.c.id == selection_items.c.resource_id)
        .correlate(selection_items)
        .exists()
    )
    inaccessible += await connection.scalar(
        select(func.count())
        .select_from(selection_items)
        .where(selection_items.c.selection_id == selection_id, ~current)
    )
    if inaccessible:
        raise DomainError(404, "not_found", "Selection unavailable under current access")
    return selection


async def summary(connection, selection_id):
    count = await connection.scalar(
        select(func.count())
        .select_from(selection_items)
        .where(selection_items.c.selection_id == selection_id)
    )
    return {"selection_id": selection_id, "total": count}


async def create(engine, actor, command, key):
    require_reader(actor)
    filters = parse_filters(command.filters)
    payload = command.model_dump(mode="json")
    payload["filters"] = filters
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    async with engine.begin() as connection:
        actor_id = await actor_identity(connection, actor)
        selection_id = uuid4()
        created = await connection.scalar(
            pg_insert(selections)
            .values(
                selection_id=selection_id,
                actor_id=actor_id,
                idempotency_key=key,
                request_hash=digest,
                query=payload,
            )
            .on_conflict_do_nothing()
            .returning(selections.c.selection_id)
        )
        row = (
            (
                await connection.execute(
                    select(selections).where(
                        selections.c.actor_id == actor_id, selections.c.idempotency_key == key
                    )
                )
            )
            .mappings()
            .one()
        )
        if row["request_hash"] != digest:
            raise DomainError(409, "idempotency_conflict", "Selection key already used")
        selection_id = row["selection_id"]
        if created:
            query = (
                select(
                    literal(selection_id),
                    resources.c.id,
                    resources.c.set_id,
                    resources.c.lock_version,
                )
                .outerjoin(sets, sets.c.set_id == resources.c.set_id)
                .where(predicate(actor, command.q.strip(), command.set_id, filters, command.ids))
            )
            await connection.execute(
                insert(selection_items).from_select(
                    ["selection_id", "resource_id", "set_id", "resource_version"], query
                )
            )
            await connection.execute(
                update(selections)
                .where(selections.c.selection_id == selection_id)
                .values(sealed=True)
            )
            result = await summary(connection, selection_id)
            if command.ids is not None and result["total"] != len(set(command.ids)):
                raise DomainError(404, "not_found", "Selected Resource not found in these results")
        else:
            await readable(connection, actor, selection_id)
            result = await summary(connection, selection_id)
        return result


class SelectionSummary(BaseModel):
    selection_id: UUID
    total: int


class SelectionItem(BaseModel):
    resource_id: str
    set_id: SetID | None
    resource_version: int
    current_version: int


class SelectionPage(BaseModel):
    can_bulk_edit: bool = False
    validation_set_id: SetID | None = None
    items: list[SelectionItem]
    total: int
    offset: int
    limit: int


async def page(engine, actor, selection_id, offset, limit):
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await readable(connection, actor, selection_id)
            result = await summary(connection, selection_id)
            rows = (
                (
                    await connection.execute(
                        select(selection_items, resources.c.lock_version.label("current_version"))
                        .join(resources, resources.c.id == selection_items.c.resource_id)
                        .where(selection_items.c.selection_id == selection_id)
                        .order_by(selection_items.c.resource_id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            from app.jobs.service import REQUIRED

            scopes = (
                (
                    await connection.execute(
                        select(selection_items.c.set_id)
                        .where(selection_items.c.selection_id == selection_id)
                        .distinct()
                        .limit(2)
                    )
                )
                .scalars()
                .all()
            )
            validation_scope = (
                scopes[0] if len(scopes) == 1 and REQUIRED.issubset(actor.permissions) else None
            )
            return {
                "items": rows,
                "total": result["total"],
                "offset": offset,
                "limit": limit,
                "validation_set_id": validation_scope,
                "can_bulk_edit": can_bulk_edit(actor),
            }
