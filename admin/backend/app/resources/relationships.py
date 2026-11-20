"""Live, scoped relationship navigation derived from canonical metadata arrays."""

from pydantic import BaseModel
from sqlalchemy import func, literal, select, union

from app.domain import DomainError
from app.resources.models import resources
from app.resources.search import resource_visible
from app.sets.models import sets

# Match data-api relationship_sync.py, including its canonical source inverse.
FAMILIES = (
    ("dct_relation_sm", "Related to", "Related to"),
    ("dct_isPartOf_sm", "Is part of", "Has part"),
    ("pcdm_memberOf_sm", "Member of", "Has member"),
    ("dct_source_sm", "Source", "Is source of"),
    ("dct_isVersionOf_sm", "Is version of", "Has version"),
    ("dct_replaces_sm", "Replaces", "Is replaced by"),
    ("dct_isReplacedBy_sm", "Is replaced by", "Replaces"),
)


class Relationship(BaseModel):
    relationship: str
    id: str
    title: str | None
    set_id: str | None


class RelationshipPage(BaseModel):
    items: list[Relationship]
    total: int
    offset: int
    limit: int


async def page(engine, actor, identifier, offset, limit):
    authorized = (
        select(
            resources.c.id,
            resources.c.dct_title_s,
            resources.c.set_id,
            *(resources.c[field] for field, _, _ in FAMILIES),
        )
        .outerjoin(sets, resources.c.set_id == sets.c.set_id)
        .where(resource_visible(actor))
        .cte("authorized_resources")
    )
    branches = []
    for field, forward, inverse in FAMILIES:
        branches.extend(
            [
                select(
                    literal(forward).label("relationship"),
                    func.unnest(authorized.c[field]).label("id"),
                ).where(authorized.c.id == identifier),
                select(literal(inverse).label("relationship"), authorized.c.id).where(
                    authorized.c[field].op("@>")([identifier])
                ),
            ]
        )
    edges = union(*branches).subquery("edges")
    query = (
        select(
            edges.c.relationship,
            edges.c.id,
            authorized.c.dct_title_s.label("title"),
            authorized.c.set_id,
        )
        .select_from(edges.outerjoin(authorized, edges.c.id == authorized.c.id))
        .where(edges.c.id != identifier, func.btrim(edges.c.id) != "")
    )
    async with engine.connect() as connection:
        if (
            await connection.scalar(select(authorized.c.id).where(authorized.c.id == identifier))
            is None
        ):
            raise DomainError(404, "not_found", "Resource not found")
        total = await connection.scalar(select(func.count()).select_from(query.subquery()))
        rows = (
            await connection.execute(
                query.order_by(edges.c.relationship, edges.c.id).offset(offset).limit(limit)
            )
        ).mappings()
        items = [dict(row, set_id=str(row["set_id"]) if row["set_id"] else None) for row in rows]
    return dict(items=items, total=total, offset=offset, limit=limit)
