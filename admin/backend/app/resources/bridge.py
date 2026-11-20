"""Local create-only Bridge aggregate import with atomic page receipts."""

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ARRAY, DateTime, Integer, String, insert, select, text

from app.activity import activity
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources.association_models import (
    resource_assets,
    resource_data_dictionaries,
    resource_data_dictionary_entries,
    resource_downloads,
    resource_licensed_accesses,
)
from app.resources.models import distributions, evidence, imports, resources
from app.resources.service import authorize_import, digest
from app.resources.validation import VOCABULARY, normalize
from app.sets.models import sets
from app.sets.schemas import SetID
from app.sets.service import get_set


class BridgeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: SetID
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class BridgeOutcome(BaseModel):
    row: int
    resource_id: str | None
    outcome: str
    errors: list[str] = []


class BridgeResult(BaseModel):
    import_id: UUID
    created: int
    items: list[BridgeOutcome]


BY_ID = {v["id"]: v for v in VOCABULARY}
BY_NAME = {v["name"]: v for v in VOCABULARY}


def nested(record, key):
    value = record.get(key) or []
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise ValueError(f"{key} must be an array of objects")
    return value


def clean(table, row):
    """Validate database-bound legacy values before the page transaction."""
    result = {}
    for key, value in row.items():
        column = table.c[key]
        if value is None:
            if not column.nullable and column.server_default is None:
                raise ValueError(f"{table.name}.{key} is required")
            continue
        if isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if value.tzinfo:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
        elif isinstance(column.type, Integer):
            value = int(value)
            if not -(2**31) <= value < 2**31:
                raise ValueError(f"{table.name}.{key} is outside integer range")
        elif isinstance(column.type, String):
            value = value if isinstance(value, str) else json.dumps(value)
            if column.type.length and len(value) > column.type.length:
                raise ValueError(f"{table.name}.{key} exceeds column length")
        result[key] = value
    return result


def adapt(record):
    candidate = {k: v for k, v in record.items() if k in resources.c and v is not None}
    # Legacy source IDs are evidence, not an approved Source mapping.
    candidate.pop("source_id", None)
    for key, value in list(candidate.items()):
        if isinstance(resources.c[key].type, ARRAY) and not isinstance(value, list):
            candidate[key] = [value]
    if isinstance(candidate.get("dct_title_s"), list):
        candidate["dct_title_s"] = next(iter(candidate["dct_title_s"]), "")
    rid = candidate.get("id")
    links = []
    if "document_distributions" in record:
        for row in nested(record, "document_distributions"):
            type_id = int(row["reference_type_id"])
            if type_id not in BY_ID:
                raise ValueError(f"Unknown Distribution type {type_id}; source retained in report")
            links.append((type_id, row.get("url"), row.get("label")))
        refs = {}
    else:
        raw = candidate.get("dct_references_s") or "{}"
        refs = json.loads(raw) if isinstance(raw, str) else raw
        if refs == []:
            refs = {}
        if not isinstance(refs, dict):
            raise ValueError("Legacy references must be an object or empty array")
    download_type = BY_NAME["download"]["id"]
    if not any(t == download_type for t, _, _ in links):
        for row in nested(record, "document_downloads"):
            url = row.get("url") or row.get("value")
            if isinstance(url, str) and url.startswith(("https://", "http://")):
                links.append((download_type, url, row.get("label")))
    for asset in nested(record, "assets"):
        key = asset.get("dct_references_uri_key")
        kind = BY_NAME.get(key) or next((v for v in VOCABULARY if v["uri"] == key), None)
        url = (asset.get("file") or {}).get("url")
        if kind and url:
            links.append((kind["id"], url, asset.get("label")))
    seen = set()
    for type_id, url, label in links:
        if (type_id, url) in seen:
            continue
        seen.add((type_id, url))
        refs.setdefault(BY_ID[type_id]["uri"], []).append({"url": url, "label": label})
    candidate["dct_references_s"] = json.dumps(refs)
    values, normalized_links, errors, warnings = normalize(candidate)
    if errors:
        raise ValueError("; ".join(errors))
    children = defaultdict(list)
    for row in nested(record, "document_downloads"):
        children[resource_downloads].append(
            clean(
                resource_downloads,
                dict(
                    resource_id=rid,
                    label=row.get("label"),
                    value=row.get("value") or row.get("url"),
                    position=row.get("position") or 0,
                    import_download_id=str(row.get("id", "")),
                ),
            )
        )
    for row in nested(record, "document_licensed_accesses"):
        children[resource_licensed_accesses].append(
            clean(
                resource_licensed_accesses,
                dict(
                    resource_id=rid,
                    institution_code=row.get("institution_code"),
                    access_url=row.get("access_url") or row.get("url"),
                    legacy_friendlier_id=row.get("friendlier_id"),
                ),
            )
        )
    for row in nested(record, "assets"):
        file = row.get("file") or {}
        meta = file.get("metadata") or {}
        children[resource_assets].append(
            clean(
                resource_assets,
                dict(
                    resource_id=rid,
                    bridge_asset_id=str(row.get("id", "")),
                    bridge_parent_id=str(row.get("parent_id", "")),
                    friendlier_id=row.get("friendlier_id"),
                    title=row.get("title"),
                    label=row.get("label"),
                    thumbnail=bool(row.get("thumbnail")),
                    dct_references_uri_key=row.get("dct_references_uri_key"),
                    position=row.get("position") or 0,
                    file_url=file.get("url"),
                    file_mime_type=meta.get("mime_type"),
                    **{
                        f"file_{k}": meta.get(k)
                        for k in ("size", "width", "height", "md5", "sha1", "sha512")
                    },
                ),
            )
        )
    dictionaries = []
    for row in nested(record, "document_data_dictionaries"):
        dictionaries.append(
            clean(
                resource_data_dictionaries,
                dict(
                    resource_id=rid,
                    legacy_document_data_dictionary_id=int(row["id"]),
                    name=row.get("name"),
                    description=row.get("description"),
                    staff_notes=row.get("staff_notes"),
                    tags=row.get("tags") or "",
                    position=row.get("position") or 0,
                ),
            )
        )
    entries = []
    ids = {d["legacy_document_data_dictionary_id"] for d in dictionaries}
    for row in nested(record, "document_data_dictionary_entries"):
        parent = int(row["document_data_dictionary_id"])
        if parent not in ids:
            raise ValueError("Dictionary entry has no parent in this Resource payload")
        entries.append(
            clean(
                resource_data_dictionary_entries,
                dict(
                    resource_data_dictionary_id=parent,
                    legacy_document_data_dictionary_entry_id=int(row["id"]),
                    field_name=row.get("field_name"),
                    position=row.get("position") or 0,
                    **{
                        k: row.get(k)
                        for k in (
                            "field_type",
                            "values",
                            "definition",
                            "definition_source",
                            "parent_field_name",
                        )
                    },
                ),
            )
        )
    return values, normalized_links, warnings, children, dictionaries, entries


async def bulk(connection, table, rows):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(sorted(row))].append(row)
    for group in groups.values():
        for offset in range(0, len(group), 500):
            await connection.execute(insert(table), group[offset : offset + 500])


async def commit(engine, actor, command, key, version):
    authorize_import(actor)
    request_hash = digest(command.model_dump(mode="json"))
    async with engine.begin() as connection:
        await connection.execute(text("SELECT pg_advisory_xact_lock(718443802)"))
        await get_set(connection, actor, command.set_id)
        await connection.execute(
            select(sets.c.set_id).where(sets.c.set_id == command.set_id).with_for_update(read=True)
        )
        scope = await get_set(connection, actor, command.set_id)
        if scope.status == "retired":
            raise DomainError(409, "retired", "Choose a non-retired Set")
        actor_id = await actor_identity(connection, actor)
        prior = (
            (await connection.execute(select(imports).where(imports.c.id == key)))
            .mappings()
            .first()
        )
        if prior:
            if prior["actor_id"] != actor_id or prior["request_hash"] != request_hash:
                raise DomainError(409, "idempotency_conflict", "Import key already used")
            return BridgeResult.model_validate(prior["response"])
        ids = [r.get("id") for r in command.records if isinstance(r.get("id"), str)]
        existing = set(
            (
                await connection.execute(select(resources.c.id).where(resources.c.id.in_(ids)))
            ).scalars()
        )
        counts = Counter(ids)
        outcomes, prepared = [], []
        for index, record in enumerate(command.records):
            rid = record.get("id")
            outcome = BridgeOutcome(
                row=index + 1, resource_id=rid if isinstance(rid, str) else None, outcome="created"
            )
            if isinstance(rid, str) and rid in existing:
                outcome.outcome = "existing"
            elif str(record.get("deleted", "")).lower() in {"true", "1", "yes"}:
                outcome.outcome = "source_deleted"
            else:
                try:
                    if isinstance(rid, str) and counts[rid] > 1:
                        raise ValueError("Duplicate ID within Bridge batch")
                    prepared.append((index, record, adapt(record)))
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    outcome.outcome = "invalid"
                    outcome.errors = [str(exc)]
            outcomes.append(outcome)
        result = BridgeResult(import_id=key, created=len(prepared), items=outcomes)
        await connection.execute(
            insert(imports).values(
                id=key,
                actor_id=actor_id,
                set_id=command.set_id,
                request_hash=request_hash,
                response=result.model_dump(mode="json"),
            )
        )
        resource_rows, evidence_rows, link_rows = [], [], []
        all_children = defaultdict(list)
        for _index, record, (
            values,
            links,
            warnings,
            children,
            _dictionaries,
            _entries,
        ) in prepared:
            rid = values["id"]
            resource_rows.append(
                dict(
                    values,
                    set_id=command.set_id,
                    created_by_actor_id=actor_id,
                    publication_state="draft",
                    b1g_publication_state_s="draft",
                    import_id=str(key),
                )
            )
            evidence_rows.append(
                dict(resource_id=rid, import_id=key, source_record=record, warnings=warnings)
            )
            link_rows.extend(dict(link, resource_id=rid, import_id=str(key)) for link in links)
            for table, rows in children.items():
                all_children[table].extend(rows)
        await bulk(connection, resources, resource_rows)
        await bulk(connection, evidence, evidence_rows)
        await bulk(connection, distributions, link_rows)
        for table, rows in all_children.items():
            await bulk(connection, table, rows)
        for _, _, (_, _, _, _, dictionaries, entries) in prepared:
            mapping = {}
            for dictionary in dictionaries:
                new_id = await connection.scalar(
                    insert(resource_data_dictionaries)
                    .values(dictionary)
                    .returning(resource_data_dictionaries.c.id)
                )
                mapping[dictionary["legacy_document_data_dictionary_id"]] = new_id
            await bulk(
                connection,
                resource_data_dictionary_entries,
                [
                    dict(
                        entry,
                        resource_data_dictionary_id=mapping[entry["resource_data_dictionary_id"]],
                    )
                    for entry in entries
                ],
            )
        await connection.execute(
            insert(activity).values(
                id=uuid4(),
                set_id=command.set_id,
                actor_id=actor_id,
                actor_display_name=actor.display_name,
                action="resources.imported",
                software_version=version,
                correlation_id=key,
                idempotency_key=key,
                details={
                    "import_id": str(key),
                    "origin": "kithe-bridge",
                    "created": result.created,
                    "skipped": sum(i.outcome != "created" for i in outcomes),
                    "invalid": sum(i.outcome == "invalid" for i in outcomes),
                },
            )
        )
    return result
