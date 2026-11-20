"""Explicit local/test migrations. Production remains behind DEC-005/DEC-009."""

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.identity import models as identity_models  # noqa: F401
from app.jobs import models as job_models  # noqa: F401
from app.lifecycles.models import metadata
from app.resources import (  # noqa: F401
    association_models,
    bulk_models,
    intake_models,
    models,
    selection_models,  # noqa: F401
)
from app.sets import models as set_models  # noqa: F401
from app.sources import models as source_models  # noqa: F401
from app.work import models as work_models  # noqa: F401
from app.workflows import catalog as workflow_catalog  # noqa: F401
from app.workflows import models as workflow_models  # noqa: F401

if get_settings().app_env not in {"development", "test"}:
    raise RuntimeError("Production migrations require closed DEC-005/DEC-009 gates")


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=metadata,
        include_object=lambda obj, name, type_, reflected, compare_to: (
            not (type_ == "table" and reflected and name not in metadata.tables)
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run)
    finally:
        await engine.dispose()


if context.config.attributes.get("connection") is not None:
    run(context.config.attributes["connection"])
else:
    asyncio.run(migrate())
