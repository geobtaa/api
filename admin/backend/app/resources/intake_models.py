"""Intake drafts have uploader scope until promoted into managed Resources."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence import metadata

batches = Table(
    "resource_intake_batches",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("receipt_key", Uuid, nullable=False),
    Column("headings", JSONB, nullable=False),
    Column("original_csv", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("actor_id", "receipt_key"),
    Index("intake_owner_date", "actor_id", "created_at"),
)
drafts = Table(
    "resource_intake_drafts",
    metadata,
    Column("batch_id", Uuid, ForeignKey(batches.c.id), primary_key=True),
    Column("row_number", Integer, primary_key=True),
    Column("resource_id", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("cells", JSONB, nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("catalog_id", Text, ForeignKey("resources.id"), unique=True),
    Column("assigned_import", Uuid, ForeignKey("resource_imports.id")),
    CheckConstraint("row_number > 0"),
    CheckConstraint("version > 0"),
)
events = Table(
    "resource_intake_activity",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("batch_id", Uuid, ForeignKey(batches.c.id), nullable=False),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("action", Text, nullable=False),
    CheckConstraint("action IN ('saved','edited','assigned')"),
    Column("details", JSONB, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
