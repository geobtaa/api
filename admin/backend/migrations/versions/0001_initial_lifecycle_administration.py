"""Initial Lifecycle administration

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "actors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('user', 'service_account', 'system')", name="actors_kind"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "subject_key", name="actors_subject_key"),
    )
    op.create_table(
        "lifecycle_commands",
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actors.id"],
        ),
        sa.PrimaryKeyConstraint("actor_id", "operation", "idempotency_key"),
    )
    op.create_table(
        "lifecycles",
        sa.Column("lifecycle_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=63), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("source_description", sa.Text(), server_default="", nullable=False),
        sa.Column("admin_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("tags", sa.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("review_interval", postgresql.INTERVAL(), nullable=True),
        sa.Column("harvest_interval", postgresql.INTERVAL(), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_actor_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "code ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(code) >= 3", name="lifecycle_code"
        ),
        sa.CheckConstraint("status IN ('active', 'paused', 'retired')", name="lifecycle_status"),
        sa.CheckConstraint("cardinality(tags) <= 20", name="lifecycle_tags"),
        sa.CheckConstraint(
            "harvest_interval IS NULL OR (extract(epoch FROM harvest_interval) > 0 AND "
            "extract(year FROM harvest_interval) * 12 + extract(month FROM "
            "harvest_interval) BETWEEN 0 AND 12000 AND extract(day FROM "
            "harvest_interval) BETWEEN 0 AND 7000 AND extract(hour FROM "
            "harvest_interval) = 0 AND extract(minute FROM harvest_interval) = 0 AND "
            "extract(second FROM harvest_interval) = 0 AND (extract(day FROM "
            "harvest_interval) = 0 OR (extract(year FROM harvest_interval) = 0 AND "
            "extract(month FROM harvest_interval) = 0)))",
            name="lifecycle_harvest_interval",
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name="lifecycle_title"),
        sa.CheckConstraint("lock_version > 0", name="lifecycle_version"),
        sa.CheckConstraint(
            "review_interval IS NULL OR (extract(epoch FROM review_interval) > 0 AND "
            "extract(year FROM review_interval) * 12 + extract(month FROM "
            "review_interval) BETWEEN 0 AND 12000 AND extract(day FROM review_interval) "
            "BETWEEN 0 AND 7000 AND extract(hour FROM review_interval) = 0 AND "
            "extract(minute FROM review_interval) = 0 AND extract(second FROM "
            "review_interval) = 0 AND (extract(day FROM review_interval) = 0 OR "
            "(extract(year FROM review_interval) = 0 AND extract(month FROM "
            "review_interval) = 0)))",
            name="lifecycle_review_interval",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actors.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_actor_id"],
            ["actors.id"],
        ),
        sa.PrimaryKeyConstraint("lifecycle_id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "lifecycles_title_id",
        "lifecycles",
        [sa.literal_column("lower(title)"), "lifecycle_id"],
        unique=False,
    )
    op.create_table(
        "lifecycle_activity_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_display_name", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), server_default="succeeded", nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("origin", sa.Text(), server_default="geomg-admin", nullable=False),
        sa.Column("software_version", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "action IN ('lifecycle.created', 'lifecycle.updated')", name="activity_action"
        ),
        sa.CheckConstraint("outcome = 'succeeded'", name="activity_outcome"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actors.id"],
        ),
        sa.ForeignKeyConstraint(
            ["lifecycle_id"],
            ["lifecycles.lifecycle_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_id", "lifecycle_id", "action", "idempotency_key"),
    )
    op.create_index(
        "activity_lifecycle_time",
        "lifecycle_activity_entries",
        ["lifecycle_id", "occurred_at", "id"],
        unique=False,
    )

    op.execute("""
        CREATE FUNCTION lifecycle_immutable_code() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.code IS DISTINCT FROM OLD.code THEN
                RAISE EXCEPTION 'Lifecycle codes are immutable';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER lifecycle_code_immutable BEFORE UPDATE ON lifecycles
        FOR EACH ROW EXECUTE FUNCTION lifecycle_immutable_code()
    """)
    op.execute("""
        CREATE FUNCTION lifecycle_activity_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Activity entries are append-only';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER lifecycle_activity_append_only
        BEFORE UPDATE OR DELETE ON lifecycle_activity_entries
        FOR EACH ROW EXECUTE FUNCTION lifecycle_activity_immutable()
    """)


def downgrade():
    op.drop_index("activity_lifecycle_time", table_name="lifecycle_activity_entries")
    op.drop_table("lifecycle_activity_entries")
    op.drop_index("lifecycles_title_id", table_name="lifecycles")
    op.drop_table("lifecycles")
    op.drop_table("lifecycle_commands")
    op.drop_table("actors")
    op.execute("DROP FUNCTION lifecycle_immutable_code()")
    op.execute("DROP FUNCTION lifecycle_activity_immutable()")
