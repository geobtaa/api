"""Shared native Set fixture for Resource, Workflow and job integration tests."""

from dataclasses import replace
from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert
from test_sets import BASE as BASE
from test_sets import EDITOR as SET_EDITOR
from test_sets import api as api

from app.identity.actors import actor_identity
from app.sources.models import sources

EDITOR = replace(SET_EDITOR, lifecycle_ids=None)


def headers(key=None):
    return {"Idempotency-Key": str(key or uuid4()), "X-GEOMG-Request": "1"}


async def create(client, **fields):
    # Parent identity is an explicit fixture, never inferred by application code.
    async with client._transport.app.state.database_engine.begin() as connection:
        actor_id = await actor_identity(connection, EDITOR)
        await connection.execute(
            insert(sources)
            .values(
                source_id="parent",
                title="Parent",
                created_by_actor_id=actor_id,
                updated_by_actor_id=actor_id,
            )
            .on_conflict_do_nothing()
        )
    values = {"set_id": str(uuid4()), "source_id": "parent", "title": "County maps", **fields}
    if "code" in values:
        values["legacy_code"] = values.pop("code")
    if "source_description" in values:
        values["description"] = values.pop("source_description")
    if isinstance(values.get("tags"), list):
        values["tags"] = "|".join(values["tags"])
    response = await client.post("/api/v1/admin/sets", headers=headers(), json=values)
    assert response.status_code == 201, response.text
    return response.json()
