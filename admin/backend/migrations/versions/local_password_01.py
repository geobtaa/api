"""Add isolated alpha credentials and database-backed sign-in throttling."""

import sqlalchemy as sa
from alembic import op

revision = "local_password_01"
down_revision = "resource_edits_merge"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "identity_local_credentials",
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("identity_accounts.actor_id"), primary_key=True
        ),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text()),
        sa.Column("setup_hash", sa.String(64), unique=True),
        sa.Column("setup_expires_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "identity_login_limits",
        sa.Column("bucket", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_identity_login_limits_expires_at", "identity_login_limits", ["expires_at"])


def downgrade():
    op.drop_table("identity_login_limits")
    op.drop_table("identity_local_credentials")
