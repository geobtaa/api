"""Immutable server-side Resource/version selections for consequential commands."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence import metadata

selections = Table(
    "resource_selections",
    metadata,
    Column("selection_id", Uuid, primary_key=True),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("idempotency_key", Uuid, nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("sealed", Boolean, nullable=False, server_default="false"),
    Column("query", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("actor_id", "idempotency_key"),
    CheckConstraint("octet_length(query::text) <= 1000000", name="selection_query_bound"),
)
selection_items = Table(
    "resource_selection_items",
    metadata,
    Column("selection_id", Uuid, ForeignKey("resource_selections.selection_id"), primary_key=True),
    Column("resource_id", String(512), primary_key=True),
    Column("lifecycle_id", Uuid, ForeignKey("lifecycles.lifecycle_id")),
    Column("set_id", String(128), ForeignKey("sets.set_id")),
    Column("resource_version", Integer, nullable=False),
)
