"""New administrative tables only; no legacy Resource tables are managed here."""

from sqlalchemy import (
    ARRAY,
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
from sqlalchemy.dialects.postgresql import INTERVAL, JSONB

from app.activity import activity as activity
from app.persistence import actors as actors
from app.persistence import metadata as metadata

lifecycles = Table(
    "lifecycles",
    metadata,
    Column("lifecycle_id", Uuid, primary_key=True),
    Column("code", String(63), nullable=False, unique=True),
    Column("title", String(250), nullable=False),
    Column("status", Text, nullable=False, server_default="active"),
    Column("endpoint_url", Text),
    Column("represented_by_id", Text, ForeignKey("resources.id", name="lifecycle_representative")),
    Column("workflow_catalog_id", String(128), ForeignKey("workflow_catalog.workflow_id")),
    Column("source_description", Text, nullable=False, server_default=""),
    Column("admin_notes", Text, nullable=False, server_default=""),
    Column("tags", ARRAY(Text), nullable=False, server_default="{}"),
    Column("review_interval", INTERVAL),
    Column("harvest_interval", INTERVAL),
    Column("review_anchor_at", DateTime(timezone=True)),
    Column("harvest_anchor_at", DateTime(timezone=True)),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("created_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("updated_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    CheckConstraint(
        "code ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(code) >= 3", name="lifecycle_code"
    ),
    CheckConstraint("length(btrim(title)) > 0", name="lifecycle_title"),
    CheckConstraint("status IN ('active', 'paused', 'retired')", name="lifecycle_status"),
    CheckConstraint("lock_version > 0", name="lifecycle_version"),
    CheckConstraint("cardinality(tags) <= 20", name="lifecycle_tags"),
    Index("lifecycles_title_id", func.lower(Column("title")), "lifecycle_id"),
)

for name in ("review_interval", "harvest_interval"):
    lifecycles.append_constraint(
        CheckConstraint(
            f"{name} IS NULL OR ("
            f"extract(epoch FROM {name}) > 0 AND "
            f"extract(year FROM {name}) * 12 + extract(month FROM {name}) BETWEEN 0 AND 12000 AND "
            f"extract(day FROM {name}) BETWEEN 0 AND 7000 AND "
            f"extract(hour FROM {name}) = 0 AND extract(minute FROM {name}) = 0 AND "
            f"extract(second FROM {name}) = 0 AND "
            f"(extract(day FROM {name}) = 0 OR "
            f"(extract(year FROM {name}) = 0 AND extract(month FROM {name}) = 0)))",
            name=f"lifecycle_{name}",
        )
    )

# Durable command receipts make a lost HTTP response safely replayable.
commands = Table(
    "lifecycle_commands",
    metadata,
    Column("actor_id", Uuid, ForeignKey("actors.id"), primary_key=True),
    Column("operation", Text, primary_key=True),
    Column("idempotency_key", Uuid, primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("response", JSONB),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
