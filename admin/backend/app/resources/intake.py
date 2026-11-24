"""Staff intake and atomic promotion through the ordinary Resource CSV create path."""

import csv
import io
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, any_, bindparam, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY

from app.auth import Actor
from app.csv_exchange import CsvInput, chunks, csv_line
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.persistence import actors
from app.resources import csv_io, service
from app.resources.intake_models import batches, drafts, events
from app.resources.models import resources
from app.sets.membership import complete_intake_assignments
from app.sets.models import commands
from app.sets.schemas import SetID
from app.sets.service import command_receipt, get_set, write_activity


class Batch(BaseModel):
    id: UUID
    uploader: str
    created_at: datetime
    pending: int


class Draft(BaseModel):
    row_number: int
    resource_id: str
    title: str
    version: int
    csv: str
    catalog_id: str | None = None


class DraftPage(BaseModel):
    pending: int
    items: list[Draft]


class Edit(CsvInput):
    version: int = Field(ge=1)


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: SetID
    rows: list[Annotated[int, Field(ge=1, le=2147483647)]] | None = Field(
        min_length=1,
        description="Original CSV row numbers. Use null to select all pending rows.",
    )


class ConfirmAssignment(Assignment):
    confirmed: Literal[True]
    preview_hash: str = Field(pattern="^[a-f0-9]{64}$")


def batch_query(actor):
    service.authorize_import(actor, unassigned=True)
    query = select(
        batches.c.id,
        batches.c.actor_id,
        batches.c.receipt_key,
        batches.c.headings,
        batches.c.created_at,
        actors.c.display_name.label("uploader"),
    ).join(actors, batches.c.actor_id == actors.c.id)
    if "resources:intake-manage" not in actor.permissions:
        query = query.where(actors.c.subject_key == actor.actor_id, actors.c.kind == actor.kind)
    return query


async def batch_for(connection, actor, batch_id, *, lock=False):
    query = batch_query(actor).where(batches.c.id == batch_id)
    if lock:
        query = query.with_for_update(of=batches)
    batch = (await connection.execute(query)).mappings().first()
    if batch is None:
        raise DomainError(404, "not_found", "Upload unavailable")
    return batch


async def log(connection, batch_id, actor_id, action, details):
    await connection.execute(
        insert(events).values(
            id=uuid4(), batch_id=batch_id, actor_id=actor_id, action=action, details=details
        )
    )


async def save_batch(connection, actor, actor_id, command, report, key, software_version):
    batch_id = uuid4()
    reader = csv.reader(io.StringIO(command.csv.lstrip("\ufeff"), newline=""), strict=True)
    headings = next(reader)
    await connection.execute(
        insert(batches).values(
            id=batch_id,
            actor_id=actor_id,
            receipt_key=key,
            original_csv=command.csv,
            headings=headings,
        )
    )
    await csv_io.apply_rows(
        connection,
        actor,
        actor_id,
        command,
        report,
        uuid4(),
        software_version,
        intake_batch_id=batch_id,
    )
    for group in chunks(report["items"]):
        saved = []
        for row in group:
            cells = next(reader)
            if row["outcome"] == "created":
                saved.append(
                    dict(
                        batch_id=batch_id,
                        row_number=row["row"],
                        resource_id=row["resource_id"],
                        title=row["values"]["dct_title_s"],
                        cells=cells,
                        catalog_id=row["resource_id"],
                    )
                )
        if saved:
            await connection.execute(insert(drafts), saved)
    report["batch_id"] = str(batch_id)
    await log(
        connection,
        batch_id,
        actor_id,
        "saved",
        {"count": sum(row["outcome"] == "created" for row in report["items"])},
    )


async def import_pending_batches(connection):
    """Materialize existing, validated intake rows during the optional-Set migration."""
    uploads = (
        await connection.execute(
            select(
                batches.c.id,
                batches.c.headings,
                batches.c.actor_id,
                actors.c.subject_key,
                actors.c.display_name,
            )
            .join(actors)
            .order_by(batches.c.created_at, batches.c.id)
        )
    ).mappings()
    for upload in uploads:
        actor = Actor(
            upload["subject_key"],
            "user",
            upload["display_name"],
            None,
            frozenset({"resources:read", "resources:import", "sets:read", "sources:read"}),
        )
        after = 0
        while True:
            rows = (
                (
                    await connection.execute(
                        select(drafts)
                        .where(pending(upload["id"]), drafts.c.row_number > after)
                        .order_by(drafts.c.row_number)
                        .limit(500)
                    )
                )
                .mappings()
                .all()
            )
            if not rows:
                break
            after = rows[-1]["row_number"]
            request = csv_io.CsvRequest(
                mode="create",
                csv=csv_line(upload["headings"]) + "".join(csv_line(r["cells"]) for r in rows),
            )
            parsed = csv_io.parse(request, actor, saved_upload=True)
            for row, saved in zip(parsed, rows, strict=True):
                row["row"] = saved["row_number"]
            report = await csv_io.plan_rows(connection, actor, request, parsed)
            await csv_io.apply_rows(
                connection,
                actor,
                upload["actor_id"],
                request,
                report,
                uuid4(),
                "intake_02",
                intake_batch_id=upload["id"],
            )
            numbers = [r["row"] for r in report["items"] if r["outcome"] == "created"]
            if numbers:
                await connection.execute(
                    update(drafts)
                    .where(drafts.c.batch_id == upload["id"], drafts.c.row_number.in_(numbers))
                    .values(catalog_id=drafts.c.resource_id)
                )


def pending(batch_id):
    return (drafts.c.batch_id == batch_id) & drafts.c.assigned_import.is_(None)


async def list_batches(engine, actor, offset, limit):
    count = select(func.count()).select_from(drafts).where(pending(batches.c.id)).scalar_subquery()
    query = (
        batch_query(actor)
        .add_columns(count.label("pending"))
        .order_by(batches.c.created_at.desc(), batches.c.id)
    )
    async with engine.connect() as connection:
        return (await connection.execute(query.offset(offset).limit(limit))).mappings().all()


def draft_item(row, headings):
    return Draft(
        **{**row, "title": row.get("current_title") or row["title"]},
        csv=csv_line(headings) + csv_line(row["cells"]),
    )


async def list_drafts(engine, actor, batch_id, offset, limit):
    async with engine.connect() as connection:
        batch = await batch_for(connection, actor, batch_id)
        query = (
            select(drafts, resources.c.dct_title_s.label("current_title"))
            .outerjoin(resources, resources.c.id == drafts.c.catalog_id)
            .where(pending(batch_id))
            .order_by(drafts.c.row_number)
        )
        rows = (await connection.execute(query.offset(offset).limit(limit))).mappings()
        return DraftPage(
            items=[draft_item(row, batch["headings"]) for row in rows],
            pending=await connection.scalar(
                select(func.count()).select_from(drafts).where(pending(batch_id))
            ),
        )


async def receipt(engine, actor, batch_id):
    async with engine.connect() as connection:
        batch = await batch_for(connection, actor, batch_id)
        report = await connection.scalar(
            select(commands.c.response).where(
                commands.c.operation == "resource:csv",
                commands.c.actor_id == batch["actor_id"],
                commands.c.idempotency_key == batch["receipt_key"],
            )
        )
        await csv_io.authorize_report(connection, actor, report)
        return report


async def edit(engine, actor, batch_id, number, command, key):
    async with engine.begin() as connection:
        batch = await batch_for(connection, actor, batch_id, lock=True)
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await command_receipt(
            connection,
            actor_id,
            "intake:edit",
            key,
            {"batch": str(batch_id), "row": number, **command.model_dump()},
            Draft,
        )
        if replay:
            return replay
        query = update(drafts).where(
            pending(batch_id), drafts.c.row_number == number, drafts.c.version == command.version
        )
        canonical = await connection.scalar(
            select(drafts.c.catalog_id).where(pending(batch_id), drafts.c.row_number == number)
        )
        if canonical is not None:
            raise DomainError(409, "catalog_draft", "Open the Resource to edit its saved metadata")
        csv_request = csv_io.CsvRequest(csv=command.csv, mode="create")
        parsed = csv_io.parse(csv_request, actor, saved_upload=True)
        plan = await csv_io.plan_rows(connection, actor, csv_request, parsed)
        reader = csv.reader(io.StringIO(command.csv.lstrip("\ufeff"), newline=""))
        if next(reader) != batch["headings"] or len(plan["items"]) != 1:
            raise DomainError(422, "invalid_csv", "Keep the original headings and one data row")
        row = plan["items"][0]
        if row["errors"]:
            raise DomainError(422, "invalid_csv", " ".join(row["errors"]))
        updated = (
            (
                await connection.execute(
                    query.values(
                        version=command.version + 1,
                        cells=next(reader),
                        resource_id=row["resource_id"],
                        title=row["values"]["dct_title_s"],
                    ).returning(drafts)
                )
            )
            .mappings()
            .first()
        )
        if not updated:
            raise DomainError(
                409, "stale_version", "Draft changed or was assigned. Reload the queue."
            )
        result = draft_item(updated, batch["headings"])
        await log(
            connection, batch_id, actor_id, "edited", {"row": number, "version": result.version}
        )
        await connection.execute(
            update(commands).where(*criteria).values(response=result.model_dump())
        )
        return result


async def assign(engine, actor, batch_id, command, key=None, software_version=None):
    async with engine.begin() as connection:
        if key:
            # Serialize alongside all other Resource import writers.
            await connection.execute(text("SELECT pg_advisory_xact_lock(718443802)"))
        batch = await batch_for(connection, actor, batch_id, lock=bool(key))
        scope = await get_set(connection, actor, command.set_id, lock=bool(key))
        if scope.status == "retired":
            raise DomainError(409, "retired", "Choose a non-retired Set")
        if key:
            actor_id = await actor_identity(connection, actor)
            criteria, replay = await command_receipt(
                connection,
                actor_id,
                "intake:assign",
                key,
                {"batch": str(batch_id), **command.model_dump(mode="json")},
                csv_io.CsvPreview,
            )
            if replay:
                created = [
                    r.model_dump() for r in replay.items if r.outcome in {"created", "assigned"}
                ]
                owners = await csv_io.current_owners(connection, actor, created)
                if any(owners.get(r["resource_id"]) != scope.set_id for r in created):
                    raise DomainError(
                        403, "permission_denied", "Assignment receipt is outside scope"
                    )
                return replay
        query = select(drafts).where(pending(batch_id)).order_by(drafts.c.row_number)
        if command.rows is not None:
            # Bind one PostgreSQL array even for large selections.
            query = query.where(
                drafts.c.row_number
                == any_(bindparam("numbers", command.rows, type_=ARRAY(Integer)))
            )
        query = query.add_columns(
            resources.c.lock_version.label("resource_version"),
            resources.c.set_id.label("current_set"),
        ).outerjoin(resources, resources.c.id == drafts.c.catalog_id)
        if key:
            existing = query.with_only_columns(drafts.c.catalog_id).order_by(None).subquery()
            await connection.execute(
                select(resources.c.id)
                .where(resources.c.id.in_(select(existing.c.catalog_id)))
                .order_by(resources.c.id)
                .with_for_update()
            )
        rows = (await connection.execute(query)).mappings().all()
        if not rows or (command.rows is not None and len(rows) != len(command.rows)):
            raise DomainError(
                409, "stale_preview", "Selection changed. Reload the queue and preview again."
            )
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(batch["headings"])
        writer.writerows(row["cells"] for row in rows)
        request = csv_io.CsvRequest(mode="create", set_id=scope.set_id, csv=buffer.getvalue())
        parsed = csv_io.parse(request, actor, saved_upload=True)
        for item, row in zip(parsed, rows, strict=True):
            item["row"] = row["row_number"]
        report = await csv_io.plan_rows(connection, actor, request, parsed)
        for item, saved in zip(report["items"], rows, strict=True):
            if (
                saved["catalog_id"]
                and item["outcome"] == "skipped"
                and saved["current_set"] is None
            ):
                item["outcome"] = "assign"
                item["warnings"] = [
                    note for note in item["warnings"] if not note.startswith("ID already exists;")
                ]
                item["changes"] = {"set_id": {"before": None, "after": scope.set_id}}
                report["ready"] += 1
        report["preview_hash"] = service.digest(
            [
                str(batch_id),
                report["preview_hash"],
                [[r["version"], r["resource_version"]] for r in rows],
            ]
        )
        if not key:
            return report
        if command.preview_hash != report["preview_hash"]:
            raise DomainError(409, "stale_preview", "Drafts or destination changed. Preview again.")
        import_id = uuid4()
        await csv_io.apply_rows(
            connection, actor, actor_id, request, report, import_id, software_version
        )
        created = [r["row"] for r in report["items"] if r["outcome"] == "created"]
        for group in chunks(created):
            await connection.execute(
                update(drafts)
                .where(pending(batch_id), drafts.c.row_number.in_(group))
                .values(assigned_import=import_id)
            )
        assigned = [item for item in report["items"] if item["outcome"] == "assign"]
        for group in chunks(assigned):
            identifiers = [item["resource_id"] for item in group]
            await connection.execute(
                update(resources)
                .where(resources.c.id.in_(identifiers), resources.c.set_id.is_(None))
                .values(
                    set_id=scope.set_id,
                    lock_version=resources.c.lock_version + 1,
                    updated_at=func.clock_timestamp(),
                )
            )
            await complete_intake_assignments(connection, identifiers)
            for item in group:
                item["outcome"] = "assigned"
        if assigned:
            await write_activity(
                connection,
                actor,
                actor_id,
                scope.set_id,
                key,
                software_version,
                action="resource.associated",
                details={
                    "batch_id": str(batch_id),
                    "rows": [item["row"] for item in assigned],
                    "resource_ids": [item["resource_id"] for item in assigned],
                    "target_set_id": scope.set_id,
                },
            )
        created.extend(item["row"] for item in assigned)
        await log(
            connection,
            batch_id,
            actor_id,
            "assigned",
            {
                "rows": created,
                "set_id": scope.set_id,
                "import_id": str(import_id)
                if any(item["outcome"] == "created" for item in report["items"])
                else None,
            },
        )
        await connection.execute(update(commands).where(*criteria).values(response=report))
        return report
