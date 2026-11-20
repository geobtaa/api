"""Allow explicit Lifecycle state-change evidence; production gates remain unchanged."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', 'resources.imported', "
        "'resource.updated', 'lifecycle.paused', 'lifecycle.activated', "
        "'lifecycle.retired', 'lifecycle.restored')",
    )


def downgrade():
    # Existing transition evidence deliberately blocks downgrade rather than being erased.
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', "
        "'resources.imported', 'resource.updated')",
    )
