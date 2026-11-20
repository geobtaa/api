"""Durable projection requests for confirmed published metadata edits."""

import sqlalchemy as sa
from alembic import op

revision = "alpha_projection_01"
down_revision = "local_password_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resource_projection_requests",
        sa.Column("resource_id", sa.String(), sa.ForeignKey("resources.id"), primary_key=True),
        sa.Column("resource_version", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("visible_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("resource_projection_requests")
