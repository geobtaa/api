"""Canonical cadence anchors and terminal review/harvest evidence (local construction)."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("lifecycles", sa.Column("review_anchor_at", sa.DateTime(timezone=True)))
    op.add_column("lifecycles", sa.Column("harvest_anchor_at", sa.DateTime(timezone=True)))
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', 'resources.imported', "
        "'resource.updated', 'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', "
        "'lifecycle.restored', 'review.completed', 'harvest.completed')",
    )
    op.drop_constraint("activity_outcome", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_outcome",
        "lifecycle_activity_entries",
        "outcome IN ('succeeded', 'partially_succeeded', 'failed', 'cancelled', 'rejected')",
    )


def downgrade():
    # Preserve history: incompatible terminal evidence blocks downgrade.
    op.drop_constraint("activity_outcome", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_outcome", "lifecycle_activity_entries", "outcome = 'succeeded'"
    )
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', 'resources.imported', "
        "'resource.updated', 'lifecycle.paused', 'lifecycle.activated', "
        "'lifecycle.retired', 'lifecycle.restored')",
    )
    op.drop_column("lifecycles", "harvest_anchor_at")
    op.drop_column("lifecycles", "review_anchor_at")
