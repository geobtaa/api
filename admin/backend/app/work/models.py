"""Each recurrence is a durable occurrence, with immutable completion evidence."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
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

maintenance = Table(
    "set_maintenance",
    metadata,
    Column("set_id", String(128), ForeignKey("sets.set_id"), primary_key=True),
    Column("work_type", String(16), primary_key=True),
    Column("interval", String(16), nullable=False),
    Column("next_due_on", Date),
    Column("enabled", Boolean, nullable=False, server_default="true"),
    Column("assignee_id", Uuid, ForeignKey("actors.id")),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("work_type IN ('review', 'ingest')", name="maintenance_work_type"),
    CheckConstraint(
        "interval ~ '^P[1-9][0-9]{0,2}[DWMY]$|^P1000[DWMY]$'", name="maintenance_interval"
    ),
    CheckConstraint("lock_version > 0", name="maintenance_version"),
)

tasks = Table(
    "work_tasks",
    metadata,
    Column("task_id", Uuid, primary_key=True),
    Column("set_id", String(128), ForeignKey("sets.set_id"), nullable=False),
    Column("work_type", String(16), nullable=False),
    Column("title", String(250), nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("status", String(16), nullable=False, server_default="open"),
    Column("due_on", Date, nullable=False),
    Column("planned_on", Date),
    Column("assignee_id", Uuid, ForeignKey("actors.id")),
    Column("recurring", Boolean, nullable=False, server_default="false"),
    Column("predecessor_id", Uuid, ForeignKey("work_tasks.task_id"), unique=True),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("created_by_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("completion_recorded_at", DateTime(timezone=True)),
    Column("completed_by_id", Uuid, ForeignKey("actors.id")),
    Column("completion_summary", Text),
    Column("evidence", JSONB, nullable=False, server_default="[]"),
    Column("processed_count", Integer, nullable=False, server_default="0"),
    Column("changed_count", Integer, nullable=False, server_default="0"),
    CheckConstraint("work_type IN ('review','ingest','other')", name="task_work_type"),
    CheckConstraint(
        "status IN ('open','in_progress','blocked','completed','cancelled')", name="task_status"
    ),
    CheckConstraint("length(btrim(title)) BETWEEN 1 AND 250", name="task_title"),
    CheckConstraint("lock_version > 0", name="task_version"),
    CheckConstraint(
        "NOT recurring OR work_type IN ('review','ingest')", name="task_recurrence_type"
    ),
    CheckConstraint(
        "processed_count >= 0 AND changed_count BETWEEN 0 AND processed_count", name="task_counts"
    ),
    CheckConstraint(
        "(status = 'completed' AND completed_at IS NOT NULL AND completion_recorded_at IS NOT NULL "
        "AND completed_by_id IS NOT NULL AND length(btrim(completion_summary)) > 0 "
        "AND completed_at <= completion_recorded_at) OR "
        "(status <> 'completed' AND completed_at IS NULL AND completion_recorded_at IS NULL "
        "AND completed_by_id IS NULL AND completion_summary IS NULL)",
        name="task_completion",
    ),
    Index("tasks_queue", "status", "due_on", "task_id"),
    Index("tasks_set_due", "set_id", "due_on"),
    Index("tasks_completed", "completed_at", "task_id"),
    Index("tasks_assignee", "assignee_id", "status", "due_on"),
    Index(
        "one_open_recurrence",
        "set_id",
        "work_type",
        unique=True,
        postgresql_where=Column("recurring")
        & Column("status").in_(["open", "in_progress", "blocked"]),
    ),
)

events = Table(
    "work_task_events",
    metadata,
    Column("event_id", Uuid, primary_key=True),
    Column("task_id", Uuid, ForeignKey("work_tasks.task_id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("actor_name", Text, nullable=False),
    Column("action", String(32), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("recorded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("details", JSONB, nullable=False),
    Index("task_event_time", "task_id", "recorded_at", "event_id"),
)

periods = Table(
    "work_periods",
    metadata,
    Column("period_id", Uuid, primary_key=True),
    Column("name", String(120), nullable=False, unique=True),
    Column("starts_on", Date, nullable=False),
    Column("ends_on", Date, nullable=False),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("created_by_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("ends_on >= starts_on", name="period_range"),
    CheckConstraint("length(btrim(name)) > 0", name="period_name"),
    CheckConstraint("lock_version > 0", name="period_version"),
)
