"""Atomic task commands and current-scope reads shared by all Work views."""

from datetime import UTC, datetime, time
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import String, and_, cast, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.domain import DomainError
from app.identity.actors import actor_identity
from app.identity.models import accounts, grants, set_scopes
from app.persistence import actors
from app.sets import service as set_service
from app.sets.models import commands, sets
from app.sources.models import sources
from app.work.cadence import advance
from app.work.models import events, maintenance, periods, tasks
from app.work.schemas import MaintenanceResponse, PeriodResponse, TaskResponse

OPEN = ("open", "in_progress", "blocked")


def authorize(actor, *permissions):
    set_service.authorize(actor, "tasks:read", *permissions)


def visible(actor):
    return set_service.visible(actor)


def task_query():
    assignee, completer = actors.alias("assignee"), actors.alias("completer")
    return select(
        tasks,
        sets.c.title.label("set_title"),
        sources.c.source_id,
        sources.c.title.label("source_title"),
        assignee.c.display_name.label("assignee_name"),
        completer.c.display_name.label("completed_by_name"),
    ).select_from(
        tasks.join(sets)
        .join(sources)
        .outerjoin(assignee, tasks.c.assignee_id == assignee.c.id)
        .outerjoin(completer, tasks.c.completed_by_id == completer.c.id)
    )


async def get_task(connection, actor, task_id):
    authorize(actor)
    row = (
        (await connection.execute(task_query().where(tasks.c.task_id == task_id, visible(actor))))
        .mappings()
        .first()
    )
    if row is None:
        raise DomainError(404, "not_found", "Task not found or inaccessible")
    return TaskResponse.model_validate(row)


async def lock_task(connection, actor, task_id):
    record = await get_task(connection, actor, task_id)
    await set_service.get_set(connection, actor, record.set_id, lock=True)
    await connection.execute(
        select(tasks.c.task_id).where(tasks.c.task_id == task_id).with_for_update()
    )
    return await get_task(connection, actor, task_id)


ASSIGNEE_PERMISSIONS = {"sets:read", "sources:read", "tasks:read", "tasks:update"}


def assignee_permissions(actor_id):
    return select(func.count(grants.c.permission)).where(
        grants.c.actor_id == actor_id, grants.c.permission.in_(ASSIGNEE_PERMISSIONS)
    ).correlate(actors, accounts).scalar_subquery() == len(ASSIGNEE_PERMISSIONS)


def assignee_scope(actor_id, actor, set_id=None):
    scope = select(set_scopes.c.actor_id).where(set_scopes.c.actor_id == actor_id)
    if set_id is not None:
        scope = scope.where(set_scopes.c.set_id == set_id)
    elif actor.set_ids is not None:
        scope = scope.where(set_scopes.c.set_id.in_(actor.set_ids))
    return accounts.c.all_sets | scope.exists()


async def assignee_allowed(connection, actor, assignee_id, current_actor_id, set_id):
    if assignee_id is None:
        return True
    if assignee_id == current_actor_id:
        return actor.kind == "user" and ASSIGNEE_PERMISSIONS.issubset(actor.permissions)
    return (
        await connection.scalar(
            select(accounts.c.actor_id)
            .join(actors)
            .where(
                accounts.c.actor_id == assignee_id,
                accounts.c.active,
                actors.c.kind == "user",
                assignee_permissions(accounts.c.actor_id),
                assignee_scope(accounts.c.actor_id, actor, set_id),
            )
        )
        is not None
    )


async def validate_assignee(connection, actor, assignee_id, current_actor_id, set_id):
    if not await assignee_allowed(connection, actor, assignee_id, current_actor_id, set_id):
        raise DomainError(
            422, "invalid_assignee", "Choose an active staff member with Task editing access"
        )


async def recurring_assignee(connection, actor, rule, actor_id):
    # Revocation must neither silently retain an ineligible assignee nor block
    # recording completed work. The occurrence remains visible as unassigned.
    return (
        rule["assignee_id"]
        if await assignee_allowed(connection, actor, rule["assignee_id"], actor_id, rule["set_id"])
        else None
    )


async def event(connection, actor, actor_id, task_id, action, details, occurred_at=None):
    await connection.execute(
        insert(events).values(
            event_id=uuid4(),
            task_id=task_id,
            actor_id=actor_id,
            actor_name=actor.display_name,
            action=action,
            details=details,
            occurred_at=occurred_at or func.clock_timestamp(),
            recorded_at=func.clock_timestamp(),
        )
    )


async def finish(connection, criteria, result):
    await connection.execute(
        update(commands).where(*criteria).values(response=result.model_dump(mode="json"))
    )
    return result


async def insert_task(
    connection, actor, actor_id, payload, *, predecessor_id=None, recurring=False
):
    task_id = uuid4()
    await connection.execute(
        insert(tasks).values(
            **payload,
            task_id=task_id,
            created_by_id=actor_id,
            predecessor_id=predecessor_id,
            recurring=recurring,
        )
    )
    await event(
        connection,
        actor,
        actor_id,
        task_id,
        "task.created",
        {
            "recurring": recurring,
            "predecessor_id": str(predecessor_id) if predecessor_id else None,
            "due_on": str(payload["due_on"]),
        },
    )
    return task_id


async def create(engine, actor, command, key):
    authorize(actor, "tasks:create")
    async with engine.begin() as connection:
        subject = await set_service.get_set(connection, actor, command.set_id, lock=True)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await set_service.command_receipt(
            connection,
            actor_id,
            "work:task:create",
            key,
            command.model_dump(mode="json"),
            TaskResponse,
        )
        if replay is not None:
            return replay
        if subject.status == "retired":
            raise DomainError(409, "retired_set", "Restore the Set before creating work")
        await validate_assignee(connection, actor, command.assignee_id, actor_id, command.set_id)
        task_id = await insert_task(connection, actor, actor_id, command.model_dump())
        return await finish(connection, criteria, await get_task(connection, actor, task_id))


async def edit(engine, actor, task_id, command, key):
    authorize(actor, "tasks:update")
    async with engine.begin() as connection:
        record = await lock_task(connection, actor, task_id)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await set_service.command_receipt(
            connection,
            actor_id,
            f"work:task:update:{task_id}",
            key,
            command.model_dump(mode="json"),
            TaskResponse,
        )
        if replay is not None:
            return replay
        editable(record, command.lock_version)
        values = command.model_dump(exclude_unset=True, exclude={"lock_version", "reason"})
        if "assignee_id" in values:
            await validate_assignee(
                connection, actor, values["assignee_id"], actor_id, record.set_id
            )
        if values.get("status") == "cancelled" and record.recurring:
            enabled = await connection.scalar(
                select(maintenance.c.enabled).where(
                    maintenance.c.set_id == record.set_id,
                    maintenance.c.work_type == record.work_type,
                )
            )
            if enabled:
                raise DomainError(
                    409, "maintenance_enabled", "Pause maintenance before cancelling its open Task"
                )
        await connection.execute(
            update(tasks)
            .where(tasks.c.task_id == task_id)
            .values(
                **values, lock_version=record.lock_version + 1, updated_at=func.clock_timestamp()
            )
        )
        if record.recurring and "due_on" in values:
            await connection.execute(
                update(maintenance)
                .where(
                    maintenance.c.set_id == record.set_id,
                    maintenance.c.work_type == record.work_type,
                )
                .values(
                    next_due_on=values["due_on"],
                    lock_version=maintenance.c.lock_version + 1,
                    updated_at=func.clock_timestamp(),
                )
            )
        await event(
            connection,
            actor,
            actor_id,
            task_id,
            "task.updated",
            {
                "changes": command.model_dump(mode="json", exclude_unset=True),
                "previous_status": record.status,
                "previous_due_on": record.due_on.isoformat(),
            },
        )
        return await finish(connection, criteria, await get_task(connection, actor, task_id))


def editable(record, expected):
    if record.lock_version != expected:
        raise DomainError(409, "stale_version", "Reload the current Task before changing it")
    if record.status not in OPEN:
        raise DomainError(409, "terminal_task", "Completed and cancelled occurrences are immutable")


async def complete(engine, actor, task_id, command, key):
    authorize(actor, "tasks:complete")
    async with engine.begin() as connection:
        record = await lock_task(connection, actor, task_id)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await set_service.command_receipt(
            connection,
            actor_id,
            f"work:task:complete:{task_id}",
            key,
            command.model_dump(mode="json"),
            TaskResponse,
        )
        if replay is not None:
            return replay
        editable(record, command.lock_version)
        await connection.execute(
            update(tasks)
            .where(tasks.c.task_id == task_id)
            .values(
                status="completed",
                completed_at=command.completed_at,
                completion_recorded_at=func.clock_timestamp(),
                completed_by_id=actor_id,
                completion_summary=command.summary,
                evidence=[x.model_dump() for x in command.evidence],
                processed_count=command.processed_count,
                changed_count=command.changed_count,
                lock_version=record.lock_version + 1,
                updated_at=func.clock_timestamp(),
            )
        )
        await event(
            connection,
            actor,
            actor_id,
            task_id,
            "task.completed",
            command.model_dump(mode="json"),
            command.completed_at,
        )
        if record.recurring:
            rule = (
                (
                    await connection.execute(
                        select(maintenance).where(
                            maintenance.c.set_id == record.set_id,
                            maintenance.c.work_type == record.work_type,
                        )
                    )
                )
                .mappings()
                .one()
            )
            subject = await set_service.get_set(connection, actor, record.set_id)
            try:
                due = advance(command.completed_at.date(), rule["interval"])
            except (ValueError, OverflowError) as exc:
                raise DomainError(
                    422, "invalid_due_date", "Next due date exceeds the supported calendar"
                ) from exc
            await connection.execute(
                update(maintenance)
                .where(
                    maintenance.c.set_id == record.set_id,
                    maintenance.c.work_type == record.work_type,
                )
                .values(
                    next_due_on=due,
                    updated_at=func.clock_timestamp(),
                    lock_version=maintenance.c.lock_version + 1,
                )
            )
            if rule["enabled"] and subject.status == "active":
                await insert_task(
                    connection,
                    actor,
                    actor_id,
                    {
                        "set_id": record.set_id,
                        "work_type": record.work_type,
                        "title": f"{record.work_type.capitalize()}: {subject.title}"[:250],
                        "due_on": due,
                        "assignee_id": await recurring_assignee(connection, actor, rule, actor_id),
                    },
                    predecessor_id=task_id,
                    recurring=True,
                )
        return await finish(connection, criteria, await get_task(connection, actor, task_id))


async def previous_occurrence(connection, set_id, work_type):
    child = tasks.alias("child")
    return await connection.scalar(
        select(tasks.c.task_id)
        .where(
            tasks.c.set_id == set_id,
            tasks.c.work_type == work_type,
            tasks.c.recurring,
            tasks.c.status.in_(("completed", "cancelled")),
            ~select(child.c.task_id).where(child.c.predecessor_id == tasks.c.task_id).exists(),
        )
        .order_by(tasks.c.created_at.desc(), tasks.c.task_id)
        .limit(1)
    )


async def configure(engine, actor, set_id, work_type, command, key, software_version):
    authorize(actor, "work:configure", "tasks:create")
    async with engine.begin() as connection:
        subject = await set_service.get_set(connection, actor, set_id, lock=True)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await set_service.command_receipt(
            connection,
            actor_id,
            f"work:maintenance:{set_id}:{work_type}",
            key,
            command.model_dump(mode="json"),
            MaintenanceResponse,
        )
        if replay is not None:
            return replay
        if subject.status == "retired":
            raise DomainError(409, "retired_set", "Restore the Set before changing maintenance")
        old = (
            (
                await connection.execute(
                    select(maintenance).where(
                        maintenance.c.set_id == set_id, maintenance.c.work_type == work_type
                    )
                )
            )
            .mappings()
            .first()
        )
        if command.lock_version != (old["lock_version"] if old else 0):
            raise DomainError(409, "stale_version", "Reload the current maintenance settings")
        await validate_assignee(connection, actor, command.assignee_id, actor_id, set_id)
        if command.enabled and subject.status != "active":
            raise DomainError(409, "inactive_set", "Activate the Set before enabling maintenance")
        values = command.model_dump(exclude={"lock_version", "next_due_on"})
        next_due = command.next_due_on or (old["next_due_on"] if old else None)
        if next_due is not None:
            values["next_due_on"] = next_due
        if old:
            await connection.execute(
                update(maintenance)
                .where(maintenance.c.set_id == set_id, maintenance.c.work_type == work_type)
                .values(
                    **values,
                    lock_version=old["lock_version"] + 1,
                    updated_at=func.clock_timestamp(),
                )
            )
        else:
            await connection.execute(
                insert(maintenance).values(**values, set_id=set_id, work_type=work_type)
            )
        pending = await connection.scalar(
            select(tasks.c.task_id).where(
                tasks.c.set_id == set_id,
                tasks.c.work_type == work_type,
                tasks.c.recurring,
                tasks.c.status.in_(OPEN),
            )
        )
        if command.next_due_on is not None and pending is not None:
            raise DomainError(
                409, "open_occurrence", "Edit the existing Task to change its due date"
            )
        if command.enabled and pending is None:
            if next_due is None:
                raise DomainError(422, "due_date_required", "Supply the first Task due date")
            pending = await insert_task(
                connection,
                actor,
                actor_id,
                {
                    "set_id": set_id,
                    "work_type": work_type,
                    "title": f"{work_type.capitalize()}: {subject.title}"[:250],
                    "due_on": next_due,
                    "assignee_id": command.assignee_id,
                },
                predecessor_id=await previous_occurrence(connection, set_id, work_type),
                recurring=True,
            )
        if pending:
            await event(
                connection,
                actor,
                actor_id,
                pending,
                "maintenance.updated",
                command.model_dump(mode="json"),
            )
        await set_service.write_activity(
            connection,
            actor,
            actor_id,
            set_id,
            uuid5(NAMESPACE_URL, f"maintenance:{set_id}:{work_type}:{key}"),
            software_version,
            action="set.updated",
            details={
                "fields": [f"maintenance.{work_type}"],
                "maintenance": command.model_dump(mode="json"),
                "request_key": str(key),
            },
        )
        result = (
            (
                await connection.execute(
                    select(maintenance).where(
                        maintenance.c.set_id == set_id, maintenance.c.work_type == work_type
                    )
                )
            )
            .mappings()
            .one()
        )
        return await finish(connection, criteria, MaintenanceResponse.model_validate(result))


def predicates(
    actor,
    *,
    set_id=None,
    source_id=None,
    status=None,
    work_type=None,
    assignee_id=None,
    unassigned=False,
    q="",
    due_from=None,
    due_to=None,
    completed_from=None,
    completed_to=None,
    calendar_from=None,
    calendar_to=None,
):
    clauses = [visible(actor)]
    for column, value in [
        (tasks.c.set_id, set_id),
        (sources.c.source_id, source_id),
        (tasks.c.work_type, work_type),
        (tasks.c.assignee_id, assignee_id),
    ]:
        if value is not None:
            clauses.append(column == value)
    if status == "pending":
        clauses.append(tasks.c.status.in_(OPEN))
    elif status:
        clauses.append(tasks.c.status == status)
    if unassigned:
        clauses.append(tasks.c.assignee_id.is_(None))
    q = q.strip()
    if q:
        clauses.append(
            or_(
                tasks.c.title.icontains(q, autoescape=True),
                sets.c.title.icontains(q, autoescape=True),
            )
        )
    if due_from:
        clauses.append(tasks.c.due_on >= due_from)
    if due_to:
        clauses.append(tasks.c.due_on <= due_to)
    if completed_from:
        clauses.append(tasks.c.completed_at >= datetime.combine(completed_from, time.min, UTC))
    if completed_to:
        clauses.append(tasks.c.completed_at <= datetime.combine(completed_to, time.max, UTC))
    day = func.coalesce(tasks.c.planned_on, tasks.c.due_on)
    if calendar_from:
        clauses.append(day >= calendar_from)
    if calendar_to:
        clauses.append(day <= calendar_to)
    return and_(*clauses)


async def page(engine, actor, offset, limit, **filters):
    authorize(actor)
    predicate = predicates(actor, **filters)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            total = await connection.scalar(
                select(func.count()).select_from(tasks.join(sets).join(sources)).where(predicate)
            )
            completed = filters.get("status") == "completed"
            ordering = (
                [tasks.c.completed_at.desc(), tasks.c.task_id]
                if completed
                else [
                    func.coalesce(tasks.c.planned_on, tasks.c.due_on)
                    if filters.get("calendar_from") or filters.get("calendar_to")
                    else tasks.c.due_on,
                    tasks.c.task_id,
                ]
            )
            rows = (
                (
                    await connection.execute(
                        task_query()
                        .where(predicate)
                        .order_by(*ordering)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
    return {"items": rows, "total": total, "offset": offset, "limit": limit}


async def history(engine, actor, task_id, offset, limit):
    authorize(actor)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await get_task(connection, actor, task_id)
            predicate = events.c.task_id == task_id
            total = await connection.scalar(
                select(func.count()).select_from(events).where(predicate)
            )
            rows = (
                (
                    await connection.execute(
                        select(events)
                        .where(predicate)
                        .order_by(events.c.recorded_at.desc(), events.c.event_id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
    return {"items": rows, "total": total, "offset": offset, "limit": limit}


async def report(engine, actor, starts_on, ends_on, group_by, offset, limit, **filters):
    authorize(actor, "work:report")
    if ends_on < starts_on:
        raise DomainError(422, "invalid_range", "End date must be on or after start date")
    predicate = predicates(
        actor, status="completed", completed_from=starts_on, completed_to=ends_on, **filters
    )
    completer = actors.alias("completer")
    key, label = {
        "source": (sources.c.source_id, sources.c.title),
        "set": (sets.c.set_id, sets.c.title),
        "work_type": (tasks.c.work_type, tasks.c.work_type),
        "completed_by": (cast(tasks.c.completed_by_id, String), completer.c.display_name),
    }[group_by]
    aggregates = [
        func.count().label("completed"),
        func.coalesce(func.sum(tasks.c.processed_count), 0).label("processed"),
        func.coalesce(func.sum(tasks.c.changed_count), 0).label("changed"),
        func.count()
        .filter(
            cast(func.timezone("UTC", tasks.c.completed_at), tasks.c.due_on.type) > tasks.c.due_on
        )
        .label("late"),
    ]
    base = tasks.join(sets).join(sources).join(completer, tasks.c.completed_by_id == completer.c.id)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            totals = (
                (await connection.execute(select(*aggregates).select_from(base).where(predicate)))
                .mappings()
                .one()
            )
            groups = (
                select(key.label("key"), label.label("label"), *aggregates)
                .select_from(base)
                .where(predicate)
                .group_by(key, label)
            )
            count = await connection.scalar(select(func.count()).select_from(groups.subquery()))
            rows = (
                (await connection.execute(groups.order_by(label, key).offset(offset).limit(limit)))
                .mappings()
                .all()
            )
    return {
        "starts_on": starts_on,
        "ends_on": ends_on,
        "group_by": group_by,
        **totals,
        "groups": rows,
        "total_groups": count,
        "offset": offset,
        "limit": limit,
    }


async def create_period(engine, actor, command, key):
    authorize(actor, "work:configure")
    async with engine.begin() as connection:
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await set_service.command_receipt(
            connection,
            actor_id,
            "work:period:create",
            key,
            command.model_dump(mode="json"),
            PeriodResponse,
        )
        if replay is not None:
            return replay
        try:
            row = (
                (
                    await connection.execute(
                        insert(periods)
                        .values(**command.model_dump(), period_id=uuid4(), created_by_id=actor_id)
                        .returning(periods)
                    )
                )
                .mappings()
                .one()
            )
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise DomainError(
                    409, "duplicate_period", "A reporting period with that name already exists"
                ) from exc
            raise
        return await finish(connection, criteria, PeriodResponse.model_validate(row))


async def resume_set(connection, actor, actor_id, subject):
    """Reactivating a Set restores enabled future work without duplicating open Tasks."""
    rules = (
        (
            await connection.execute(
                select(maintenance).where(
                    maintenance.c.set_id == subject.set_id,
                    maintenance.c.enabled,
                    maintenance.c.next_due_on.is_not(None),
                )
            )
        )
        .mappings()
        .all()
    )
    for rule in rules:
        pending = await connection.scalar(
            select(tasks.c.task_id).where(
                tasks.c.set_id == subject.set_id,
                tasks.c.work_type == rule["work_type"],
                tasks.c.recurring,
                tasks.c.status.in_(OPEN),
            )
        )
        if pending is None:
            await insert_task(
                connection,
                actor,
                actor_id,
                {
                    "set_id": subject.set_id,
                    "work_type": rule["work_type"],
                    "title": f"{rule['work_type'].capitalize()}: {subject.title}"[:250],
                    "due_on": rule["next_due_on"],
                    "assignee_id": await recurring_assignee(connection, actor, rule, actor_id),
                },
                predecessor_id=await previous_occurrence(
                    connection, subject.set_id, rule["work_type"]
                ),
                recurring=True,
            )
