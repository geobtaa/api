"""Scoped, paginated reads of Resource association families."""

from sqlalchemy import func, select

from app.domain import DomainError
from app.resources.association_models import FAMILIES, resource_data_dictionaries
from app.resources.models import resources
from app.resources.search import resource_visible
from app.sets.models import sets


async def page(engine, actor, identifier, family, offset, limit):
    if actor.kind != "user" or not {"resources:read", "resources:update"}.issubset(
        actor.permissions
    ):
        raise DomainError(
            403, "permission_denied", "Association reads require staff Resource editor access"
        )
    table = FAMILIES[family]
    if family == "dictionary-entries":
        source = table.join(
            resource_data_dictionaries,
            table.c.resource_data_dictionary_id == resource_data_dictionaries.c.id,
        )
        resource_id = resource_data_dictionaries.c.resource_id
    else:
        source = table
        resource_id = table.c.subject_id if family == "relationships" else table.c.resource_id
    scope = (resources.c.id == identifier) & resource_visible(actor)
    query = (
        select(table)
        .select_from(
            source.join(resources, resource_id == resources.c.id).outerjoin(
                sets, resources.c.set_id == sets.c.set_id
            )
        )
        .where(scope)
    )
    ordering = [table.c.position, table.c.id] if "position" in table.c else [table.c.id]
    async with engine.connect() as connection:
        exists = await connection.scalar(
            select(resources.c.id).outerjoin(sets, resources.c.set_id == sets.c.set_id).where(scope)
        )
        if exists is None:
            raise DomainError(404, "not_found", "Resource not found")
        total = await connection.scalar(select(func.count()).select_from(query.subquery()))
        rows = (
            (await connection.execute(query.order_by(*ordering).offset(offset).limit(limit)))
            .mappings()
            .all()
        )
    return {"items": [dict(row) for row in rows], "total": total, "offset": offset, "limit": limit}
