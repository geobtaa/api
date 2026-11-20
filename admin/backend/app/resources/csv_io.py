"""Batched CSV mutations and streaming, scoped Resource exchange."""

import csv
import io
import json
import sys
from collections import Counter, defaultdict
from itertools import chain
from typing import Any, Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import bindparam, delete, func, insert, select, text, update

from app.activity import activity
from app.csv_exchange import CsvInput, chunks
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources import csv_format, distribution_csv, editor, service, source_membership
from app.resources.models import distributions, evidence, imports, resources
from app.resources.schemas import DistributionEdit, ResourceUpdate
from app.resources.search import resource_visible
from app.resources.validation import SCHEMA, TYPES, normalize
from app.sets.models import commands, sets
from app.sets.schemas import SetID
from app.sets.service import authorize as authorize_sets
from app.sets.service import get_set


class CsvRequest(CsvInput):
    set_id: SetID | None = Field(
        default=None,
        description="Create in this Set or omit to import Resources without a Set. Scopes updates.",
    )
    mode: Literal["upsert", "create", "update", "add_links", "replace_links"] = "upsert"


class CsvCommit(CsvRequest):
    preview_hash: str = Field(pattern="^[a-f0-9]{64}$")
    confirmed: bool


class DistributionSummary(BaseModel):
    added: int
    removed: int
    relabeled: int
    reordered: bool


class CsvRow(BaseModel):
    row: int
    resource_id: str
    outcome: str
    values: dict[str, Any]
    supplied_fields: list[str]
    clear_fields: list[str]
    errors: list[str]
    set_id: str | None = None
    input_rows: list[int] = []
    link_changes: DistributionSummary | None = None
    warnings: list[str]
    changes: dict[str, dict[str, Any]]


class CsvPreview(BaseModel):
    batch_id: UUID | None = None
    preview_hash: str
    ready: int
    items: list[CsvRow]


def fields(actor):
    return {
        **{field["name"]: field for field in editor.contract(actor)["fields"]},
        "source_id": {"name": "source_id", "kind": "text"},
    }


def parse_rows(source, command, actor, *, saved_upload=False):
    """Yield parsed CSV rows without retaining the whole file; duplicate checks are separate."""
    csv.field_size_limit(sys.maxsize)
    definitions = fields(actor)
    allowed = {"id", "lock_version", "set_id", "distributions", "_csv_encoding", *definitions}
    allowed |= {name + "__clear" for name in [*definitions, "distributions"]}
    try:
        lines = iter(source)
        reader = csv.reader(chain([next(lines).lstrip("\ufeff")], lines), strict=True)
        original_header = next(reader)
        friendly_fields = {
            csv_format.field_name(name) for name in original_header if name in csv_format.ALIASES
        }
        header = [csv_format.field_name(name) for name in original_header]
        allowed |= csv_format.EVIDENCE
        if not saved_upload:
            csv_format.validate_header(header, columns(actor), friendly=bool(friendly_fields))
        elif "id" not in header:
            raise ValueError("Missing Resource ID column")
        if len(header) != len(set(header)) or set(header) - allowed:
            raise ValueError("Use unique supported column names, including id")
        editable_columns = set(definitions) - {"source_id"} | {"distributions"}
        blank_candidates = [name for name in header if name in editable_columns]
        found = False
        for index, cells in enumerate(reader, 1):
            row = {"row": index, "resource_id": "", "values": {}, "clear_fields": [], "errors": []}
            found = True
            if len(cells) != len(header):
                row["errors"].append("Cell count does not match the header")
                yield row
                continue
            raw = dict(zip(header, cells, strict=True))
            row["legacy_source"] = {
                name: value for name, value in raw.items() if name in csv_format.EVIDENCE and value
            }
            encoding = raw.get("_csv_encoding", "")
            if encoding not in {"", "apostrophe-v1", "geomg-v1"}:
                row["errors"].append("Unsupported CSV encoding")
            if encoding in {"apostrophe-v1", "geomg-v1"}:
                raw = {
                    name: value[1:] if value.startswith("'") else value
                    for name, value in raw.items()
                }
            if command.mode in {"update", "upsert"}:
                row["blank_fields"] = [name for name in blank_candidates if raw[name] == ""]
            row["resource_id"] = raw.get("id", "")
            row["lock_version"] = raw.get("lock_version", "")
            if not row["resource_id"].strip() or len(row["resource_id"]) > 512:
                row["errors"].append("Supply a Resource ID of at most 512 characters")
            if raw.get("set_id"):
                row["asserted_set"] = raw["set_id"]
            if command.set_id and raw.get("set_id") and raw["set_id"] != command.set_id:
                row["errors"].append("Set column must match the selected Set")
            for name in [*definitions, "distributions"]:
                value, clear = raw.get(name, ""), raw.get(name + "__clear", "")
                if clear not in {"", "true", "false"}:
                    row["errors"].append(f"{name}__clear: use true or false")
                if name == "source_id" and clear == "true":
                    row["errors"].append(
                        "source_id is derived from the managing Set and cannot be cleared"
                    )
                    continue
                if clear == "true":
                    if value != "":
                        row["errors"].append(f"{name}: cannot supply a value and clear it")
                    if name == "distributions":
                        row["distributions"] = []
                    else:
                        row["clear_fields"].append(name)
                if value == "":
                    continue
                try:
                    if not value.strip():
                        raise ValueError("whitespace-only cells are ambiguous")
                    kind = definitions.get(name, {}).get("kind")
                    if kind in {"list", "integer_list"} or name == "distributions":
                        if (
                            name in friendly_fields
                            and name != "distributions"
                            and not (encoding == "geomg-v1" and value.startswith("["))
                        ):
                            value = value.split("|")
                            if any(not part.strip() for part in value):
                                raise ValueError("empty pipe-separated values are ambiguous")
                            if kind == "integer_list":
                                value = [int(part) for part in value]
                        else:
                            value = json.loads(value)
                        if not isinstance(value, list):
                            raise ValueError("use a JSON array")
                    elif kind == "boolean":
                        if value not in {"true", "false"}:
                            raise ValueError("use true or false")
                        value = value == "true"
                    if name == "distributions":
                        links = [
                            DistributionEdit.model_validate(item).model_dump() for item in value
                        ]
                        if any(
                            link["distribution_type_id"] not in TYPES.values() for link in links
                        ):
                            raise ValueError("unknown Distribution type")
                        if len(
                            {(link["distribution_type_id"], link["url"]) for link in links}
                        ) != len(links):
                            raise ValueError("duplicate Distribution type/URL")
                        row[name] = links
                    elif name == "source_id":
                        row["source_id"] = value
                    else:
                        row["values"][name] = value
                except (ValueError, TypeError) as exc:
                    row["errors"].append(f"{name}: {exc}")
            yield row
        if not found:
            raise ValueError("Supply at least one data row")
    except (csv.Error, ValueError, StopIteration) as exc:
        raise DomainError(422, "invalid_csv", str(exc) or "CSV is empty") from exc


def parse(command, actor, *, saved_upload=False):
    if command.mode in {"add_links", "replace_links"}:
        return distribution_csv.parse(command.csv)
    rows = list(
        parse_rows(io.StringIO(command.csv, newline=""), command, actor, saved_upload=saved_upload)
    )
    ids = Counter(row["resource_id"] for row in rows)
    for row in rows:
        if ids[row["resource_id"]] > 1:
            row["errors"].append("Duplicate Resource ID in this batch")
    return rows


def create_record(row):
    record = {"id": row["resource_id"], **row["values"]}
    if "source_id" in row:
        record["source_id"] = row["source_id"]
    if row.get("legacy_source"):
        record["geomg_v1_source"] = row["legacy_source"]
    if "distributions" in row:
        references = {}
        uris = {value: key for key, value in TYPES.items()}
        for link in row["distributions"]:
            references.setdefault(uris[link["distribution_type_id"]], []).append(
                {
                    key: value
                    for key, value in link.items()
                    if key in {"url", "label"} and value is not None
                }
            )
        record["dct_references_s"] = json.dumps(references)
    return record


def update_command(row):
    version = row["lock_version"]
    if not version.isascii() or not version.isdigit() or int(version) < 1:
        raise ValueError(
            "Export the current Resources, keep the Lock Version column, "
            "and copy your edits into that file."
        )
    return ResourceUpdate(
        lock_version=int(version),
        values=row["values"],
        clear_fields=row["clear_fields"],
        **({"distributions": row["distributions"]} if "distributions" in row else {}),
    )


def authorize_csv(actor, command):
    resource_import = command.mode in {"create", "upsert"}
    standalone = resource_import and command.set_id is None
    service.authorize_import(actor, unassigned=standalone)
    if not resource_import and not editor.can_update(actor):
        raise DomainError(
            403, "permission_denied", "CSV updates require Resource update permission"
        )
    if not standalone:
        authorize_sets(actor)


async def plan_rows(connection, actor, command, rows):
    """Validate each row against its target and bind the result to the preview."""
    authorize_csv(actor, command)
    scope = await get_set(connection, actor, command.set_id) if command.set_id else None
    if scope and scope.status == "retired":
        raise DomainError(409, "retired", "Choose a non-retired Set")
    occupied = set()
    existing = {}
    saved_links = defaultdict(list)
    next_position = {}
    for chunk in chunks(rows):
        identifiers = [row["resource_id"] for row in chunk]
        if command.mode in {"create", "upsert"}:
            occupied.update(
                await connection.scalars(
                    select(resources.c.id).where(resources.c.id.in_(identifiers))
                )
            )
        if command.mode != "create" and editor.can_update(actor):
            query = (
                select(
                    resources,
                    sets.c.status.label("set_status"),
                    sets.c.source_id,
                    sets.c.lock_version.label("set_version"),
                )
                .outerjoin(sets, sets.c.set_id == resources.c.set_id)
                .where(resources.c.id.in_(identifiers), resource_visible(actor))
            )
            if command.mode == "upsert" and not {"sets:read", "sources:read"}.issubset(
                actor.permissions
            ):
                query = query.where(resources.c.set_id.is_(None))
            if scope:
                query = query.where(resources.c.set_id == scope.set_id)
            elif "sets:retired-read" not in actor.permissions:
                query = query.where(sets.c.status.is_distinct_from("retired"))
            records = (await connection.execute(query)).mappings().all()
            existing.update({record["id"]: record for record in records})
            identifiers = [record["id"] for record in records]
            links = (
                (
                    await connection.execute(
                        select(distributions)
                        .where(distributions.c.resource_id.in_(identifiers))
                        .order_by(distributions.c.position, distributions.c.id)
                    )
                )
                .mappings()
                .all()
            )
            for link in links:
                next_position[link["resource_id"]] = link["position"] + 1
                saved_links[link["resource_id"]].append(
                    {name: link[name] for name in ["distribution_type_id", "url", "label"]}
                )
    for row in rows:
        blank_fields = row.pop("blank_fields", [])
        target = existing.get(row["resource_id"])
        creating = command.mode == "create" or (
            command.mode == "upsert" and row["resource_id"] not in occupied
        )
        if creating and scope:
            row["errors"].extend(source_membership.assertion_errors(row, scope.source_id))
            row["set_id"] = scope.set_id
        elif not creating and target is not None:
            # The same blank cell is absent on create and clears a stored value on update.
            for name in blank_fields:
                if name == "distributions":
                    row["distributions"] = []
                elif name not in row["clear_fields"] and (
                    target[name] is not None or name == "dct_title_s"
                ):
                    row["clear_fields"].append(name)
            if command.mode == "upsert":
                row["matched_version"] = target["lock_version"]
                if not row["lock_version"]:
                    row["lock_version"] = str(target["lock_version"])
            row["set_id"] = target["set_id"]
            row["set_version"] = target["set_version"]
            row["errors"].extend(source_membership.assertion_errors(row, target["source_id"]))
            if row.get("asserted_set", target["set_id"]) != target["set_id"]:
                row["errors"].append("Set ID must match the current managing Set")

        row.update(
            outcome="invalid",
            changes={},
            warnings=[
                f"{name} is kept in upload history. Current settings are managed separately."
                for name in row.get("legacy_source", {})
            ],
            supplied_fields=[
                *row["values"],
                *(["distributions"] if "distributions" in row else []),
            ],
        )
        if row["errors"]:
            continue
        try:
            if creating:
                if row["clear_fields"]:
                    raise ValueError("Clear columns apply only to updates")
                if "gbl_mdVersion_s" not in row["values"]:
                    row["values"]["gbl_mdVersion_s"] = "Aardvark"
                    row["warnings"].append("Metadata Version defaults to Aardvark for new drafts.")
                record = create_record(row)
                record.pop("geomg_v1_source", None)
                _, _, errors, warnings = normalize(
                    record,
                    publication_required=set(SCHEMA["required"])
                    - csv_format.LEGACY_PUBLICATION_FIELDS.keys(),
                    publication_labels=csv_format.LABELS,
                )
                if errors:
                    outcome = "invalid"
                elif row["resource_id"] in occupied:
                    outcome = "skipped"
                else:
                    outcome = "create"
                if outcome == "skipped":
                    warnings.append("ID already exists; no existing Resource will be changed")
                row.update(outcome=outcome, errors=errors, warnings=row["warnings"] + warnings)
                row["changes"] = {
                    name: {"before": None, "after": value} for name, value in row["values"].items()
                }
                if "distributions" in row:
                    row["changes"]["distributions"] = {"before": [], "after": row["distributions"]}
            else:
                if target is None:
                    if command.mode == "update":
                        raise ValueError(
                            "No matching Resource in your selected scope. For a new record, "
                            "use the Resource CSV import page."
                        )
                    if command.mode == "upsert":
                        raise ValueError(
                            "This ID is unavailable for editing in your selected scope."
                        )
                    raise ValueError("Resource missing or unavailable in your selected scope")
                if command.mode in {"add_links", "replace_links"}:
                    row["next_position"] = next_position.get(row["resource_id"], 0)
                    row["lock_version"] = str(target["lock_version"])
                    row["distributions"] = distribution_csv.desired_links(
                        command.mode, row["distributions"], saved_links[row["resource_id"]]
                    )
                values, links = editor.prepare_changes(
                    target,
                    update_command(row),
                    saved_links[row["resource_id"]],
                )
                changes = {
                    name: {"before": target[name], "after": value} for name, value in values.items()
                }
                if links is not None:
                    if "distributions" in blank_fields and not links:
                        row["clear_fields"].append("distributions")
                    changes["distributions"] = {
                        "before": saved_links[row["resource_id"]],
                        "after": links,
                    }
                    if command.mode in {"add_links", "replace_links"}:
                        row["link_changes"] = distribution_csv.summarize(
                            saved_links[row["resource_id"]], links
                        )
                row.update(outcome="update", changes=changes)
        except DomainError as exc:
            row["outcome"] = (
                "unchanged"
                if exc.code == "no_changes"
                else "conflict"
                if exc.status == 409
                else "invalid"
            )
            if exc.code != "no_changes":
                row["errors"].append(
                    "Lock Version is stale. Export the current Resource and reapply your edits."
                    if exc.code == "stale_version"
                    else exc.message
                )
        except (ValueError, ValidationError) as exc:
            row["errors"].append(str(exc))
    result = {
        "items": rows,
        "ready": sum(row["outcome"] in {"create", "update"} for row in rows),
    }
    result["preview_hash"] = service.digest(
        {
            "request": command.model_dump(mode="json", exclude={"preview_hash", "confirmed"}),
            "set_version": scope.lock_version if scope else None,
            **result,
        }
    )
    return result


async def plan(connection, actor, command):
    return await plan_rows(connection, actor, command, parse(command, actor))


async def preview(engine, actor, command):
    async with engine.begin() as connection:
        return await plan(connection, actor, command)


async def current_owners(connection, actor, rows):
    owners = {}
    for group in chunks(rows):
        query = (
            select(resources.c.id, resources.c.set_id)
            .outerjoin(sets, resources.c.set_id == sets.c.set_id)
            .where(resource_visible(actor), resources.c.id.in_([r["resource_id"] for r in group]))
        )
        if "sets:retired-read" not in actor.permissions:
            query = query.where(sets.c.status.is_distinct_from("retired"))
        owners.update((await connection.execute(query)).tuples().all())
    return owners


async def authorize_report(connection, actor, report, command=None):
    # Intake receipts may include before-values from updates outside the intake queue.
    matched = [row for row in report["items"] if "matched_version" in row]
    if matched and not editor.can_update(actor):
        raise DomainError(403, "permission_denied", "Resource update permission required")
    if any(row.get("set_id") for row in matched):
        authorize_sets(actor)
    exposed = list(matched)
    if command is not None:
        for row in report["items"]:
            if "matched_version" in row:
                continue
            if row["outcome"] == "created" or (
                command.mode not in {"create", "upsert"}
                and (row.get("set_id") or row["outcome"] in {"updated", "unchanged"})
            ):
                exposed.append(row)
    owners = await current_owners(connection, actor, exposed)
    for row in exposed:
        identifier = row["resource_id"]
        intake_create = report.get("batch_id") and row["outcome"] == "created"
        original_owner = row.get("set_id", command.set_id if command else None)
        if identifier not in owners or (not intake_create and owners[identifier] != original_owner):
            raise DomainError(
                403, "permission_denied", "Import report is no longer available in this scope"
            )


async def commit(engine, actor, command, key, software_version):
    authorize_csv(actor, command)
    if not command.confirmed:
        raise DomainError(422, "confirmation_required", "Confirm the CSV preview")
    async with engine.begin() as connection:
        await connection.execute(text("SELECT pg_advisory_xact_lock(718443802)"))
        locked = set()
        if command.set_id:
            await get_set(connection, actor, command.set_id, lock=True)
            locked = {command.set_id}
        actor_id = await actor_identity(connection, actor)
        criteria = (
            commands.c.actor_id == actor_id,
            commands.c.operation == "resource:csv",
            commands.c.idempotency_key == key,
        )
        previous = (await connection.execute(select(commands).where(*criteria))).mappings().first()
        request_hash = service.digest(command.model_dump(mode="json"))
        if previous and previous["request_hash"] != request_hash:
            raise DomainError(
                409, "idempotency_conflict", "CSV key already used for different input"
            )
        # A committed upload already has validated rows, including historical file layouts.
        parsed = previous["response"]["items"] if previous else parse(command, actor)
        if not command.set_id and command.mode != "create":
            # Use the same sorted Set lock order as membership reassignment.
            owners = await current_owners(connection, actor, parsed)
            locked = {owner for owner in owners.values() if owner is not None}
            for group in chunks(sorted(locked)):
                await connection.execute(
                    select(sets.c.set_id)
                    .where(sets.c.set_id.in_(group))
                    .order_by(sets.c.set_id)
                    .with_for_update()
                )
            unassigned = sorted(identifier for identifier, owner in owners.items() if owner is None)
            for group in chunks(unassigned):
                await connection.execute(
                    select(resources.c.id)
                    .where(resources.c.id.in_(group))
                    .order_by(resources.c.id)
                    .with_for_update()
                )
        if previous:
            report = previous["response"]
            await authorize_report(connection, actor, report, command)
            return report
        # Lock the Set first, matching individual edit/import lock ordering.
        # The Set lock prevents concurrent Resource edits while validating/applying.
        result = await plan_rows(connection, actor, command, parsed)
        if result["preview_hash"] != command.preview_hash or any(
            r.get("set_id") and r["set_id"] not in locked for r in result["items"]
        ):
            raise DomainError(409, "stale_preview", "Data changed; preview the CSV again")
        if not command.set_id and (
            command.mode == "create" or any(r["outcome"] == "create" for r in result["items"])
        ):
            from app.resources.intake import save_batch

            await save_batch(connection, actor, actor_id, command, result, key, software_version)
        else:
            await apply_rows(connection, actor, actor_id, command, result, key, software_version)
        await connection.execute(
            insert(commands).values(
                actor_id=actor_id,
                operation="resource:csv",
                idempotency_key=key,
                request_hash=request_hash,
                response=result,
            )
        )
        return result


def columns(actor, format="technical"):
    names = list(fields(actor))
    if format == "geomg":
        ordered = [name for name in csv_format.PRIMARY.values() if name in names or name == "id"]
        ordered += [name for name in names if name not in ordered]
        ordered += ["set_id", "lock_version", "distributions", "_csv_encoding"]
        return [csv_format.LABELS[name] for name in ordered]
    return ["_csv_encoding", "id", "set_id", "lock_version", *names, "distributions"]


async def export(engine, actor, q="", set_id=None, ids=None, filters=None, format="technical"):
    from app.resources.copy_export import query, stream

    async for chunk in stream(
        engine, query(actor, columns(actor, format), q, set_id, filters, ids)
    ):
        yield chunk


async def apply_rows(
    connection, actor, actor_id, command, result, key, software_version, *, intake_batch_id=None
):
    """Execute database batches without a query/receipt per Resource."""
    ready = [row for row in result["items"] if row["outcome"] in {"create", "update"}]
    created = sum(row["outcome"] == "create" for row in ready)
    if created:
        await connection.execute(
            insert(imports).values(
                id=key,
                intake_batch_id=intake_batch_id,
                actor_id=actor_id,
                set_id=command.set_id,
                request_hash=service.digest(command.model_dump(mode="json")),
                response={"created": created, "csv": True},
            )
        )
    for chunk in chunks(ready):
        records, sources, links, events = [], [], [], []
        updates = defaultdict(list)
        replace_links = []
        replacements = {}
        for row in chunk:
            start_position = 0
            identifier = row["resource_id"]
            if row["outcome"] == "create":
                record = create_record(row)
                values, normalized_links, _, _ = normalize(record)
                records.append(
                    {
                        **values,
                        "set_id": command.set_id,
                        "created_by_actor_id": actor_id,
                        "publication_state": "draft",
                        "b1g_publication_state_s": "draft",
                        "import_id": str(key),
                    }
                )
                if "gbl_mdVersion_s" not in row["supplied_fields"]:
                    record.pop("gbl_mdVersion_s", None)
                sources.append(
                    {
                        "resource_id": identifier,
                        "import_id": key,
                        "source_record": record,
                        "warnings": row["warnings"],
                    }
                )
                desired_links = row.get("distributions", normalized_links)
                row["outcome"] = "created"
                details = {
                    "import_id": str(key),
                    "created": 1,
                    "skipped": 0,
                    "invalid": 0,
                    "resource_ids": [identifier],
                }
                action = "resources.imported"
            else:
                values = {
                    name: change["after"]
                    for name, change in row["changes"].items()
                    if name != "distributions"
                }
                names = tuple(sorted(values))
                updates[names].append(
                    {"target_id": identifier, **{"value_" + name: values[name] for name in names}}
                )
                desired_links = row["changes"].get("distributions", {}).get("after")
                if desired_links is not None:
                    if command.mode == "add_links":
                        start_position = row["next_position"]
                        existing_count = len(row["changes"]["distributions"]["before"])
                        desired_links = desired_links[existing_count:]
                    elif command.mode == "replace_links":
                        replacements[identifier] = desired_links
                        desired_links = None
                    else:
                        replace_links.append(identifier)
                row["outcome"] = "updated"
                action = "resource.updated"
                details = {
                    "resource_id": identifier,
                    "fields": sorted(row["changes"]),
                    "clear_fields": row["clear_fields"],
                    "lock_version": int(row["lock_version"]) + 1,
                }
            if desired_links:
                links.extend(
                    {
                        "resource_id": identifier,
                        "distribution_type_id": link["distribution_type_id"],
                        "url": link["url"],
                        "label": link.get("label"),
                        "position": position + start_position,
                        "import_id": str(key),
                    }
                    for position, link in enumerate(desired_links)
                )
            events.append(
                {
                    "id": uuid4(),
                    "set_id": row.get("set_id"),
                    "resource_id": identifier if row.get("set_id") is None else None,
                    "actor_id": actor_id,
                    "actor_display_name": actor.display_name,
                    "action": action,
                    "software_version": software_version,
                    "correlation_id": key,
                    "idempotency_key": uuid5(key, str(row["row"])),
                    "details": details,
                }
            )
        # SQLAlchemy executemany requires equal key sets; group sparse create rows.
        grouped = defaultdict(list)
        for record in records:
            grouped[tuple(sorted(record))].append(record)
        for group in grouped.values():
            await connection.execute(insert(resources), group)
        if sources:
            await connection.execute(insert(evidence), sources)
        for names, group in updates.items():
            await connection.execute(
                update(resources)
                .where(resources.c.id == bindparam("target_id"))
                .values(
                    **{name: bindparam("value_" + name) for name in names},
                    lock_version=resources.c.lock_version + 1,
                    updated_at=func.clock_timestamp(),
                    gbl_mdModified_dt=func.timezone("UTC", func.clock_timestamp()),
                ),
                group,
            )
        if replace_links:
            await connection.execute(
                delete(distributions).where(distributions.c.resource_id.in_(replace_links))
            )
        if replacements:
            await distribution_csv.replace_groups(connection, replacements, key)
        for group in chunks(links):
            await connection.execute(insert(distributions), group)
        if events:
            await connection.execute(insert(activity), events)
