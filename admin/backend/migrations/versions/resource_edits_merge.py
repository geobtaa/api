"""Join bulk edit history and manual draft creation after both schemas are present."""

revision = "resource_edits_merge"
down_revision = ("bulk_edits_01", "resource_create_01")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
