"""Job transactions and current authorization; no browser-owned execution state."""

from uuid import uuid4

from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.activity import activity
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.jobs.models import attempts, items, jobs
from app.jobs.schemas import JobResponse
from app.persistence import actors
from app.resources.models import resources
from app.sets.models import sets
from app.sets.service import visible
from app.workflows import service as workflows

TERMINAL = {"succeeded", "partially_succeeded", "failed", "cancelled", "rejected"}
REQUIRED = {"jobs:submit", "jobs:read", "resources:read", "sets:read"}


def authorize(actor, set_id, permissions):
    if actor is None or actor.kind != "user" or not permissions.issubset(actor.permissions):
        raise DomainError(403, "permission_denied", "Permission denied")
    if actor.set_ids is not None and str(set_id) not in actor.set_ids:
        raise DomainError(404, "not_found", "Job or Set not found")


async def totals(connection, job_id):
    rows = await connection.execute(
        select(items.c.disposition, func.count())
        .where(items.c.job_id == job_id)
        .group_by(items.c.disposition)
    )
    return dict(rows.all())


async def response(connection, job):
    return JobResponse(**job, totals=await totals(connection, job["job_id"]))


async def readable(connection, actor, job_id, extra=frozenset()):
    row = (
        (
            await connection.execute(
                select(jobs).join(sets).where(jobs.c.job_id == job_id, visible(actor))
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise DomainError(404, "not_found", "Job not found")
    authorize(actor, row["set_id"], {"jobs:read", "sets:read", "resources:read"} | extra)
    return row


async def submit(engine, actor, command, key, software_version):
    authorize(actor, command.set_id, REQUIRED)
    payload = command.model_dump(mode="json")
    if command.selection_id is None:
        payload.pop("selection_id")  # Preserve existing inline submission receipts.
    request_hash = workflows.digest(payload)
    async with engine.begin() as connection:
        state = await connection.scalar(
            select(sets.c.status)
            .where(sets.c.set_id == command.set_id, visible(actor))
            .with_for_update(read=True)
        )
        if state is None:
            raise DomainError(404, "not_found", "Set not found")
        actor_id = await actor_identity(connection, actor)
        criteria = [
            jobs.c.actor_id == actor_id,
            jobs.c.set_id == command.set_id,
            jobs.c.operation == "resources.validate",
            jobs.c.idempotency_key == key,
        ]
        previous = (await connection.execute(select(jobs).where(*criteria))).mappings().first()
        if previous:
            if previous["request_hash"] != request_hash:
                raise DomainError(
                    409, "idempotency_conflict", "Key already used for another selection"
                )
            return await response(connection, previous)
        if state == "retired":
            raise DomainError(409, "retired", "Retired Sets cannot start work")
        workflow_id = None
        if command.workflow_version_id:
            authorize(actor, command.set_id, {"workflows:read"})
            from app.workflows.models import versions

            version = (
                (
                    await connection.execute(
                        select(versions)
                        .where(versions.c.version_id == command.workflow_version_id)
                        .with_for_update(read=True)
                    )
                )
                .mappings()
                .first()
            )
            if version is None:
                raise DomainError(404, "not_found", "Workflow version not found")
            root = await workflows.root(connection, actor, version["workflow_id"])
            if root["set_id"] != command.set_id:
                raise DomainError(404, "not_found", "Workflow version not found")
            definition = await workflows.version_response(connection, version)
            if (
                version["state"] != "active"
                or len(definition.processes) != 1
                or any(
                    process.process_type != "validate"
                    or process.configuration.model_dump(exclude_none=True)
                    for process in definition.processes
                )
            ):
                raise DomainError(
                    422,
                    "unsupported_workflow",
                    "This worker supports active validation-only definitions",
                )
            workflow_id = version["workflow_id"]
        if command.selection_id:
            from app.resources import selections as saved
            from app.resources.selection_models import selection_items

            await saved.readable(connection, actor, command.selection_id)
            count = await connection.scalar(
                select(func.count())
                .select_from(selection_items)
                .where(selection_items.c.selection_id == command.selection_id)
            )
            wrong_scope = await connection.scalar(
                select(func.count())
                .select_from(selection_items)
                .where(
                    selection_items.c.selection_id == command.selection_id,
                    selection_items.c.set_id != command.set_id,
                )
            )
            if not count or wrong_scope:
                raise DomainError(
                    422, "invalid_selection", "Select Resources from one Set for validation"
                )
        else:
            selected = dict(
                (
                    await connection.execute(
                        select(resources.c.id, resources.c.lock_version)
                        .where(
                            resources.c.set_id == command.set_id,
                            resources.c.id.in_([r.resource_id for r in command.selection]),
                        )
                        .with_for_update(read=True)
                    )
                ).all()
            )
            for row in command.selection:
                if row.resource_id not in selected:
                    raise DomainError(404, "not_found", "Selected Resource not found")
                if selected[row.resource_id] != row.lock_version:
                    raise DomainError(409, "stale_version", "Selection changed. Preview again.")
        job_id = uuid4()
        inserted = await connection.scalar(
            pg_insert(jobs)
            .values(
                job_id=job_id,
                set_id=command.set_id,
                actor_id=actor_id,
                operation="resources.validate",
                idempotency_key=key,
                request_hash=request_hash,
                workflow_id=workflow_id,
                workflow_version_id=command.workflow_version_id,
                software_version=software_version,
            )
            .on_conflict_do_nothing()
            .returning(jobs.c.job_id)
        )
        if inserted and command.selection_id:
            await connection.execute(
                insert(items).from_select(
                    ["job_id", "position", "resource_id", "resource_version"],
                    select(
                        literal(job_id),
                        func.row_number().over(order_by=selection_items.c.resource_id),
                        selection_items.c.resource_id,
                        selection_items.c.resource_version,
                    ).where(selection_items.c.selection_id == command.selection_id),
                )
            )
        elif inserted:
            await connection.execute(
                insert(items),
                [
                    dict(
                        job_id=job_id,
                        position=n,
                        resource_id=r.resource_id,
                        resource_version=r.lock_version,
                    )
                    for n, r in enumerate(command.selection, 1)
                ],
            )
        job = (await connection.execute(select(jobs).where(*criteria))).mappings().one()
        if job["request_hash"] != request_hash:
            raise DomainError(409, "idempotency_conflict", "Key already used for another selection")
        return await response(connection, job)


async def finish(connection, job, state, acting_actor=None):
    """Terminal state, exact totals, report, attempt and business evidence commit together."""
    job_id = job["job_id"]
    evidence_actor_id = (
        await actor_identity(connection, acting_actor) if acting_actor else job["actor_id"]
    )
    counts = await totals(connection, job_id)
    if counts.get("pending", 0):
        raise ValueError("Cannot finish with pending items")
    from app.jobs.reports import write_report

    await write_report(connection, job_id, counts)
    await connection.execute(
        update(jobs)
        .where(jobs.c.job_id == job_id)
        .values(
            state=state,
            lease_token=None,
            lease_until=None,
            finished_at=func.clock_timestamp(),
        )
    )
    await connection.execute(
        update(attempts)
        .where(
            attempts.c.job_id == job_id,
            attempts.c.number == job["attempt_number"],
            attempts.c.state == "running",
        )
        .values(state=state, finished_at=func.clock_timestamp())
    )
    await connection.execute(
        insert(activity).values(
            id=uuid4(),
            set_id=job["set_id"],
            actor_id=evidence_actor_id,
            actor_display_name=await connection.scalar(
                select(actors.c.display_name).where(actors.c.id == evidence_actor_id)
            ),
            action="validation.completed",
            outcome=state,
            software_version=job["software_version"],
            correlation_id=job_id,
            idempotency_key=job_id,
            job_id=job_id,
            workflow_id=job["workflow_id"],
            workflow_version_id=job["workflow_version_id"],
            details={"totals": counts, "validation_scope": "draft", "total": sum(counts.values())},
        )
    )


async def cancel(engine, actor, job_id):
    async with engine.begin() as connection:
        job = await readable(connection, actor, job_id, {"jobs:cancel"})
        job = (
            (
                await connection.execute(
                    select(jobs).where(jobs.c.job_id == job_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )
        if job["state"] not in TERMINAL:
            await connection.execute(
                update(items)
                .where(items.c.job_id == job_id, items.c.disposition == "pending")
                .values(disposition="cancelled")
            )
            await finish(connection, job, "cancelled", actor)
        job = (
            (await connection.execute(select(jobs).where(jobs.c.job_id == job_id))).mappings().one()
        )
        return await response(connection, job)


async def expire_artifacts(connection):
    from app.jobs.reports import expire

    return await expire(connection)
