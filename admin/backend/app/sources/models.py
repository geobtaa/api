"""Source identity is independent of Lifecycle and Aardvark Resource identity."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence import metadata

sources = Table(
    "sources",
    metadata,
    Column("source_id", String(128), primary_key=True),
    Column("title", String(250), nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("landing_page", String(2048)),
    Column("admin_notes", Text, nullable=False, server_default=""),
    Column("legacy_code", String(128)),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("created_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("updated_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    CheckConstraint("source_id ~ '^[A-Za-z0-9_-]{1,128}$'", name="source_id_format"),
    CheckConstraint("length(btrim(title)) > 0", name="source_title"),
    CheckConstraint("length(description) <= 5000", name="source_description_bound"),
    CheckConstraint("length(admin_notes) <= 10000", name="source_notes_bound"),
    CheckConstraint("lock_version > 0", name="source_version"),
    Index("sources_title_id", func.lower(Column("title")), "source_id"),
    Index("sources_legacy_code", "legacy_code", "source_id"),
)

commands = Table(
    "source_commands",
    metadata,
    Column("actor_id", Uuid, ForeignKey("actors.id"), primary_key=True),
    Column("operation", Text, primary_key=True),
    Column("idempotency_key", Uuid, primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("response", JSONB),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
