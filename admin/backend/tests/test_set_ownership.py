from uuid import uuid4

import pytest
from alembic import command
from conftest import alembic_config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_api import make_settings

from app.main import create_app


def test_public_contracts_use_one_native_set_and_retire_lifecycle_routes():
    document = create_app(settings=make_settings()).openapi()
    paths = document["paths"]
    assert not any("lifecycles" in path for path in paths)
    assert "/api/v1/admin/resources/{resource_id}/set" in paths
    for name in ("ImportRequest", "ResourceResponse", "WorkflowCreate", "Submit"):
        fields = document["components"]["schemas"][name]["properties"]
        assert "set_id" in fields and "lifecycle_id" not in fields
        if name == "ResourceResponse":
            assert {option["type"] for option in fields["set_id"]["anyOf"]} == {"string", "null"}
        else:
            assert fields["set_id"]["type"] == "string"
        assert fields["set_id"].get("format") != "uuid"
    for name in ("Invitation", "AccountChange", "SessionActorResponse"):
        assert "lifecycle_ids" not in document["components"]["schemas"][name]["properties"]


@pytest.mark.integration
async def test_populated_legacy_cutover_fails_before_mutation(database_engine):
    actor_id, lifecycle_id = uuid4(), uuid4()
    async with database_engine.begin() as connection:
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0021"))
        await connection.execute(
            text("""INSERT INTO actors(id, subject_key, kind, display_name)
            VALUES (:id, 'legacy-owner', 'user', 'Legacy owner')"""),
            {"id": actor_id},
        )
        await connection.execute(
            text("""INSERT INTO lifecycles
            (lifecycle_id, code, title, created_by_actor_id, updated_by_actor_id)
            VALUES (:id, 'legacy-group', 'Unmapped legacy group', :actor, :actor)"""),
            {"id": lifecycle_id, "actor": actor_id},
        )
        await connection.execute(
            text("""INSERT INTO resources
            (id, lifecycle_id, publication_state, created_by_actor_id)
            VALUES ('legacy-map', :scope, 'draft', :actor)"""),
            {"scope": lifecycle_id, "actor": actor_id},
        )
    with pytest.raises(DBAPIError, match="Reviewed Set ownership cutover required"):
        async with database_engine.begin() as connection:
            await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "head"))
    async with database_engine.connect() as connection:
        assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0021"
        assert (
            await connection.scalar(
                text("SELECT lifecycle_id FROM resources WHERE id = 'legacy-map'")
            )
            == lifecycle_id
        )
        assert (
            await connection.scalar(
                text("""SELECT count(*) FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='resources'
            AND column_name='set_id'""")
            )
            == 0
        )
