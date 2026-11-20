"""Bounded legacy-code reads for reviewed Set reassignment; Source comes from Set."""

from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.resources import search
from app.resources.models import evidence, resources
from app.sets.membership import authorize
from app.sets.models import sets
from app.sets.schemas import SetID


class SourceCandidate(BaseModel):
    id: str
    set_id: SetID
    lock_version: int
    source_id: str
    b1g_code_s: str | None
    code_origin: str | None
    editable: bool


class SourceCandidatePage(BaseModel):
    items: list[SourceCandidate]
    next_cursor: str | None


async def candidates(engine, actor, after, limit, set_id=None):
    authorize(actor, "resources:associate")
    raw_code = evidence.c.source_record["b1g_code_s"]
    evidence_code = case((func.jsonb_typeof(raw_code) == "string", raw_code.astext))
    # Bridge and JSON imports deliberately retain administrative legacy codes as evidence.
    # A populated relational value takes precedence; neither path changes the evidence.
    code = func.coalesce(resources.c.b1g_code_s, evidence_code)
    statement = (
        select(
            resources.c.id,
            resources.c.set_id,
            resources.c.lock_version,
            sets.c.source_id,
            code.label("b1g_code_s"),
            case(
                (resources.c.b1g_code_s.is_not(None), "resource"),
                (evidence_code.is_not(None), "import_evidence"),
            ).label("code_origin"),
            ((resources.c.publication_state == "draft") & (sets.c.status != "retired")).label(
                "editable"
            ),
        )
        .join(sets, resources.c.set_id == sets.c.set_id)
        .outerjoin(evidence, resources.c.id == evidence.c.resource_id)
        .where(search.predicate(actor, set_id=set_id))
        .order_by(resources.c.id)
        .limit(limit + 1)
    )
    if after is not None:
        statement = statement.where(resources.c.id > after)
    async with engine.connect() as connection:
        rows = (await connection.execute(statement)).mappings().all()
    return {
        "items": rows[:limit],
        "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
    }
