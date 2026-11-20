"""Staff CSV exchange for the Source and Set catalogs."""

import csv
import io
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Literal
from uuid import uuid5

from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.csv_exchange import CsvInput, chunks, csv_line, safe_cell
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources.service import digest
from app.sets import service as set_service
from app.sets.models import sets
from app.sets.schemas import SetCreate, SetUpdate
from app.sources import service as source_service
from app.sources.models import sources
from app.sources.schemas import SourceCreate, SourceUpdate
from app.workflows.catalog import require_catalog


class CatalogCsvRequest(CsvInput):
    mode: Literal["create", "update"]


class CatalogCsvCommit(CatalogCsvRequest):
    preview_hash: str = Field(pattern="^[0-9a-f]{64}$")
    confirmed: Literal[True]


class CatalogCsvRow(BaseModel):
    row: int
    record_id: str
    outcome: str = "invalid"
    errors: list[str] = []
    warnings: list[str] = []
    clear_fields: list[str] = []
    changes: dict[str, dict] = {}
    version: int | None = None


class CatalogCsvReport(BaseModel):
    items: list[CatalogCsvRow]
    preview_hash: str
    ready: int


@dataclass(frozen=True)
class Catalog:
    name: str
    id_field: str
    create: type[BaseModel]
    edit: type[BaseModel]

    @property
    def service(self):
        return set_service if self.name == "sets" else source_service

    @property
    def table(self):
        return sets if self.name == "sets" else sources

    @property
    def editable(self):
        return [k for k in self.edit.model_fields if k != "lock_version"]

    def columns(self):
        ids = [self.id_field, "source_id"] if self.name == "sets" else [self.id_field]
        return [
            *ids,
            "lock_version",
            *self.editable,
            "_csv_encoding",
            *(k + "__clear" for k in self.editable if k != "title"),
        ]

    def query(self, actor):
        query = select(self.table)
        if self.name == "sets":
            query = query.where(set_service.visible(actor), sets.c.status != "retired")
        return query

    def authorize(self, actor, mode=None):
        permissions = []
        if mode:
            permissions.append(self.service.CREATE if mode == "create" else self.service.UPDATE)
        if self.name == "sets" and mode == "create":
            permissions.append(set_service.SOURCE_USE)
            if actor.set_ids is not None:
                raise DomainError(
                    403, "permission_denied", "Creating Sets requires unrestricted Set scope"
                )
        self.service.authorize(actor, *permissions)


SOURCES = Catalog("sources", "source_id", SourceCreate, SourceUpdate)
SETS = Catalog("sets", "set_id", SetCreate, SetUpdate)


def parse(spec, source):
    csv.field_size_limit(sys.maxsize)
    reader = csv.DictReader(io.StringIO(source.removeprefix("\ufeff"), newline=""), strict=True)
    try:
        names = reader.fieldnames or []
        if (
            spec.id_field not in names
            or len(set(names)) != len(names)
            or set(names) - set(spec.columns())
        ):
            raise ValueError(f"Use unique template headers including {spec.id_field}")
        rows = list(reader)
        if not rows:
            raise ValueError("Supply at least one data row")
        for row in rows:
            if row.get("_csv_encoding") == "apostrophe-v1":
                for k, v in row.items():
                    if isinstance(v, str):
                        row[k] = v.removeprefix("'")
        return rows
    except (csv.Error, ValueError) as exc:
        raise DomainError(422, "invalid_csv", str(exc)) from exc


async def export(connection, spec, actor):
    names = spec.columns()
    yield csv_line(names)
    rows = await connection.stream(
        spec.query(actor).order_by(spec.table.c[spec.id_field]).execution_options(yield_per=500)
    )
    async for row in rows.mappings():
        yield csv_line(
            [
                "apostrophe-v1" if k == "_csv_encoding" else safe_cell(str(row.get(k) or ""))
                for k in names
            ]
        )


def values_for(spec, mode, raw, row):
    if None in raw or None in raw.values():
        raise ValueError("Cell count does not match the template")
    if raw.get("_csv_encoding", "") not in ("", "apostrophe-v1"):
        raise ValueError("Unsupported CSV encoding")
    values = {}
    for name in spec.editable:
        value, clear = raw.get(name, ""), raw.get(name + "__clear", "")
        if clear not in ("", "true", "false"):
            raise ValueError(f"{name}__clear must be true or false")
        if clear == "true":
            if mode == "create" or value:
                raise ValueError(f"{name}: a clear requires update mode and an empty cell")
            row.clear_fields.append(name)
            values[name] = None if spec.table.c[name].nullable else ""
        elif value:
            if not value.strip():
                raise ValueError(f"{name}: whitespace-only cells are ambiguous")
            values[name] = value
    return values


async def plan(connection, spec, actor, command, *, lock=False):
    raw_rows = parse(spec, command.csv)
    counts = Counter(raw.get(spec.id_field) or "" for raw in raw_rows)
    existing = {}
    reserved_ids = set()
    for ids in chunks(sorted(counts)):
        if spec == SETS and command.mode == "create":
            reserved_ids.update(
                await connection.scalars(
                    select(sets.c.set_id).where(sets.c.set_id.in_(ids), sets.c.status == "retired")
                )
            )
        query = spec.query(actor).where(spec.table.c[spec.id_field].in_(ids))
        if lock:
            query = query.order_by(spec.table.c[spec.id_field]).with_for_update()
        existing.update({r[spec.id_field]: r for r in (await connection.execute(query)).mappings()})
    rows, mutations = [], {}
    for number, raw in enumerate(raw_rows, 1):
        identifier = raw.get(spec.id_field) or ""
        row = CatalogCsvRow(row=number, record_id=identifier)
        rows.append(row)
        old = existing.get(identifier)
        if old:
            row.version = old["lock_version"]
        try:
            if counts[identifier] > 1 or not identifier.strip():
                raise ValueError(f"Supply a unique {spec.id_field} for every row")
            if identifier in reserved_ids:
                raise ValueError("Set ID unavailable for creation")
            fields = values_for(spec, command.mode, raw, row)
            if command.mode == "create":
                fields[spec.id_field] = identifier
                if spec == SETS:
                    fields["source_id"] = raw.get("source_id", "")
                mutation = spec.create.model_validate(fields)
                if getattr(mutation, spec.id_field) != identifier:
                    raise ValueError("Remove surrounding whitespace from the ID")
                if old:
                    row.outcome = "skipped"
                    continue
                if spec == SETS:
                    await source_service.get_source(connection, actor, mutation.source_id)
            else:
                if not old:
                    raise ValueError("Record missing or unavailable")
                if spec == SETS and raw.get("source_id") and raw["source_id"] != old["source_id"]:
                    raise ValueError("A Set's Source ID is immutable")
                version = raw.get("lock_version") or ""
                if not version.isascii() or not version.isdigit() or int(version) < 1:
                    raise ValueError("Export the catalog and keep its lock_version column")
                if int(version) != old["lock_version"]:
                    row.outcome = "conflict"
                    raise ValueError(
                        "Record changed. Export the current version and review your edits"
                    )
                fields = {k: v for k, v in fields.items() if v != old[k]}
                if not fields:
                    row.outcome = "unchanged"
                    continue
                mutation = spec.edit.model_validate(dict(fields, lock_version=int(version)))
            effective = mutation.model_dump(exclude_unset=True, exclude={"lock_version"})
            if spec == SETS and "workflow_catalog_id" in effective:
                await require_catalog(connection, effective["workflow_catalog_id"])
                effective["workflow"] = effective["workflow_catalog_id"] or ""
            elif spec == SETS and old and "workflow" in effective:
                effective["workflow_catalog_id"] = None
            row.changes = {
                k: {"before": old[k] if old else None, "after": v}
                for k, v in effective.items()
                if not old or v != old[k]
            }
            if row.changes:
                row.outcome = command.mode
                mutations[number] = mutation
            else:
                row.outcome = "unchanged"
        except (ValueError, DomainError) as exc:
            row.errors.append(str(exc))
    return CatalogCsvReport(
        items=rows,
        ready=len(mutations),
        preview_hash=digest(
            {
                "request": command.model_dump(exclude={"preview_hash", "confirmed"}),
                "items": [r.model_dump() for r in rows],
            }
        ),
    ), mutations


async def preview(engine, spec, actor, command):
    spec.authorize(actor, command.mode)
    async with engine.connect() as connection:
        report, _ = await plan(connection, spec, actor, command)
    return report


async def apply(engine, spec, actor, command, key, software_version):
    spec.authorize(actor, command.mode)
    async with engine.begin() as connection:
        actor_id = await actor_identity(connection, actor)
        criteria, replay = await spec.service.command_receipt(
            connection, actor_id, "catalog:csv", key, command.model_dump(), CatalogCsvReport
        )
        if replay is not None:
            if spec == SETS:
                exposed = [r.record_id for r in replay.items if r.version or r.outcome == "created"]
                for group in chunks(exposed):
                    available = await connection.scalars(
                        spec.query(actor)
                        .with_only_columns(sets.c.set_id)
                        .where(sets.c.set_id.in_(group))
                    )
                    if set(available) != set(group):
                        raise DomainError(
                            403, "permission_denied", "Report exceeds current Set scope"
                        )
            return replay
        report, mutations = await plan(connection, spec, actor, command, lock=True)
        if report.preview_hash != command.preview_hash:
            raise DomainError(409, "stale_preview", "Data changed. Preview this file again")
        for row in sorted(report.items, key=lambda r: r.record_id):
            if row.row in mutations:
                await spec.service.mutate(
                    engine,
                    actor,
                    mutations[row.row],
                    uuid5(key, f"{spec.name}:{row.row}"),
                    software_version,
                    row.record_id if command.mode == "update" else None,
                    connection=connection,
                )
                row.outcome = "updated" if command.mode == "update" else "created"
        await connection.execute(
            update(spec.service.commands).where(*criteria).values(response=report.model_dump())
        )
        return report
