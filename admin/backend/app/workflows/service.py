"""Workflow authoring shares the Set transaction and authorization boundary."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.activity import activity
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.sets.models import commands, sets
from app.sets.service import get_set, visible
from app.workflows.models import processes, versions, workflows
from app.workflows.schemas import Definition, VersionResponse, WorkflowResponse

READ = "workflows:read"
CHANGE = "workflows:change"
ACTIVATE = "workflows:activate"


def rights(actor, set_status):
    return {
        "can_change": actor.kind == "user"
        and CHANGE in actor.permissions
        and set_status != "retired",
        "can_activate": actor.kind == "user"
        and ACTIVATE in actor.permissions
        and set_status != "retired",
    }


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def root(connection, actor, workflow_id):
    row = (
        (
            await connection.execute(
                select(workflows, sets.c.status.label("set_status"))
                .join(sets, sets.c.set_id == workflows.c.set_id)
                .where(workflows.c.workflow_id == workflow_id, visible(actor))
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise DomainError(404, "not_found", "Workflow not found")
    return row


async def version_response(connection, row):
    entries = (
        (
            await connection.execute(
                select(processes)
                .where(processes.c.version_id == row["version_id"])
                .order_by(processes.c.position)
            )
        )
        .mappings()
        .all()
    )
    return VersionResponse(
        **row,
        processes=[
            {key: value for key, value in entry.items() if key not in {"process_id", "version_id"}}
            for entry in entries
        ],
    )


async def detail(connection, actor, workflow_id):
    row = await root(connection, actor, workflow_id)
    current = (
        (
            await connection.execute(
                select(versions).where(
                    versions.c.workflow_id == workflow_id,
                    versions.c.state.in_(["active", "draft"]),
                )
            )
        )
        .mappings()
        .all()
    )
    definitions = {
        version["state"]: await version_response(connection, version) for version in current
    }
    return WorkflowResponse(
        **{k: v for k, v in row.items() if k != "set_status"},
        active=definitions.get("active"),
        draft=definitions.get("draft"),
        **rights(actor, row["set_status"]),
    )


async def get_version(connection, actor, workflow_id, version_id):
    await root(connection, actor, workflow_id)
    row = (
        (
            await connection.execute(
                select(versions).where(
                    versions.c.workflow_id == workflow_id,
                    versions.c.version_id == version_id,
                )
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise DomainError(404, "not_found", "Workflow version not found")
    return await version_response(connection, row)


async def list_workflows(engine, actor, set_id, offset, limit):
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await get_set(connection, actor, set_id)
            predicate = workflows.c.set_id == set_id
            total = await connection.scalar(
                select(func.count()).select_from(workflows).where(predicate)
            )
            rows = (
                (
                    await connection.execute(
                        select(workflows)
                        .where(predicate)
                        .order_by(workflows.c.title, workflows.c.workflow_id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            return {"items": rows, "total": total, "offset": offset, "limit": limit}


async def history(engine, actor, workflow_id, offset, limit):
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await root(connection, actor, workflow_id)
            predicate = versions.c.workflow_id == workflow_id
            total = await connection.scalar(
                select(func.count()).select_from(versions).where(predicate)
            )
            rows = (
                (
                    await connection.execute(
                        select(versions)
                        .where(predicate)
                        .order_by(versions.c.number.desc())
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            return {
                "items": [await version_response(connection, row) for row in rows],
                "total": total,
                "offset": offset,
                "limit": limit,
            }


async def replace_processes(connection, version_id, definition):
    await connection.execute(delete(processes).where(processes.c.version_id == version_id))
    for process in definition.processes:
        values = process.model_dump(mode="json")
        values["configuration"] = process.configuration.model_dump(exclude_none=True)
        await connection.execute(
            insert(processes).values(process_id=uuid4(), version_id=version_id, **values)
        )


async def mutate(engine, actor, operation, command, key, software_version, workflow_id=None):
    permission = ACTIVATE if operation == "activate" else CHANGE
    if actor.kind != "user" or permission not in actor.permissions:
        raise DomainError(403, "permission_denied", "Permission denied")
    async with engine.begin() as connection:
        set_id = (
            command.set_id
            if operation == "create"
            else (await root(connection, actor, workflow_id))["set_id"]
        )
        await get_set(connection, actor, set_id)
        await connection.execute(
            select(sets.c.set_id).where(sets.c.set_id == set_id).with_for_update(read=True)
        )
        scope = await get_set(connection, actor, set_id)
        if workflow_id is not None:
            await connection.execute(
                select(workflows.c.workflow_id)
                .where(workflows.c.workflow_id == workflow_id)
                .with_for_update()
            )
        actor_id = await actor_identity(connection, actor)
        payload = {
            "workflow_id": str(workflow_id) if workflow_id else None,
            **command.model_dump(mode="json"),
        }
        criteria = (
            commands.c.actor_id == actor_id,
            commands.c.operation == f"workflow:{operation}:{set_id}",
            commands.c.idempotency_key == key,
        )
        inserted = await connection.scalar(
            pg_insert(commands)
            .values(
                actor_id=actor_id,
                operation=f"workflow:{operation}:{set_id}",
                idempotency_key=key,
                request_hash=digest(payload),
            )
            .on_conflict_do_nothing()
            .returning(commands.c.idempotency_key)
        )
        if inserted is None:
            receipt = (await connection.execute(select(commands).where(*criteria))).mappings().one()
            if receipt["request_hash"] != digest(payload):
                raise DomainError(
                    409,
                    "idempotency_conflict",
                    "Request key already used for different Workflow changes",
                )
            response = WorkflowResponse.model_validate(receipt["response"])
            return response.model_copy(update=rights(actor, scope.status))
        if scope.status == "retired":
            raise DomainError(409, "retired", "Retired Sets cannot change Workflows")
        if operation == "create":
            workflow_id, version_id = uuid4(), uuid4()
            await connection.execute(
                insert(workflows).values(
                    workflow_id=workflow_id,
                    set_id=set_id,
                    title=command.title,
                    created_by_actor_id=actor_id,
                    updated_by_actor_id=actor_id,
                )
            )
            await connection.execute(
                insert(versions).values(
                    version_id=version_id,
                    workflow_id=workflow_id,
                    number=1,
                    created_by_actor_id=actor_id,
                )
            )
            await replace_processes(connection, version_id, command)
            action = "workflow.created"
        else:
            previous = await detail(connection, actor, workflow_id)
            if command.lock_version != previous.lock_version:
                raise DomainError(
                    409, "stale_version", "Workflow changed. Reload and compare before retrying."
                )
            if operation == "clone":
                if previous.draft is not None or previous.active is None:
                    raise DomainError(
                        409,
                        "draft_unavailable",
                        "Cloning requires an active version and no existing draft",
                    )
                version_id = uuid4()
                number = 1 + await connection.scalar(
                    select(func.max(versions.c.number)).where(versions.c.workflow_id == workflow_id)
                )
                await connection.execute(
                    insert(versions).values(
                        version_id=version_id,
                        workflow_id=workflow_id,
                        number=number,
                        created_by_actor_id=actor_id,
                    )
                )
                await replace_processes(
                    connection, version_id, Definition(processes=previous.active.processes)
                )
                action = "workflow.draft_created"
            else:
                if previous.draft is None:
                    raise DomainError(
                        409, "draft_unavailable", "Clone the active version before editing"
                    )
                version_id = previous.draft.version_id
                if operation == "update":
                    await replace_processes(connection, version_id, command)
                    action = "workflow.updated"
                else:
                    if command.version_id != version_id:
                        raise DomainError(409, "stale_version", "The selected draft changed")
                    definition = Definition(processes=previous.draft.processes)
                    if not definition.processes:
                        raise DomainError(
                            422, "empty_workflow", "Add at least one process before activation"
                        )
                    if previous.active is not None:
                        await connection.execute(
                            update(versions)
                            .where(versions.c.version_id == previous.active.version_id)
                            .values(state="superseded")
                        )
                    await connection.execute(
                        update(versions)
                        .where(versions.c.version_id == version_id)
                        .values(
                            state="active",
                            checksum=digest(definition.model_dump(mode="json")),
                            activated_at=func.clock_timestamp(),
                            activated_by_actor_id=actor_id,
                        )
                    )
                    action = "workflow.activated"
            await connection.execute(
                update(workflows)
                .where(workflows.c.workflow_id == workflow_id)
                .values(
                    lock_version=workflows.c.lock_version + 1,
                    updated_at=func.clock_timestamp(),
                    updated_by_actor_id=actor_id,
                )
            )
        response = await detail(connection, actor, workflow_id)
        await connection.execute(
            insert(activity).values(
                id=uuid4(),
                set_id=set_id,
                actor_id=actor_id,
                actor_display_name=actor.display_name,
                action=action,
                software_version=software_version,
                correlation_id=uuid4(),
                idempotency_key=key,
                workflow_id=workflow_id,
                workflow_version_id=version_id,
                details={"lock_version": response.lock_version},
            )
        )
        await connection.execute(
            update(commands).where(*criteria).values(response=response.model_dump(mode="json"))
        )
    return response
