"""Enable atomic Resource edit Activity Log entries (local construction)."""

from alembic import op

revision = "0003"
down_revision = "43b1f6d2ed11"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', "
        "'resources.imported', 'resource.updated')",
    )


def downgrade():
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', 'resources.imported')",
    )
