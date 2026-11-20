"""Typed immutable Activity, retaining the historical physical table name."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence import metadata

MANAGED_SUBJECT = (
    "(set_id IS NULL AND source_id IS NULL AND lifecycle_id IS NOT NULL "
    "AND action NOT IN ('source.created', 'source.updated', 'set.created', 'set.updated', "
    "'set.deactivated', 'set.activated', 'set.retired', 'set.restored', "
    "'set.representative_changed', 'set.migrated')) OR "
    "(set_id IS NULL AND source_id IS NOT NULL AND lifecycle_id IS NULL "
    "AND action IN ('source.created', 'source.updated', "
    "'review.completed', 'harvest.completed') "
    "AND resource_id IS NULL AND workflow_id IS NULL "
    "AND workflow_version_id IS NULL AND job_id IS NULL) OR "
    "(set_id IS NOT NULL AND source_id IS NULL AND lifecycle_id IS NULL "
    "AND action NOT LIKE 'lifecycle.%' AND action NOT IN ('source.created', 'source.updated'))"
)

activity = Table(
    "lifecycle_activity_entries",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("lifecycle_id", Uuid, ForeignKey("lifecycles.lifecycle_id")),
    Column("source_id", String(128), ForeignKey("sources.source_id")),
    Column("set_id", String(128), ForeignKey("sets.set_id")),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("actor_display_name", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("outcome", Text, nullable=False, server_default="succeeded"),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("recorded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("origin", Text, nullable=False, server_default="geomg-admin"),
    Column("software_version", Text, nullable=False),
    Column("correlation_id", Uuid, nullable=False),
    Column("idempotency_key", Uuid, nullable=False),
    Column("reason", Text),
    Column("resource_id", Text, ForeignKey("resources.id", name="activity_resource_identity")),
    Column("details", JSONB, nullable=False),
    UniqueConstraint("actor_id", "lifecycle_id", "action", "idempotency_key"),
    CheckConstraint(
        "action IN ('lifecycle.created', 'lifecycle.updated', "
        "'resources.imported', 'resource.updated', 'resource.created', 'lifecycle.paused', "
        "'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored', "
        "'review.completed', 'harvest.completed', 'workflow.created', "
        "'workflow.updated', 'workflow.draft_created', 'workflow.activated', "
        "'validation.completed', 'lifecycle.representative_changed', 'resource.associated', "
        "'source.created', 'source.updated', 'set.created', 'set.updated', "
        "'set.deactivated', 'set.activated', 'set.retired', 'set.restored', "
        "'set.representative_changed', 'set.migrated')",
        name="activity_action",
    ),
    CheckConstraint(
        "outcome IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled', 'rejected')",
        name="activity_outcome",
    ),
    CheckConstraint(
        "CASE WHEN action = 'resource.created' THEN "
        "(resource_id IS NOT NULL AND source_id IS NULL AND lifecycle_id IS NULL "
        "AND workflow_id IS NULL AND workflow_version_id IS NULL AND job_id IS NULL) ELSE "
        + MANAGED_SUBJECT
        + " OR (set_id IS NULL AND source_id IS NULL AND lifecycle_id IS NULL "
        "AND resource_id IS NOT NULL AND workflow_id IS NULL AND job_id IS NULL "
        "AND action IN ('resources.imported','resource.updated')) END",
        name="activity_subject",
    ),
    UniqueConstraint(
        "actor_id", "source_id", "action", "idempotency_key", name="activity_source_replay"
    ),
    UniqueConstraint("actor_id", "set_id", "action", "idempotency_key", name="activity_set_replay"),
    Index("activity_set_time", "set_id", "occurred_at", "id"),
    Index("activity_source_time", "source_id", "occurred_at", "id"),
    Index("activity_lifecycle_time", "lifecycle_id", "occurred_at", "id"),
)
