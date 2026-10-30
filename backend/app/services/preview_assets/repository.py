"""Publish validated manifests atomically, retaining the last successful result."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db.models import (
    distribution_types,
    resource_assets,
    resource_distributions,
    resource_preview_assets,
    resource_thumbnail_state,
    resources,
)

from .models import Manifest, Outcome, eligible, enabled, fingerprint


def record_signature(record):
    lower = {k.lower(): v for k, v in record.items()}
    keys = (
        "dct_references_s",
        "dct_accessrights_s",
        "publication_state",
        "gbl_suppressed_b",
        "locn_geometry",
        "dcat_bbox",
        "_preview_sources",
    )
    return fingerprint({k: lower.get(k) for k in keys})


def source_queries(resource_id):
    return (
        select(
            resource_assets.c.dct_references_uri_key.label("uri"),
            resource_assets.c.file_url.label("url"),
        )
        .where(resource_assets.c.resource_id == resource_id, resource_assets.c.thumbnail.is_(False))
        .order_by(resource_assets.c.position, resource_assets.c.id),
        select(distribution_types.c.distribution_uri.label("uri"), resource_distributions.c.url)
        .join(
            distribution_types,
            resource_distributions.c.distribution_type_id == distribution_types.c.id,
        )
        .where(resource_distributions.c.resource_id == resource_id)
        .order_by(resource_distributions.c.position, resource_distributions.c.id),
    )


def hydrate_sources(connection, record):
    record = dict(record)
    record["_preview_sources"] = [
        dict(row)
        for query in source_queries(record["id"])
        for row in connection.execute(query).mappings()
    ]
    return record


def next_active(previous, attempt: Manifest):
    if attempt.status == Outcome.READY:
        published = attempt.model_dump(mode="json")
        if (
            previous
            and attempt.thumbnail_status != Outcome.READY
            and previous.get("thumbnail_status") == "ready"
        ):
            for key in ("thumbnail_status", "thumbnail_key", "thumbnail_url"):
                published[key] = previous[key]
        return published
    return previous


def save_attempt(connection, resource_id, signature, attempt):
    row = (
        connection.execute(
            select(resource_preview_assets)
            .where(resource_preview_assets.c.resource_id == resource_id)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    current = (
        connection.execute(select(resources).where(resources.c.id == resource_id))
        .mappings()
        .first()
    )
    previous = row["active_manifest"] if row and row["record_signature"] == signature else None
    current = hydrate_sources(connection, current) if current else None
    if not current or not eligible(current) or record_signature(current) != signature:
        active = None
    else:
        active = next_active(previous, attempt)
    values = dict(
        resource_id=resource_id,
        record_signature=signature,
        status=attempt.status.value,
        active_manifest=active,
        last_attempt=attempt.model_dump(mode="json"),
        updated_at=datetime.now(timezone.utc),
    )
    connection.execute(
        insert(resource_preview_assets)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["resource_id"],
            set_={k: v for k, v in values.items() if k != "resource_id"},
        )
    )


async def published_for(resource_id, session):
    if not enabled():
        return None
    row = (
        (
            await session.execute(
                select(
                    resource_preview_assets,
                    resources.c.dct_accessRights_s,
                    resources.c.publication_state,
                    resources.c.gbl_suppressed_b,
                    resources.c.dct_references_s,
                    resources.c.locn_geometry,
                    resources.c.dcat_bbox,
                )
                .join(resources, resources.c.id == resource_preview_assets.c.resource_id)
                .where(resource_preview_assets.c.resource_id == resource_id)
            )
        )
        .mappings()
        .first()
    )
    if not row or not eligible(dict(row)):
        return None
    current = dict(row)
    current["_preview_sources"] = []
    for query in source_queries(resource_id):
        current["_preview_sources"].extend(
            dict(item) for item in (await session.execute(query)).mappings()
        )
    if row["record_signature"] != record_signature(current):
        return None
    manifest = row["active_manifest"] or row["last_attempt"]
    for dependency in (manifest or {}).get("dependencies", []):
        child = (
            (
                await session.execute(
                    select(resources).where(resources.c.id == dependency["resource_id"])
                )
            )
            .mappings()
            .first()
        )
        if not child or not eligible(dict(child)):
            return None
        child = dict(child)
        child["_preview_sources"] = []
        for query in source_queries(child["id"]):
            child["_preview_sources"].extend(
                dict(item) for item in (await session.execute(query)).mappings()
            )
        if record_signature(child) != dependency["signature"]:
            return None
    return manifest


async def attach_preview(resource, record, session=None):
    if not enabled() or not eligible(record):
        return
    from db.session import async_session

    if session is None:
        async with async_session() as owned:
            manifest = await published_for(str(record["id"]), owned)
    else:
        manifest = await published_for(str(record["id"]), session)
    from .geometry import metadata_coverage

    ui = resource.setdefault("meta", {}).setdefault("ui", {})
    ui["coverage"] = (
        manifest.get("coverage")
        if manifest and manifest.get("coverage")
        else metadata_coverage(record).model_dump(mode="json")
    )
    ui.setdefault("viewer", {})["geometry"] = ui["coverage"]["geometry"]
    if manifest and manifest.get("coverage") and not manifest.get("coverage_url"):
        ui.pop("static_map", None)
    if ui["coverage"]["kind"] == "unavailable":
        ui.pop("static_map", None)
    if manifest and manifest.get("coverage_url"):
        ui["static_map"] = manifest["coverage_url"]
    if manifest:
        ui["preview"] = {
            k: v for k, v in manifest.items() if k not in {"coverage", "thumbnail_key"}
        }
        # Curated and successful native thumbnails retain priority. Resolver URLs
        # may represent missing/failed captures and can use the prepared image.
        current = ui.get("thumbnail_url") or ""
        failed = bool(ui.get("thumbnail_placeholder"))
        if current and not ui.get("thumbnail_curated"):
            async with async_session() as state_session:
                state = (
                    await state_session.execute(
                        select(resource_thumbnail_state.c.state).where(
                            resource_thumbnail_state.c.resource_id == str(record["id"])
                        )
                    )
                ).scalar()
                failed = failed or state in {"failure", "placeheld"}
        if (
            manifest.get("thumbnail_status") == "ready"
            and not ui.get("thumbnail_curated")
            and (not current or failed or "/placeholder" in current)
        ):
            ui["thumbnail_url"] = manifest["thumbnail_url"]
            ui.pop("thumbnail_placeholder", None)
