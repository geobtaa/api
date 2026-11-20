"""Durable commands, fenced attempts, bounded results and retained report metadata."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.activity import activity
from app.persistence import metadata
from app.workflows import models as workflow_models  # noqa: F401

jobs = Table(
    "jobs",
    metadata,
    Column("job_id", Uuid, primary_key=True),
    Column("lifecycle_id", Uuid, ForeignKey("lifecycles.lifecycle_id")),
    Column("set_id", String(128), ForeignKey("sets.set_id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("operation", Text, nullable=False),
    Column("idempotency_key", Uuid, nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("workflow_id", Uuid),
    Column("workflow_version_id", Uuid),
    Column("state", Text, nullable=False, server_default="queued"),
    Column("attempt_number", Integer, nullable=False, server_default="0"),
    Column("lease_token", Uuid),
    Column("lease_until", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    Column("software_version", String(100), nullable=False),
    UniqueConstraint("actor_id", "lifecycle_id", "operation", "idempotency_key"),
    UniqueConstraint("lifecycle_id", "job_id"),
    UniqueConstraint("actor_id", "set_id", "operation", "idempotency_key", name="job_set_receipt"),
    UniqueConstraint("set_id", "job_id", name="job_set_identity"),
    ForeignKeyConstraint(
        ["set_id", "workflow_id"],
        ["workflows.set_id", "workflows.workflow_id"],
        name="job_set_workflow",
    ),
    ForeignKeyConstraint(
        ["lifecycle_id", "workflow_id"], ["workflows.lifecycle_id", "workflows.workflow_id"]
    ),
    ForeignKeyConstraint(
        ["workflow_id", "workflow_version_id"],
        ["workflow_versions.workflow_id", "workflow_versions.version_id"],
    ),
    CheckConstraint(
        "(workflow_id IS NULL) = (workflow_version_id IS NULL)", name="job_workflow_pair"
    ),
    CheckConstraint("operation = 'resources.validate'", name="job_operation"),
    CheckConstraint(
        "state IN ('queued','running','succeeded','partially_succeeded',"
        "'failed','cancelled','rejected')",
        name="job_state",
    ),
    CheckConstraint("attempt_number BETWEEN 0 AND 3", name="job_attempt_limit"),
    CheckConstraint(
        "(state = 'running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)",
        name="job_lease",
    ),
    Index("jobs_claim", "state", "lease_until", "created_at", "job_id"),
)
items = Table(
    "job_items",
    metadata,
    Column("job_id", Uuid, ForeignKey("jobs.job_id"), primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("resource_id", String(512), nullable=False),
    Column("resource_version", Integer, nullable=False),
    Column("disposition", Text, nullable=False, server_default="pending"),
    Column("details", JSONB, nullable=False, server_default="{}"),
    UniqueConstraint("job_id", "resource_id"),
    CheckConstraint("position > 0 AND resource_version > 0", name="job_item_bounds"),
    CheckConstraint(
        "disposition IN ('pending','unchanged','conflicted',"
        "'invalid','failed','cancelled','rejected')",
        name="job_item_disposition",
    ),
    CheckConstraint("octet_length(details::text) <= 16384", name="job_item_details_bound"),
)
attempts = Table(
    "job_attempts",
    metadata,
    Column("job_id", Uuid, ForeignKey("jobs.job_id"), primary_key=True),
    Column("number", Integer, primary_key=True),
    Column("lease_token", Uuid, nullable=False, unique=True),
    Column("state", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    CheckConstraint(
        "state IN ('running','expired','succeeded','partially_succeeded',"
        "'failed','cancelled','rejected')",
        name="job_attempt_state",
    ),
)
artifacts = Table(
    "job_artifacts",
    metadata,
    Column("artifact_id", Uuid, primary_key=True),
    Column("job_id", Uuid, ForeignKey("jobs.job_id"), nullable=False, unique=True),
    Column("checksum", String(64), nullable=False),
    Column("byte_count", BigInteger, nullable=False),
    Column("content", LargeBinary),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("expired_at", DateTime(timezone=True)),
    CheckConstraint(
        "byte_count >= 0 AND (content IS NULL OR octet_length(content) = byte_count)",
        name="job_artifact_size",
    ),
)
activity.append_column(Column("job_id", Uuid))
activity.append_constraint(
    ForeignKeyConstraint(
        ["lifecycle_id", "job_id"],
        ["jobs.lifecycle_id", "jobs.job_id"],
        name="activity_job_lifecycle",
    )
)


artifact_chunks = Table(
    "job_artifact_chunks",
    metadata,
    Column("artifact_id", Uuid, ForeignKey("job_artifacts.artifact_id"), primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("content", LargeBinary, nullable=False),
    CheckConstraint(
        "position > 0 AND octet_length(content) BETWEEN 1 AND 65536", name="artifact_chunk_bound"
    ),
)

activity.append_constraint(
    ForeignKeyConstraint(
        ["set_id", "job_id"], ["jobs.set_id", "jobs.job_id"], name="activity_set_job"
    )
)
