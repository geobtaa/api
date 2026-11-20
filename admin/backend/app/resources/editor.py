"""Shared compact editor contract and selective draft mutations."""

from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import ARRAY, Boolean, Integer, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.activity import activity
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources.create import can_create
from app.resources.distributions import save_links
from app.resources.models import distributions, projection_requests, resources
from app.resources.schemas import ResourceDetailResponse
from app.resources.search import resource_visible
from app.resources.service import detail, digest
from app.resources.validation import DESCRIPTIVE_B1G, SCHEMA, TYPES, VOCABULARY, normalize
from app.sets.models import commands, sets
from app.sets.service import visible

GROUPS = {
    "Description": [
        "dct_title_s",
        "dct_alternative_sm",
        "dct_description_sm",
        "gbl_resourceClass_sm",
        "gbl_resourceType_sm",
        "dct_format_s",
        "dct_language_sm",
        "gbl_displayNote_sm",
        "gbl_mdVersion_s",
    ],
    "People & subjects": [
        "dct_creator_sm",
        "dct_publisher_sm",
        "schema_provider_s",
        "dct_subject_sm",
        "dcat_theme_sm",
        "dcat_keyword_sm",
    ],
    "Place & time": [
        "dct_spatial_sm",
        "locn_geometry",
        "dcat_bbox",
        "dcat_centroid",
        "dct_temporal_sm",
        "dct_issued_s",
        "gbl_indexYear_im",
        "gbl_dateRange_drsim",
        "gbl_georeferenced_b",
    ],
    "Rights": [
        "dct_accessRights_s",
        "dct_rights_sm",
        "dct_rightsHolder_sm",
        "dct_license_sm",
    ],
    "Relationships": [
        "dct_relation_sm",
        "pcdm_memberOf_sm",
        "dct_isPartOf_sm",
        "dct_source_sm",
        "dct_isVersionOf_sm",
        "dct_replaces_sm",
        "dct_isReplacedBy_sm",
    ],
    "Additional metadata": [
        "dct_identifier_sm",
        "gbl_fileSize_s",
        "gbl_wxsIdentifier_s",
        *sorted(DESCRIPTIVE_B1G),
    ],
}
LABELS = {
    "dct_title_s": "Title",
    "dct_alternative_sm": "Alternative titles",
    "dct_description_sm": "Descriptions",
    "gbl_resourceClass_sm": "Resource classes",
    "gbl_resourceType_sm": "Resource types",
    "dct_format_s": "Format",
    "dct_language_sm": "Languages",
    "gbl_displayNote_sm": "Display notes",
    "gbl_mdVersion_s": "Metadata version",
    "dct_creator_sm": "Creators",
    "dct_publisher_sm": "Publishers",
    "schema_provider_s": "Provider",
    "dct_subject_sm": "Subjects",
    "dcat_theme_sm": "Themes",
    "dcat_keyword_sm": "Keywords",
    "dct_spatial_sm": "Places",
    "locn_geometry": "Geometry",
    "dcat_bbox": "Bounding box",
    "dcat_centroid": "Centroid",
    "dct_temporal_sm": "Temporal coverage",
    "dct_issued_s": "Date issued",
    "gbl_indexYear_im": "Index years",
    "gbl_dateRange_drsim": "Date ranges",
    "gbl_georeferenced_b": "Georeferenced",
    "dct_accessRights_s": "Access rights",
    "dct_rights_sm": "Rights",
    "dct_rightsHolder_sm": "Rights holders",
    "dct_license_sm": "Licenses",
    "dct_identifier_sm": "Identifiers",
    "dct_relation_sm": "Related Resources",
    "pcdm_memberOf_sm": "Member of",
    "dct_isPartOf_sm": "Part of",
    "dct_source_sm": "Sources",
    "dct_isVersionOf_sm": "Version of",
    "dct_replaces_sm": "Replaces",
    "dct_isReplacedBy_sm": "Replaced by",
    "gbl_fileSize_s": "File size",
    "gbl_wxsIdentifier_s": "Service layer identifier",
    "b1g_image_ss": "Image URL",
    "b1g_geonames_sm": "GeoNames URIs",
    "b1g_language_sm": "Language labels",
    "b1g_creatorID_sm": "Creator identifiers",
    "b1g_dct_conformsTo_sm": "Conforms to",
    "b1g_dcat_spatialResolutionInMeters_sm": "Spatial resolution in meters",
    "b1g_geodcat_spatialResolutionAsText_sm": "Spatial resolution description",
    "b1g_dct_provenanceStatement_sm": "Provenance statements",
    "b1g_dct_provenance_sm": "Provenance",
    "b1g_dcat_spatialResolutionInMeters_s": "Spatial resolution (legacy scalar)",
    "b1g_localCollectionLabel_sm": "Local collection labels",
}
EDITABLE = {name for names in GROUPS.values() for name in names}


def can_update(actor):
    return actor.kind == "user" and {"resources:read", "resources:update"}.issubset(
        actor.permissions
    )


def can_bulk_edit(actor):
    return can_update(actor) and "resources:bulk-update" in actor.permissions


def contract(actor):
    fields = []
    for section, names in GROUPS.items():
        for name in names:
            column = resources.c[name]
            kind = (
                "integer_list"
                if isinstance(column.type, ARRAY) and isinstance(column.type.item_type, Integer)
                else "list"
                if isinstance(column.type, ARRAY)
                else "boolean"
                if isinstance(column.type, Boolean)
                else "text"
            )
            fields.append(
                {
                    "name": name,
                    "label": LABELS[name],
                    "section": section,
                    "kind": kind,
                    "required": name == "dct_title_s",
                    "choices": SCHEMA["properties"].get(name, {}).get("enum", []),
                    "multiline": name
                    in {
                        "dct_description_sm",
                        "gbl_displayNote_sm",
                        "locn_geometry",
                        "dct_rights_sm",
                    },
                }
            )
    return {
        "fields": fields,
        "sections": [*GROUPS, "Distributions"],
        "distribution_types": VOCABULARY,
        "can_update": can_update(actor),
        "can_create": can_create(actor),
        "can_choose_set": {"sets:read", "sources:read"}.issubset(actor.permissions),
        "can_bulk_edit": can_bulk_edit(actor),
        "maximum_values": 1000,
    }


async def edit(
    engine,
    actor,
    identifier,
    command,
    key,
    software_version,
    *,
    dry_run=False,
    published=False,
    preview_id=None,
):
    if not can_update(actor):
        raise DomainError(
            403, "permission_denied", "Resource editing requires staff update permission"
        )
    unknown = (set(command.values) | set(command.clear_fields)) - EDITABLE
    if unknown:
        raise DomainError(
            422, "invalid_fields", "Fields are not editable: " + ", ".join(sorted(unknown))
        )
    if set(command.values) & set(command.clear_fields):
        raise DomainError(422, "ambiguous_clear", "Do not supply and clear the same field")
    if "dct_title_s" in command.clear_fields:
        raise DomainError(422, "required_field", "Title cannot be cleared")
    payload = command.model_dump(mode="json", exclude_unset=True)
    request_hash = digest(payload)
    async with engine.begin() as connection:
        # All writers take the managing Set before the Resource, matching imports,
        # reassignment and retirement. A joined FOR UPDATE has no such lock order.
        ownership = (
            await connection.execute(
                select(resources.c.set_id)
                .outerjoin(sets, resources.c.set_id == sets.c.set_id)
                .where(resources.c.id == identifier, resource_visible(actor))
            )
        ).first()
        if ownership is None:
            raise DomainError(404, "not_found", "Resource not found")
        set_id = ownership.set_id
        if set_id is not None:
            await connection.execute(
                select(sets.c.set_id)
                .where(sets.c.set_id == set_id, visible(actor))
                .with_for_update()
            )
        row = (
            (
                await connection.execute(
                    select(resources, sets.c.status.label("set_status"))
                    .outerjoin(sets, resources.c.set_id == sets.c.set_id)
                    .where(
                        resources.c.id == identifier,
                        resources.c.set_id == set_id,
                        resource_visible(actor),
                    )
                    .with_for_update(of=resources)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(409, "stale_version", "Resource association changed. Reload it")
        if published:
            if "resources:edit-published" not in actor.permissions:
                raise DomainError(
                    403, "permission_denied", "Published Resource editing permission required"
                )
            if (
                not set_id
                or row["publication_state"] != "published"
                or row["gbl_suppressed_b"]
                or row["set_status"] == "retired"
            ):
                raise DomainError(
                    409, "read_only", "Choose a visible published Resource in a non-retired Set"
                )
            actor_id = await actor_identity(connection, actor)
            preview_operation = f"published-preview:{identifier}"
            preview_hash = digest([set_id, payload])
            if not dry_run:
                proof = await connection.scalar(
                    select(commands.c.request_hash).where(
                        commands.c.actor_id == actor_id,
                        commands.c.operation == preview_operation,
                        commands.c.idempotency_key == preview_id,
                    )
                )
                if proof != preview_hash:
                    raise DomainError(
                        409, "invalid_preview", "Preview these changes before confirming"
                    )
        if not dry_run:
            if not published:
                actor_id = await actor_identity(connection, actor)
            criteria = (
                commands.c.actor_id == actor_id,
                commands.c.operation
                == f"{'published-edit' if published else 'resource:update'}:{identifier}",
                commands.c.idempotency_key == key,
            )
            receipt = (
                (await connection.execute(select(commands).where(*criteria))).mappings().first()
            )
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise DomainError(
                        409,
                        "idempotency_conflict",
                        "This request key was used for different changes",
                    )
                return ResourceDetailResponse.model_validate(receipt["response"])
            prior_activity = await connection.scalar(
                select(activity.c.id).where(
                    activity.c.actor_id == actor_id,
                    activity.c.set_id == row["set_id"],
                    activity.c.action == "resource.updated",
                    activity.c.idempotency_key == key,
                )
            )
            if prior_activity is not None:
                raise DomainError(
                    409, "idempotency_conflict", "This request key was used for another Resource"
                )
        old = (
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
        values, links = prepare_changes(row, command, old, published=published)
        if published:
            candidate = {**row, **values}
            missing = [name for name in SCHEMA["required"] if not candidate.get(name)]
            if missing:
                raise DomainError(
                    422,
                    "publication_incomplete",
                    "Missing publication fields: " + ", ".join(missing),
                )
        if dry_run:
            changes = {
                name: {"before": row[name], "after": value} for name, value in values.items()
            }
            if links is not None:
                changes["distributions"] = {"before": [dict(item) for item in old], "after": links}
            if published:
                preview_id = uuid4()
                await connection.execute(
                    insert(commands).values(
                        actor_id=actor_id,
                        operation=preview_operation,
                        idempotency_key=preview_id,
                        request_hash=preview_hash,
                        response={},
                    )
                )
                return {"preview_id": preview_id, "changes": jsonable_encoder(changes)}
            return jsonable_encoder(changes)
        await connection.execute(
            update(resources)
            .where(resources.c.id == identifier)
            .values(
                **values,
                lock_version=row["lock_version"] + 1,
                updated_at=func.clock_timestamp(),
                gbl_mdModified_dt=func.timezone("UTC", func.clock_timestamp()),
            )
        )
        if links is not None:
            await save_links(
                connection, identifier, [{**link, "position": i} for i, link in enumerate(links)]
            )
        await connection.execute(
            insert(activity).values(
                id=uuid4(),
                set_id=row["set_id"],
                resource_id=identifier if row["set_id"] is None else None,
                actor_id=actor_id,
                actor_display_name=actor.display_name,
                action="resource.updated",
                software_version=software_version,
                correlation_id=key,
                idempotency_key=key,
                details={
                    "resource_id": identifier,
                    "fields": [*sorted(values), *(["distributions"] if links is not None else [])],
                    "clear_fields": sorted(command.clear_fields),
                    "lock_version": row["lock_version"] + 1,
                },
            )
        )
        if published:
            await connection.execute(
                insert(projection_requests).values(
                    resource_id=identifier, resource_version=row["lock_version"] + 1
                )
            )
        # Read on the same transaction so success evidence and the saved view agree.
        result = jsonable_encoder(await detail(engine, actor, identifier, connection=connection))
        await connection.execute(
            pg_insert(commands).values(
                actor_id=actor_id,
                operation=f"{'published-edit' if published else 'resource:update'}:{identifier}",
                idempotency_key=key,
                request_hash=request_hash,
                response=result,
            )
        )
    return result


def prepare_changes(row, command, old, *, published=False):
    """Validate selective changes against a locked row or preview snapshot."""
    if "dct_title_s" in command.clear_fields:
        raise DomainError(422, "required_field", "Title cannot be cleared")
    if (
        row["publication_state"] != ("published" if published else "draft")
        or row["set_status"] == "retired"
    ):
        raise DomainError(409, "read_only", "Only drafts in non-retired Sets can be edited")
    if row["lock_version"] != command.lock_version:
        raise DomainError(
            409,
            "stale_version",
            "This Resource changed. Load the latest version and review your draft before retrying.",
        )
    values, _, errors, _ = normalize(
        {"id": row["id"], "dct_title_s": row["dct_title_s"], **command.values}
    )
    values = {name: values[name] for name in command.values if name in values}
    for name, value in command.values.items():
        if isinstance(value, str) and value and not value.strip():
            errors.append(f"{LABELS[name]}: whitespace-only text is not an explicit clear")
        if (
            value != row[name]
            and isinstance(value, list)
            and any(isinstance(item, str) and not item.strip() for item in value)
        ):
            errors.append(f"{LABELS[name]}: remove blank entries; use an empty list for no values")
        choices = SCHEMA["properties"].get(name, {}).get("enum", [])
        if choices and value not in choices and value != row[name]:
            errors.append(f"{LABELS[name]}: choose one of {', '.join(choices)}")
    if errors:
        raise DomainError(422, "validation_error", "; ".join(errors))
    values.update({name: None for name in command.clear_fields})
    values = {name: value for name, value in values.items() if row[name] != value}
    links = None
    if command.distributions is not None:
        links = [link.model_dump() for link in command.distributions]
        keys = [(link["distribution_type_id"], link["url"]) for link in links]
        if len(set(keys)) != len(keys) or any(
            link["distribution_type_id"] not in TYPES.values() for link in links
        ):
            raise DomainError(
                422,
                "invalid_distributions",
                "Choose known Distribution types and unique type/URL pairs",
            )
        if [dict(item) for item in old] == links:
            links = None
    if not values and links is None:
        raise DomainError(422, "no_changes", "No changed values to save")
    return values, links
