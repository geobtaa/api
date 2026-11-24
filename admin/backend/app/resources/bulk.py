"""Scoped, preview-first metadata replacements with append-only reversal evidence."""

from collections import defaultdict
from uuid import uuid4, uuid5

from sqlalchemy import bindparam, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.activity import activity
from app.domain import DomainError
from app.jobs.models import items as job_items
from app.jobs.models import jobs
from app.persistence import actors
from app.resources import editor, selections
from app.resources.bulk_models import actions, executions, items, results
from app.resources.models import resources
from app.resources.schemas import ResourceUpdate
from app.resources.search import resource_visible
from app.resources.selection_models import selection_items
from app.resources.service import digest
from app.sets.models import sets

CHUNK = 250


def authorize(actor):
    if not editor.can_bulk_edit(actor):
        raise DomainError(403, "permission_denied", "Staff bulk edit permission is required")


def summary_query():
    return select(
        actions, executions.c.applied_at, executions.c.actor_name.label("applied_by")
    ).outerjoin(executions, executions.c.action_id == actions.c.id)


async def accessible(conn, actor, action_id, *, lock=False):
    query = summary_query().where(actions.c.id == action_id)
    if lock:
        query = query.with_for_update(of=actions)
    action = (await conn.execute(query)).mappings().first()
    if action is None:
        raise DomainError(404, "not_found", "Bulk action unavailable")
    await selections.readable(conn, actor, action["selection_id"])
    return action


def members(selection_id):
    return select(
        selection_items.c.resource_id,
        selection_items.c.set_id,
        selection_items.c.resource_version.label("expected"),
    ).where(selection_items.c.selection_id == selection_id)


def reversible_members(action_id):
    return (
        select(
            items.c.resource_id,
            items.c.set_id,
            results.c.after_version.label("expected"),
            items.c.changes,
        )
        .join(results)
        .where(items.c.action_id == action_id, results.c.status == "changed")
    )


def current_rows(source, actor, columns=(), *, lock=False):
    active_job = (
        select(job_items.c.resource_id)
        .join(jobs)
        .where(job_items.c.resource_id == resources.c.id, jobs.c.state.in_(["queued", "running"]))
        .exists()
    )
    query = (
        select(
            *source.c,
            resources.c.set_id.label("current_set"),
            resources.c.lock_version,
            resources.c.publication_state,
            sets.c.status.label("set_status"),
            active_job.label("active_job"),
            resource_visible(actor).label("can_read"),
            *(resources.c[name] for name in columns),
        )
        .select_from(
            source.join(resources, resources.c.id == source.c.resource_id).outerjoin(
                sets, sets.c.set_id == resources.c.set_id
            )
        )
        .order_by(resources.c.id)
    )
    return query.with_for_update(of=resources) if lock else query


def ineligible(row):
    if not row["can_read"]:
        raise DomainError(404, "not_found", "Selection unavailable under current access")
    if row["expected"] != row["lock_version"] or row["set_id"] != row["current_set"]:
        return "conflict"
    if row["publication_state"] != "draft" or row["set_status"] == "retired":
        return "read_only"
    if row["active_job"]:
        return "active_job"
    return None


def edit_patch(command):
    fields = sorted(set(command.values) | set(command.clear_fields))
    if not fields or set(fields) - editor.EDITABLE:
        raise DomainError(422, "invalid_fields", "Choose one or more editable metadata fields")
    if set(command.values) & set(command.clear_fields):
        raise DomainError(422, "ambiguous_clear", "Choose either replace or clear for each field")
    if "dct_title_s" in command.clear_fields:
        raise DomainError(422, "required_field", "Title cannot be cleared")
    patch = ResourceUpdate(lock_version=1, values=command.values, clear_fields=command.clear_fields)
    return fields, patch


def preview_item(row, patch):
    status = ineligible(row)
    changes = {}
    if status is None:
        if patch is None:
            # Revert the exact stored version, including legacy values and null vs empty lists.
            changes = {
                name: {"before": diff["after"], "after": diff["before"]}
                for name, diff in row["changes"].items()
            }
        else:
            try:
                values, _ = editor.prepare_changes(
                    {**row, "id": row["resource_id"]},
                    patch.model_copy(update={"lock_version": row["expected"]}),
                    [],
                )
                changes = {
                    name: {"before": row[name], "after": value} for name, value in values.items()
                }
            except DomainError as exc:
                if exc.code != "no_changes":
                    raise
        status = "ready" if changes else "unchanged"
    return dict(
        resource_id=row["resource_id"],
        set_id=row["set_id"],
        before_version=row["expected"],
        changes=changes,
        status=status,
    )


async def preview(engine, actor, key, *, command=None, reverts=None):
    authorize(actor)
    async with engine.begin() as conn:
        if reverts is None:
            selection_id = command.selection_id
            fields, patch = edit_patch(command)
            query = members(selection_id)
            payload = command.model_dump(mode="json")
        else:
            original = await accessible(conn, actor, reverts)
            if original["reverts"] or not original["applied_at"]:
                raise DomainError(409, "not_reversible", "Choose a confirmed edit to revert")
            selection_id, fields, patch = original["selection_id"], original["fields"], None
            query = reversible_members(reverts)
            payload = {"reverts": str(reverts)}
        selection = await selections.readable(conn, actor, selection_id)
        request_hash = digest(payload)
        action_id = await conn.scalar(
            pg_insert(actions)
            .values(
                id=uuid4(),
                actor_id=selection["actor_id"],
                actor_name=actor.display_name,
                key=key,
                selection_id=selection_id,
                reverts=reverts,
                request_hash=request_hash,
                fields=fields,
            )
            .on_conflict_do_nothing(index_elements=[actions.c.actor_id, actions.c.key])
            .returning(actions.c.id)
        )
        if action_id is None:
            previous = (
                (
                    await conn.execute(
                        select(actions).where(
                            actions.c.actor_id == selection["actor_id"], actions.c.key == key
                        )
                    )
                )
                .mappings()
                .one()
            )
            if previous["request_hash"] != request_hash:
                raise DomainError(
                    409, "idempotency_conflict", "Request key already used for another preview"
                )
            return {"id": previous["id"]}
        columns = sorted(set(fields) | {"dct_title_s"}) if patch else []
        stream = await conn.stream(current_rows(query.subquery(), actor, columns))
        async for chunk in stream.mappings().partitions(CHUNK):
            await conn.execute(
                insert(items),
                [dict(action_id=action_id, **preview_item(row, patch)) for row in chunk],
            )
        await selections.readable(conn, actor, selection_id)
        return {"id": action_id}


async def write_chunk(conn, action, chunk, actor, software_version):
    groups = defaultdict(list)
    events, outcomes = [], []
    for row in chunk:
        status = ineligible(row) or row["status"]
        version = None
        if status == "ready":
            status, version = "changed", row["expected"] + 1
            changes = row["changes"]
            groups[tuple(sorted(changes))].append(
                {
                    "target_id": row["resource_id"],
                    **{"value_" + k: v["after"] for k, v in changes.items()},
                }
            )
            events.append(
                dict(
                    id=uuid4(),
                    set_id=row["set_id"],
                    resource_id=row["resource_id"],
                    actor_id=action["actor_id"],
                    actor_display_name=actor.display_name,
                    action="resource.updated",
                    software_version=software_version,
                    correlation_id=action["id"],
                    idempotency_key=uuid5(action["id"], row["resource_id"]),
                    details={
                        "bulk_action_id": str(action["id"]),
                        "reverts": str(action["reverts"]) if action["reverts"] else None,
                        "resource_id": row["resource_id"],
                        "fields": sorted(changes),
                        "previous_version": row["expected"],
                        "lock_version": version,
                    },
                )
            )
        outcomes.append(
            dict(
                action_id=action["id"],
                resource_id=row["resource_id"],
                status=status,
                after_version=version,
            )
        )
    for names, params in groups.items():
        await conn.execute(
            update(resources)
            .where(resources.c.id == bindparam("target_id"))
            .values(
                **{name: bindparam("value_" + name) for name in names},
                lock_version=resources.c.lock_version + 1,
                updated_at=func.clock_timestamp(),
                gbl_mdModified_dt=func.timezone("UTC", func.clock_timestamp()),
            ),
            params,
        )
    if events:
        await conn.execute(insert(activity), events)
    await conn.execute(insert(results), outcomes)


async def confirm(engine, actor, action_id, software_version):
    authorize(actor)
    async with engine.begin() as conn:
        action = await accessible(conn, actor, action_id, lock=True)
        # Read in a fresh statement after waiting for a concurrent confirmation.
        if await conn.scalar(
            select(executions.c.action_id).where(executions.c.action_id == action_id)
        ):
            return {"id": action_id}
        selected = select(items.c.set_id).where(items.c.action_id == action_id)
        await conn.execute(
            select(sets.c.set_id)
            .where(sets.c.set_id.in_(selected))
            .order_by(sets.c.set_id)
            .with_for_update()
        )
        query = select(
            items.c.resource_id,
            items.c.set_id,
            items.c.before_version.label("expected"),
            items.c.status,
            items.c.changes,
        ).where(items.c.action_id == action_id)
        await conn.execute(
            insert(executions).values(
                action_id=action_id, actor_id=action["actor_id"], actor_name=actor.display_name
            )
        )
        stream = await conn.stream(current_rows(query.subquery(), actor, lock=True))
        async for chunk in stream.mappings().partitions(CHUNK):
            await write_chunk(conn, action, chunk, actor, software_version)
        await selections.readable(conn, actor, action["selection_id"])
        return {"id": action_id}


async def detail(engine, actor, action_id, offset, limit):
    authorize(actor)
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="REPEATABLE READ")
        async with conn.begin():
            action = await accessible(conn, actor, action_id)
            state = func.coalesce(results.c.status, items.c.status)
            base = items.outerjoin(results)
            total_query = (
                select(state, func.count())
                .select_from(base)
                .where(items.c.action_id == action_id)
                .group_by(state)
            )
            totals = dict((await conn.execute(total_query)).all())
            query = (
                select(
                    items.c.resource_id,
                    items.c.before_version,
                    results.c.after_version,
                    state.label("status"),
                    items.c.changes,
                )
                .select_from(base)
                .where(items.c.action_id == action_id)
                .order_by(items.c.resource_id)
            )
            page = (await conn.execute(query.offset(offset).limit(limit))).mappings().all()
            return {
                **action,
                "totals": totals,
                "total": sum(totals.values()),
                "offset": offset,
                "limit": limit,
                "items": page,
            }


async def history(engine, actor, offset, limit):
    authorize(actor)
    query = (
        summary_query()
        .join(actors, actors.c.id == actions.c.actor_id)
        .where(actors.c.kind == actor.kind, actors.c.subject_key == actor.actor_id)
    )
    async with engine.connect() as conn:
        total = await conn.scalar(select(func.count()).select_from(query.subquery()))
        rows = (
            (
                await conn.execute(
                    query.order_by(actions.c.created_at.desc(), actions.c.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )
    return {"total": total, "offset": offset, "limit": limit, "items": rows}
