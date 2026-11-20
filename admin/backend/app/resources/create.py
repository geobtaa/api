"""Create one staff-authored catalog draft with an atomic receipt and Activity."""

from uuid import uuid4

from sqlalchemy import insert, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.activity import activity
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.resources.models import resources
from app.resources.schemas import CreatedResource
from app.resources.search import resource_visible
from app.resources.service import resource_query
from app.resources.validation import normalize
from app.sets.models import commands
from app.sets.service import command_receipt, get_set


def can_create(actor):
    return actor.kind == "user" and {"resources:read", "resources:create"}.issubset(
        actor.permissions
    )


async def create_draft(engine, actor, command, key, software_version):
    if not can_create(actor):
        raise DomainError(403, "permission_denied", "Staff Resource creation permission required")
    record = {"id": command.id, "dct_title_s": command.title, "gbl_mdVersion_s": "Aardvark"}
    if command.description and command.description.strip():
        record["dct_description_sm"] = [command.description]
    values, _, errors, _ = normalize(record)
    if errors:
        raise DomainError(422, "validation_error", "; ".join(errors))
    async with engine.begin() as connection:
        # Imports use this same lock between their ID check and insertion.
        await connection.execute(text("SELECT pg_advisory_xact_lock(718443802)"))
        scope = (
            await get_set(connection, actor, command.set_id, lock=True) if command.set_id else None
        )
        actor_id = await actor_identity(connection, actor)
        criteria, prior = await command_receipt(
            connection, actor_id, "resource:create", key, command.model_dump(), CreatedResource
        )
        if prior:
            visible = await connection.scalar(
                resource_query()
                .with_only_columns(resources.c.id)
                .where(resources.c.id == prior.id, resource_visible(actor))
            )
            if visible is None:
                raise DomainError(404, "not_found", "Resource not found")
            return prior
        if scope and scope.status == "retired":
            raise DomainError(409, "retired", "Choose a non-retired Set")
        identifier = await connection.scalar(
            pg_insert(resources)
            .values(
                **values,
                set_id=command.set_id,
                created_by_actor_id=actor_id,
                publication_state="draft",
                b1g_publication_state_s="draft",
            )
            .on_conflict_do_nothing(index_elements=[resources.c.id])
            .returning(resources.c.id)
        )
        if identifier is None:
            raise DomainError(
                409, "id_unavailable", "This Resource ID is unavailable. Choose another ID."
            )
        await connection.execute(
            insert(activity).values(
                id=uuid4(),
                resource_id=identifier,
                set_id=command.set_id,
                actor_id=actor_id,
                actor_display_name=actor.display_name,
                action="resource.created",
                software_version=software_version,
                correlation_id=key,
                idempotency_key=key,
                details={"resource_id": identifier, "lock_version": 1},
            )
        )
        result = CreatedResource(id=identifier)
        await connection.execute(
            update(commands).where(*criteria).values(response=result.model_dump())
        )
    return result
