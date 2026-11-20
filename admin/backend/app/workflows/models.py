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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.activity import activity
from app.persistence import metadata

process_types = Table(
    "workflow_process_types",
    metadata,
    Column("key", Text, primary_key=True),
    Column("label", Text, nullable=False),
    Column("definition", Text, nullable=False),
)
workflows = Table(
    "workflows",
    metadata,
    Column("workflow_id", Uuid, primary_key=True),
    Column("lifecycle_id", Uuid, ForeignKey("lifecycles.lifecycle_id")),
    Column("set_id", String(128), ForeignKey("sets.set_id"), nullable=False),
    Column("title", String(250), nullable=False),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("created_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("updated_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("lifecycle_id", "workflow_id"),
    UniqueConstraint("set_id", "workflow_id", name="workflow_set_identity"),
    CheckConstraint("length(btrim(title)) > 0", name="workflow_title"),
    CheckConstraint("lock_version > 0", name="workflow_lock_version"),
    Index("workflows_lifecycle_title", "lifecycle_id", "title", "workflow_id"),
    Index("workflows_set_title", "set_id", "title", "workflow_id"),
)
versions = Table(
    "workflow_versions",
    metadata,
    Column("version_id", Uuid, primary_key=True),
    Column("workflow_id", Uuid, ForeignKey("workflows.workflow_id"), nullable=False),
    Column("number", Integer, nullable=False),
    Column("state", Text, nullable=False, server_default="draft"),
    Column("checksum", String(64)),
    Column("created_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("activated_by_actor_id", Uuid, ForeignKey("actors.id")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("activated_at", DateTime(timezone=True)),
    UniqueConstraint("workflow_id", "number"),
    UniqueConstraint("workflow_id", "version_id"),
    CheckConstraint("number > 0", name="workflow_version_number"),
    CheckConstraint("state IN ('draft', 'active', 'superseded')", name="workflow_version_state"),
    CheckConstraint(
        "state = 'draft' OR (checksum IS NOT NULL AND activated_at IS NOT NULL "
        "AND activated_by_actor_id IS NOT NULL)",
        name="workflow_activation_evidence",
    ),
    Index(
        "workflow_one_active", "workflow_id", unique=True, postgresql_where=text("state = 'active'")
    ),
    Index(
        "workflow_one_draft", "workflow_id", unique=True, postgresql_where=text("state = 'draft'")
    ),
)
processes = Table(
    "workflow_processes",
    metadata,
    Column("process_id", Uuid, primary_key=True),
    Column("version_id", Uuid, ForeignKey("workflow_versions.version_id"), nullable=False),
    Column("position", Integer, nullable=False),
    Column("process_type", Text, ForeignKey("workflow_process_types.key"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("configuration_schema_version", Integer, nullable=False, server_default="1"),
    Column("configuration", JSONB, nullable=False),
    UniqueConstraint("version_id", "position"),
    CheckConstraint("position BETWEEN 1 AND 100", name="workflow_process_position"),
    CheckConstraint("configuration_schema_version = 1", name="workflow_configuration_version"),
    CheckConstraint(
        "jsonb_typeof(configuration) = 'object' AND octet_length(configuration::text) <= 8192",
        name="workflow_configuration_bound",
    ),
)


# Composite links ensure an Activity entry cannot point into another Lifecycle or Workflow.
def add_activity_links(activity):
    activity.append_column(Column("workflow_id", Uuid))
    activity.append_constraint(
        ForeignKeyConstraint(
            ["set_id", "workflow_id"],
            ["workflows.set_id", "workflows.workflow_id"],
            name="activity_set_workflow",
        )
    )
    activity.append_column(Column("workflow_version_id", Uuid))
    activity.append_constraint(
        ForeignKeyConstraint(
            ["lifecycle_id", "workflow_id"],
            ["workflows.lifecycle_id", "workflows.workflow_id"],
            name="activity_workflow_lifecycle",
        )
    )
    activity.append_constraint(
        ForeignKeyConstraint(
            ["workflow_id", "workflow_version_id"],
            ["workflow_versions.workflow_id", "workflow_versions.version_id"],
            name="activity_workflow_version",
        )
    )
    activity.append_constraint(
        CheckConstraint(
            "(workflow_id IS NULL) = (workflow_version_id IS NULL)",
            name="activity_workflow_pair",
        )
    )


add_activity_links(activity)
