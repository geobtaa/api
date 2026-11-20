import hashlib
import json
from contextlib import nullcontext
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.activity import activity
from app.auth import Actor
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources import source_membership
from app.resources.models import distributions, evidence, imports, projection_requests, resources
from app.resources.schemas import (
    ImportCommit,
    ImportPreview,
    ImportRequest,
    ImportResult,
    RowOutcome,
)
from app.resources.search import resource_visible
from app.resources.validation import TYPES, normalize
from app.sets.membership import has_permission
from app.sets.models import sets
from app.sets.service import get_set


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def authorize_import(actor, *, unassigned=False):
    required = {"resources:import", "resources:read"}
    if not unassigned:
        required.add("sets:read")
    if actor.kind != "user" or not required.issubset(actor.permissions):
        raise DomainError(
            403, "permission_denied", "Resource import requires staff import and read permissions"
        )


async def plan(connection, actor, command: ImportRequest):
    scope = await get_set(connection, actor, command.set_id)
    if scope.status == "retired":
        raise DomainError(409, "retired", "Choose a non-retired Set")
    ids = [row.get("id") for row in command.records if isinstance(row.get("id"), str)]
    existing = set(
        (await connection.execute(select(resources.c.id).where(resources.c.id.in_(ids)))).scalars()
    )
    counts = {identifier: ids.count(identifier) for identifier in set(ids)}
    outcomes = []
    for index, record in enumerate(command.records):
        _, _, errors, warnings = normalize(record)
        errors.extend(source_membership.assertion_errors(record, scope.source_id))
        identifier = record.get("id")
        identifier = identifier if isinstance(identifier, str) else None
        if identifier is not None and counts.get(identifier, 0) > 1:
            errors.append("Duplicate Resource ID within this batch; choose one source row")
        outcome = "invalid" if errors else "skipped" if identifier in existing else "ready"
        if outcome == "skipped":
            warnings.append("ID already exists; no existing Resource will be changed")
        outcomes.append(
            RowOutcome(
                row=index + 1,
                resource_id=identifier,
                title=str(record.get("dct_title_s", "")),
                outcome=outcome,
                errors=errors,
                warnings=warnings,
            )
        )
    hash_value = digest(
        {
            "request": command.model_dump(mode="json", exclude={"preview_hash", "confirmed"}),
            "set_version": scope.lock_version,
            "items": [row.model_dump() for row in outcomes],
        }
    )
    return ImportPreview(
        set_id=command.set_id,
        set_title=scope.title,
        preview_hash=hash_value,
        items=outcomes,
        ready=sum(row.outcome == "ready" for row in outcomes),
    )


async def preview(engine, actor, command):
    authorize_import(actor)
    async with engine.connect() as connection:
        return await plan(connection, actor, command)


async def commit(
    engine: AsyncEngine, actor: Actor, command: ImportCommit, key: UUID, software_version: str
):
    authorize_import(actor)
    if not command.confirmed:
        raise DomainError(422, "confirmation_required", "Confirm the preview before importing")
    request_hash = digest(command.model_dump(mode="json"))
    async with engine.begin() as connection:
        # One bounded import transaction at a time; serializes competing IDs and retries.
        await connection.execute(text("SELECT pg_advisory_xact_lock(718443802)"))
        await get_set(connection, actor, command.set_id)
        actor_id = await actor_identity(connection, actor)
        previous = (
            (await connection.execute(select(imports).where(imports.c.id == key)))
            .mappings()
            .first()
        )
        if previous:
            if previous["actor_id"] != actor_id or previous["request_hash"] != request_hash:
                raise DomainError(
                    409, "idempotency_conflict", "This import key was used for a different request"
                )
            return ImportResult.model_validate(previous["response"])
        await connection.execute(
            select(sets.c.set_id).where(sets.c.set_id == command.set_id).with_for_update(read=True)
        )
        current = await plan(connection, actor, command)
        if current.preview_hash != command.preview_hash:
            raise DomainError(
                409, "stale_preview", "The import preview changed. Preview again before confirming."
            )
        result = ImportResult(
            import_id=key,
            set_id=command.set_id,
            items=current.items,
            created=current.ready,
        )
        for item in result.items:
            if item.outcome == "ready":
                item.outcome = "created"
        await connection.execute(
            insert(imports).values(
                id=key,
                actor_id=actor_id,
                set_id=command.set_id,
                request_hash=request_hash,
                response=result.model_dump(mode="json"),
            )
        )
        for item in result.items:
            if item.outcome != "created":
                continue
            record = command.records[item.row - 1]
            values, links, _, _ = normalize(record)
            await connection.execute(
                insert(resources).values(
                    **values,
                    set_id=command.set_id,
                    created_by_actor_id=actor_id,
                    publication_state="draft",
                    b1g_publication_state_s="draft",
                    import_id=str(key),
                )
            )
            if links:
                await connection.execute(
                    insert(distributions),
                    [
                        {**link, "resource_id": item.resource_id, "import_id": str(key)}
                        for link in links
                    ],
                )
            await connection.execute(
                insert(evidence).values(
                    resource_id=item.resource_id,
                    import_id=key,
                    source_record=record,
                    warnings=item.warnings,
                )
            )
        await connection.execute(
            insert(activity).values(
                id=uuid4(),
                set_id=command.set_id,
                actor_id=actor_id,
                actor_display_name=actor.display_name,
                action="resources.imported",
                software_version=software_version,
                correlation_id=key,
                idempotency_key=key,
                details={
                    "import_id": str(key),
                    "created": result.created,
                    "skipped": sum(i.outcome == "skipped" for i in result.items),
                    "invalid": sum(i.outcome == "invalid" for i in result.items),
                    "resource_ids": [i.resource_id for i in result.items if i.outcome == "created"],
                },
            )
        )
    return result


def resource_query():
    return select(resources, sets.c.title.label("set_title"), sets.c.source_id).outerjoin(
        sets, resources.c.set_id == sets.c.set_id
    )


async def serialize(connection, rows):
    ids = [row["id"] for row in rows]
    links = (
        (
            await connection.execute(
                select(distributions)
                .where(distributions.c.resource_id.in_(ids))
                .order_by(distributions.c.position, distributions.c.id)
            )
        )
        .mappings()
        .all()
    )
    by_id = {identifier: {} for identifier in ids}
    uri_by_type = {value: key for key, value in TYPES.items()}
    for link in links:
        uri = uri_by_type[link["distribution_type_id"]]
        by_id[link["resource_id"]].setdefault(uri, []).append(
            {"url": link["url"], "label": link["label"]}
        )
    result = []
    excluded = {
        "lifecycle_id",
        "source_id",
        "legacy_source_id",
        "set_id",
        "set_title",
        "lock_version",
        "created_at",
        "updated_at",
        "created_by_actor_id",
        "publication_state",
        "import_id",
        "dct_references_s",
    }
    for row in rows:
        metadata = {
            key: value for key, value in row.items() if key not in excluded and value is not None
        }
        metadata["b1g_publication_state_s"] = row["publication_state"]
        refs = {
            uri: values[0]["url"]
            if len(values) == 1 and values[0]["label"] is None
            else [{k: v for k, v in value.items() if v is not None} for value in values]
            for uri, values in by_id[row["id"]].items()
        }
        if refs:
            metadata["dct_references_s"] = json.dumps(refs)
        result.append(
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "set_id": row["set_id"],
                "set_title": row["set_title"],
                "publication_state": row["publication_state"],
                "lock_version": row["lock_version"],
                "metadata": jsonable_encoder(metadata),
            }
        )
    return result


async def list_resources(engine, actor, q, offset, limit, set_id=None, filters=None):
    from app.resources.search import predicate as search_predicate

    predicate = search_predicate(actor, q, set_id, filters)
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            query = resource_query().where(predicate)
            total = await connection.scalar(select(func.count()).select_from(query.subquery()))
            rows = (
                (
                    await connection.execute(
                        query.order_by(func.lower(resources.c.dct_title_s), resources.c.id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            items = await serialize(connection, rows)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


async def detail(engine, actor, identifier, connection=None):
    async with engine.connect() if connection is None else nullcontext(connection) as connection:
        row = (
            (
                await connection.execute(
                    resource_query().where(resources.c.id == identifier, resource_visible(actor))
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(404, "not_found", "Resource not found")
        item = (await serialize(connection, [row]))[0]
        source = (
            (await connection.execute(select(evidence).where(evidence.c.resource_id == identifier)))
            .mappings()
            .one_or_none()
        )
        links = (
            (
                await connection.execute(
                    select(
                        distributions.c.distribution_type_id,
                        distributions.c.url,
                        distributions.c.label,
                    )
                    .where(distributions.c.resource_id == identifier)
                    .order_by(distributions.c.position, distributions.c.id)
                )
            )
            .mappings()
            .all()
        )
        set_status = await connection.scalar(
            select(sets.c.status).where(sets.c.set_id == row["set_id"])
        )
        projection = None
        if row["publication_state"] == "published":
            result = (
                await connection.execute(
                    select(projection_requests.c.visible_at).where(
                        projection_requests.c.resource_id == identifier,
                        projection_requests.c.resource_version == row["lock_version"],
                    )
                )
            ).first()
            if result:
                projection = "live" if result.visible_at else "pending"
        return {
            **item,
            "projection_status": projection,
            "can_associate": has_permission(actor, "resources:associate")
            and (actor.set_ids is None or bool(actor.set_ids))
            and set_status != "retired"
            and (row["set_id"] is not None or row["publication_state"] == "draft"),
            "editable": actor.kind == "user"
            and "resources:update" in actor.permissions
            and (
                row["publication_state"] == "draft"
                or (
                    row["publication_state"] == "published"
                    and row["set_id"] is not None
                    and not row["gbl_suppressed_b"]
                    and "resources:edit-published" in actor.permissions
                )
            )
            and set_status != "retired",
            "distributions": [dict(link) for link in links],
            "source_record": source["source_record"] if source is not None else None,
            "import_warnings": source["warnings"] if source is not None else [],
        }
