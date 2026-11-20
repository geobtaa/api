"""Receive a named, one-way production Bridge batch for the isolated alpha catalog."""

import hashlib
import json
import secrets
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, DateTime, delete, func, insert, select, text, update
from sqlalchemy.exc import DataError, IntegrityError

from app.activity import activity
from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources import bridge
from app.resources.association_models import (
    resource_assets,
    resource_data_dictionaries,
    resource_data_dictionary_entries,
    resource_downloads,
    resource_licensed_accesses,
)
from app.resources.distributions import save_links
from app.resources.models import distributions, projection_requests, resources
from app.resources.service import digest
from app.sets.models import sets

machine = Actor(
    "kithe-production-bridge", "service_account", "Production Kithe Bridge", None, frozenset()
)
token_header = APIKeyHeader(name="X-GEOMG-Bridge-Token", auto_error=False)
CHILDREN = {
    "assets": resource_assets,
    "document_downloads": resource_downloads,
    "document_licensed_accesses": resource_licensed_accesses,
}
ADMIN_FIELDS = {
    "id",
    "publication_state",
    "set_id",
    "legacy_source_id",
    "lifecycle_id",
    "created_by_actor_id",
    "lock_version",
    "created_at",
    "updated_at",
}
STATES = {"draft", "published", "unpublished", "retired"}


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[dict] = Field(min_length=1, max_length=500)


class Item(BaseModel):
    resource_id: str | None
    outcome: str


class Result(BaseModel):
    batch_id: UUID
    items: list[Item]


async def authorized(request: Request, token: str | None = Depends(token_header)):
    settings = request.app.state.settings
    if not (
        settings.app_env == "dev2"
        and settings.bridge_token_sha256
        and token
        and settings.bridge_token_expires_at
        and datetime.now(timezone.utc) < settings.bridge_token_expires_at
        and secrets.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), settings.bridge_token_sha256
        )
    ):
        raise HTTPException(403, "Bridge credential unavailable")


def materialize(record):
    state = record.get("publication_state") or record.get("b1g_publication_state_s")
    if isinstance(state, list) and len(state) == 1:
        state = state[0]
    if state not in STATES:
        raise ValueError("Invalid publication state")
    values, links, warnings, children, dictionaries, entries = bridge.adapt(record)
    if any(w.startswith("Unknown reference URI") for w in warnings):
        raise ValueError("Unknown reference type")
    for name, raw in record.items():
        if name not in resources.c or name in ADMIN_FIELDS or name in values:
            continue
        column = resources.c[name]
        if raw is not None:
            if name == "import_id":
                raw = str(raw)
            elif isinstance(column.type, DateTime):
                raw = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if raw.tzinfo:
                    raw = raw.astimezone(timezone.utc).replace(tzinfo=None)
            elif isinstance(column.type, Date):
                raw = date.fromisoformat(raw)
            elif hasattr(column.type, "item_type") and not isinstance(raw, list):
                raw = [raw]
        values[name] = raw
    for key in ADMIN_FIELDS:
        values.pop(key, None)
    # The public API orders Distributions by position then row ID.
    by_target = {(link["distribution_type_id"], link["url"]): link for link in links}
    for index, item in enumerate(record["document_distributions"]):
        link = by_target.get((int(item["reference_type_id"]), item.get("url")))
        if link:
            link["position"] = index if item.get("position") is None else int(item["position"])
            if item.get("id") is not None:
                link["import_id"] = str(item["id"])
    values.update(publication_state=state, b1g_publication_state_s=state)
    return values, links, children, dictionaries, entries


async def replace_dictionaries(conn, rid, dictionaries, entries):
    await conn.execute(
        delete(resource_data_dictionaries).where(resource_data_dictionaries.c.resource_id == rid)
    )
    parents = {}
    for dictionary in dictionaries:
        parents[dictionary["legacy_document_data_dictionary_id"]] = await conn.scalar(
            insert(resource_data_dictionaries)
            .values(dictionary)
            .returning(resource_data_dictionaries.c.id)
        )
    await bridge.bulk(
        conn,
        resource_data_dictionary_entries,
        [
            {**entry, "resource_data_dictionary_id": parents[entry["resource_data_dictionary_id"]]}
            for entry in entries
        ],
    )


async def apply_record(conn, record, actor_id, version):
    rid = record.get("id")
    if not isinstance(rid, str) or not rid.strip() or len(rid) > 512:
        return "invalid"
    mapping = (
        (
            await conn.execute(
                text("SELECT set_id,origin FROM alpha_bridge_membership WHERE resource_id=:rid"),
                {"rid": rid},
            )
        )
        .mappings()
        .first()
    )
    if str(record.get("deleted", "")).lower() in {"true", "1", "yes", "on"}:
        return "deletion_review"
    if not mapping:
        return "intake"
    if mapping["origin"] == "pilot":
        return "pilot_review"
    status = await conn.scalar(
        select(sets.c.status).where(sets.c.set_id == mapping["set_id"]).with_for_update()
    )
    row = (
        (await conn.execute(select(resources).where(resources.c.id == rid).with_for_update()))
        .mappings()
        .first()
    )
    prior = (
        (
            await conn.execute(
                text("SELECT * FROM alpha_bridge_state WHERE resource_id=:rid"), {"rid": rid}
            )
        )
        .mappings()
        .first()
    )
    source_hash = digest({k: v for k, v in record.items() if k != "kithe_updated_at"})
    try:
        updated = datetime.fromisoformat(record["kithe_updated_at"].replace("Z", "+00:00"))
        if updated.tzinfo is None:
            return "invalid"
        if prior and updated < prior["source_updated_at"]:
            return "stale"
        if prior and prior["source_hash"] == source_hash:
            await conn.execute(
                text(
                    "UPDATE alpha_bridge_state SET source_updated_at=:updated "
                    "WHERE resource_id=:rid"
                ),
                {"updated": updated, "rid": rid},
            )
            return "unchanged"
        if (
            status == "retired"
            or row
            and (
                (not prior and (row.lock_version != 1 or row.created_by_actor_id != actor_id))
                or row.set_id != mapping["set_id"]
                or (prior and updated == prior["source_updated_at"])
            )
        ):
            return "conflict"
        if not all(
            isinstance(record.get(k), list)
            for k in (
                *CHILDREN,
                "document_distributions",
                "document_data_dictionaries",
                "document_data_dictionary_entries",
            )
        ):
            return "incomplete"
        values, links, children, dictionaries, entries = materialize(record)
        change_links = True
        change_dicts = True
        changed_tables = list(CHILDREN.values())
        if prior and row:
            # Compare against the last *accepted upstream* payload every time, even
            # after merging a clean upstream change on top of a staff revision.
            original = prior["source_record"]
            baseline, old_links, old_children, old_dicts, old_entries = materialize(original)
            values = {k: v for k, v in values.items() if v != baseline.get(k)}
            for name in (
                set(baseline) - set(record) - {"publication_state", "b1g_publication_state_s"}
            ):
                if name not in ADMIN_FIELDS and name not in values:
                    values[name] = None
            # The staff editor also stamps this field on every metadata edit.
            # Preserve a later local timestamp while merging unrelated fields.
            for name, new_value in values.items():
                if name == "gbl_mdModified_dt" and row[name] and row[name] != baseline.get(name):
                    values[name] = max(row[name], new_value) if new_value else row[name]
                    continue
                if row[name] != baseline.get(name) and row[name] != new_value:
                    return "conflict"
            changed_tables = [t for t in changed_tables if children[t] != old_children[t]]
            change_dicts = (dictionaries, entries) != (old_dicts, old_entries)
            change_links = links != old_links
            if change_links:
                current_links = (
                    await conn.execute(
                        select(
                            distributions.c.distribution_type_id,
                            distributions.c.url,
                            distributions.c.label,
                        )
                        .where(distributions.c.resource_id == rid)
                        .order_by(distributions.c.position, distributions.c.id)
                    )
                ).all()
                expected_links = [
                    (link["distribution_type_id"], link["url"], link.get("label"))
                    for link in sorted(old_links, key=lambda link: link["position"])
                ]
                if current_links != expected_links:
                    return "conflict"
    except ValueError, KeyError, TypeError, AttributeError, OverflowError:
        return "invalid"
    new_version = row.lock_version + 1 if row else 1
    if row:
        await conn.execute(
            update(resources)
            .where(resources.c.id == rid)
            .values(**values, lock_version=new_version, updated_at=func.now())
        )
    else:
        await conn.execute(
            insert(resources).values(
                **values, id=rid, set_id=mapping["set_id"], created_by_actor_id=actor_id
            )
        )
    if change_links:
        await save_links(conn, rid, links)
    for table in changed_tables:
        await conn.execute(delete(table).where(table.c.resource_id == rid))
        await bridge.bulk(conn, table, children[table])
    if change_dicts:
        await replace_dictionaries(conn, rid, dictionaries, entries)
    await conn.execute(
        text("""INSERT INTO alpha_bridge_state
        VALUES(:rid,:version,:hash,:updated,cast(:record AS jsonb))
        ON CONFLICT(resource_id) DO UPDATE SET resource_version=excluded.resource_version,
        source_hash=excluded.source_hash,source_updated_at=excluded.source_updated_at,
        source_record=excluded.source_record"""),
        {
            "rid": rid,
            "version": new_version,
            "hash": source_hash,
            "updated": updated,
            "record": json.dumps(record),
        },
    )
    key = uuid4()
    await conn.execute(
        insert(activity).values(
            id=uuid4(),
            set_id=mapping["set_id"],
            actor_id=actor_id,
            actor_display_name=machine.display_name,
            action="resources.imported",
            software_version=version,
            correlation_id=key,
            idempotency_key=key,
            details={
                "origin": "production-bridge",
                "resource_id": rid,
                "resource_version": new_version,
            },
        )
    )
    await conn.execute(
        insert(projection_requests).values(resource_id=rid, resource_version=new_version)
    )
    return "updated" if row else "created"


async def ingest(engine, batch, key, version):
    request_hash = digest(batch.model_dump())
    async with engine.begin() as conn:
        await conn.execute(select(func.pg_advisory_xact_lock(572911632)))
        prior = (
            (
                await conn.execute(
                    text("SELECT * FROM alpha_bridge_receipts WHERE batch_id=:key"), {"key": key}
                )
            )
            .mappings()
            .first()
        )
        if prior:
            if prior["request_hash"] != request_hash:
                raise DomainError(409, "idempotency_conflict", "Batch key already used")
            return Result.model_validate(prior["result"])
        actor_id = await actor_identity(conn, machine)
        result = Result(batch_id=key, items=[])
        # Sort Set locks before resource-level writes to match membership and bulk commands.
        ids = [r["id"] for r in batch.records if isinstance(r.get("id"), str)]
        await conn.execute(
            text("""SELECT s.set_id FROM sets s WHERE s.set_id IN
          (SELECT set_id FROM alpha_bridge_membership WHERE resource_id=ANY(:ids))
          ORDER BY s.set_id FOR UPDATE"""),
            {"ids": ids},
        )
        evidence = []
        for index, record in enumerate(batch.records):
            try:
                async with conn.begin_nested():
                    outcome = await apply_record(conn, record, actor_id, version)
            except DataError, IntegrityError:
                outcome = "invalid"
            rid = record.get("id") if isinstance(record.get("id"), str) else None
            result.items.append(Item(resource_id=rid, outcome=outcome))
            evidence.append(
                {
                    "key": key,
                    "ordinal": index,
                    "rid": rid,
                    "outcome": outcome,
                    "record": json.dumps(record),
                }
            )
        await conn.execute(
            text(
                "INSERT INTO alpha_bridge_receipts(batch_id,request_hash,result) "
                "VALUES(:key,:hash,cast(:result AS jsonb))"
            ),
            {"key": key, "hash": request_hash, "result": result.model_dump_json()},
        )
        await conn.execute(
            text(
                "INSERT INTO alpha_bridge_evidence "
                "VALUES(:key,:ordinal,:rid,:outcome,cast(:record AS jsonb))"
            ),
            evidence,
        )
        return result


router = APIRouter(prefix="/admin/intake", tags=["resources"])


@router.post(
    "/bridge-batches",
    operation_id="intake_accept_bridge_batch",
    response_model=Result,
    dependencies=[Depends(authorized), Depends(mutation_header)],
)
async def receive(batch: Batch, database: Database, key: RequestKey, request: Request):
    """Stage a production feed page and update only approved, unchanged aggregates."""
    return await ingest(database, batch, key, request.app.state.settings.app_version)


class ReviewItem(Item):
    batch_id: UUID
    ordinal: int
    recorded_at: datetime


@router.get(
    "/bridge-reviews", operation_id="intake_list_bridge_reviews", response_model=list[ReviewItem]
)
async def reviews(
    database: Database,
    actor: Annotated[Actor, Depends(require_permissions("resources:intake-manage"))],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List held feed items for authorized staff. Source payloads stay in private evidence."""
    if actor.kind != "user":
        raise HTTPException(403, "Staff intake permission required")
    async with database.connect() as conn:
        result = await conn.execute(
            text("""SELECT e.batch_id,e.ordinal,e.resource_id,e.outcome,r.recorded_at
          FROM alpha_bridge_evidence e JOIN alpha_bridge_receipts r USING(batch_id)
          LEFT JOIN alpha_bridge_membership m ON m.resource_id=e.resource_id
          LEFT JOIN resources current ON current.id=e.resource_id
          WHERE e.outcome IN ('invalid','conflict','pilot_review','intake',
                               'deletion_review','incomplete')
          AND (:global_scope OR (m.set_id = ANY(cast(:scope AS text[]))
               AND (current.id IS NULL OR current.set_id = ANY(cast(:scope AS text[])))))
          ORDER BY r.recorded_at DESC,e.batch_id,e.ordinal LIMIT :limit OFFSET :offset"""),
            {
                "global_scope": actor.set_ids is None,
                "scope": list(actor.set_ids or []),
                "limit": limit,
                "offset": offset,
            },
        )
        return result.mappings().all()
