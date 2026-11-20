"""Previewed bulk edits, confirmed executions and immutable per-Resource evidence."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence import metadata

actions = Table(
    "resource_bulk_actions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("selection_id", Uuid, ForeignKey("resource_selections.selection_id"), nullable=False),
    Column("reverts", Uuid, ForeignKey("resource_bulk_actions.id")),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("actor_name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("key", Uuid, nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("fields", JSONB, nullable=False),
    UniqueConstraint("actor_id", "key"),
    Index("resource_bulk_history", "actor_id", "created_at", "id"),
)
items = Table(
    "resource_bulk_items",
    metadata,
    Column("action_id", Uuid, ForeignKey(actions.c.id), primary_key=True),
    Column("resource_id", Text, primary_key=True),
    Column("set_id", String(128), ForeignKey("sets.set_id")),
    Column("before_version", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("changes", JSONB, nullable=False),
    CheckConstraint("before_version > 0"),
    CheckConstraint("status IN ('ready','unchanged','conflict','read_only','active_job')"),
)
executions = Table(
    "resource_bulk_executions",
    metadata,
    Column("action_id", Uuid, ForeignKey(actions.c.id), primary_key=True),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("actor_name", Text, nullable=False),
    Column(
        "applied_at", DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    ),
)
results = Table(
    "resource_bulk_results",
    metadata,
    Column("action_id", Uuid, ForeignKey(executions.c.action_id), primary_key=True),
    Column("resource_id", Text, primary_key=True),
    Column("status", Text, nullable=False),
    Column("after_version", Integer),
    ForeignKeyConstraint(["action_id", "resource_id"], [items.c.action_id, items.c.resource_id]),
    CheckConstraint("status IN ('changed','unchanged','conflict','read_only','active_job')"),
    CheckConstraint("(status = 'changed') = (after_version IS NOT NULL)"),
)
