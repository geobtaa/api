"""Shared descriptive workflow lookup stays distinct from executable definitions."""

import pytest
from sqlalchemy import select

from app.sets.schemas import SetCreate
from app.workflows.catalog import catalog


@pytest.mark.integration
async def test_migrated_catalog_ids_and_shared_references(database_engine):
    async with database_engine.connect() as conn:
        ids = (await conn.scalars(select(catalog.c.workflow_id))).all()
    assert len(ids) == 14
    assert "py_ogm_aardvark" in ids
    assert "py_umedia" not in ids
    assert catalog.name == "workflow_catalog"
    assert "workflow_catalog_id" in SetCreate.model_fields


async def test_catalog_rejects_unknown_value_and_accepts_clear():
    from unittest.mock import AsyncMock

    import pytest

    from app.domain import DomainError
    from app.workflows.catalog import require_catalog

    connection = AsyncMock()
    connection.scalar.return_value = None
    await require_catalog(connection, None)
    connection.scalar.assert_not_called()
    with pytest.raises(DomainError) as error:
        await require_catalog(connection, "py_umedia")
    assert error.value.status == 422
    assert error.value.code == "unknown_workflow"
    connection.scalar.return_value = "py_ogm_aardvark"
    await require_catalog(connection, "py_ogm_aardvark")
