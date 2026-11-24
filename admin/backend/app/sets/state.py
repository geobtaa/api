"""Confirmed Set state changes, serialized with maintenance and Task commands."""

from sqlalchemy import func, select, update

from app.activity import activity
from app.identity.actors import actor_identity
from app.jobs.models import jobs
from app.resources.models import resources
from app.sets.models import commands, sets
from app.sets.schemas import SetResponse, SetStatePreview
from app.sets.service import SetError, authorize, command_receipt, get_set, write_activity
from app.work.models import tasks

TRANSITIONS = {
    ("active", "inactive"): ("sets:update", "Deactivate Set", "set.deactivated"),
    ("inactive", "active"): ("sets:update", "Activate Set", "set.activated"),
    ("active", "retired"): ("sets:retire", "Retire Set", "set.retired"),
    ("inactive", "retired"): ("sets:retire", "Retire Set", "set.retired"),
    ("retired", "inactive"): ("sets:restore", "Restore to inactive", "set.restored"),
}


def options(actor):
    return [
        {"current": current, "target": target, "label": label}
        for (current, target), (permission, label, _) in TRANSITIONS.items()
        if actor.kind == "user" and permission in actor.permissions
    ]


def transition(actor, current, target):
    result = TRANSITIONS.get((current, target))
    if result is None:
        raise SetError(409, "invalid_transition", "This state transition is unavailable")
    authorize(actor, result[0])
    return result[2]


async def open_tasks(connection, set_id):
    return await connection.scalar(
        select(func.count())
        .select_from(tasks)
        .where(tasks.c.set_id == set_id, tasks.c.status.in_(("open", "in_progress", "blocked")))
    )


async def active_jobs(connection, set_id):
    return await connection.scalar(
        select(func.count())
        .select_from(jobs)
        .where(jobs.c.set_id == set_id, jobs.c.state.in_(("queued", "running")))
    )


async def preview(engine, actor, set_id, target):
    authorize(actor)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            item = await get_set(connection, actor, set_id)
            transition(actor, item.status, target)
            count = await open_tasks(connection, set_id)
            job_count = await active_jobs(connection, set_id)
            resource_count = await connection.scalar(
                select(func.count()).select_from(resources).where(resources.c.set_id == set_id)
            )
    consequences = [
        "Existing Task history and completion reports are preserved.",
        "The state change and its reason are recorded in Set history.",
        "Resource membership, publication and existing job evidence are preserved.",
    ]
    if target == "retired":
        consequences.append(
            "Retirement stops new Tasks, maintenance changes and routine Set edits. "
            "The Set is omitted from default lists."
        )
        if count:
            consequences.append(f"Resolve {count} open Task(s) before retiring this Set.")
        if job_count:
            consequences.append(f"Finish or cancel {job_count} active job(s) before retirement.")
    elif target == "inactive":
        consequences.append(
            "Future recurring Tasks pause. Existing Tasks can still be completed. "
            "Activation requires a separate action."
        )
    else:
        consequences.append(
            "Enabled maintenance resumes. A next Task is created for each due maintenance "
            "rule that does not already have an open occurrence."
        )
    return SetStatePreview(
        set_id=set_id,
        title=item.title,
        current=item.status,
        target=target,
        lock_version=item.lock_version,
        open_tasks=count,
        active_jobs=job_count,
        managed_resources=resource_count,
        can_proceed=target != "retired" or (count == 0 and job_count == 0),
        consequences=consequences,
    )


async def change(engine, actor, set_id, command, key, software_version):
    authorize(actor)
    allowed = {value[0] for (_, target), value in TRANSITIONS.items() if target == command.target}
    if not allowed.intersection(actor.permissions):
        raise SetError(403, "permission_denied", "Set state permission required")
    async with engine.begin() as connection:
        previous = await get_set(connection, actor, set_id, lock=True)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await command_receipt(
            connection,
            actor_id,
            f"state:{set_id}",
            key,
            command.model_dump(mode="json"),
            SetResponse,
        )
        if replay is not None:
            # A restored Set may now be active; use the original action's permission.
            actions = {value[2]: value[0] for value in TRANSITIONS.values()}
            action = await connection.scalar(
                select(activity.c.action).where(
                    activity.c.set_id == set_id,
                    activity.c.actor_id == actor_id,
                    activity.c.idempotency_key == key,
                    activity.c.action.in_(actions),
                )
            )
            if action not in actions:
                raise SetError(409, "incomplete_receipt", "State command evidence is unavailable")
            authorize(actor, actions[action])
            return replay
        if previous.lock_version != command.lock_version:
            raise SetError(409, "stale_version", "Set changed. Refresh the state preview.")
        action = transition(actor, previous.status, command.target)
        if command.target == "retired" and await open_tasks(connection, set_id):
            raise SetError(409, "open_tasks", "Resolve open Tasks before retiring this Set")
        if command.target == "retired" and await active_jobs(connection, set_id):
            raise SetError(409, "active_jobs", "Finish or cancel active jobs before retirement")
        await connection.execute(
            update(sets)
            .where(sets.c.set_id == set_id)
            .values(
                status=command.target,
                lock_version=sets.c.lock_version + 1,
                updated_at=func.clock_timestamp(),
                updated_by_actor_id=actor_id,
            )
        )
        result = await get_set(connection, actor, set_id)
        if command.target == "active":
            from app.work.service import resume_set

            await resume_set(connection, actor, actor_id, result)
        await write_activity(
            connection,
            actor,
            actor_id,
            set_id,
            key,
            software_version,
            action=action,
            reason=command.reason,
            details={
                "previous_status": previous.status,
                "status": result.status,
                "previous_version": previous.lock_version,
                "lock_version": result.lock_version,
            },
        )
        await connection.execute(
            update(commands).where(*criteria).values(response=result.model_dump(mode="json"))
        )
    return result
