"""Shared request/database boundaries independent of any catalog domain."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def engine(request: Request) -> AsyncEngine:
    if not hasattr(request.app.state, "database_engine"):
        request.app.state.database_engine = create_async_engine(
            request.app.state.settings.database_url, pool_pre_ping=True
        )
    return request.app.state.database_engine


def mutation_header(
    x_geomg_request: Annotated[
        Literal["1"], Header(description="Required CSRF protection header; send 1.")
    ],
):
    """Validate the literal header before a mutation; missing/invalid values return 422."""


Database = Annotated[AsyncEngine, Depends(engine)]
RequestKey = Annotated[
    UUID,
    Header(alias="Idempotency-Key", description="Keep this UUID when retrying the same request"),
]
