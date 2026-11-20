"""Align standalone GEOMG's two association column names with the deployed catalog."""

from alembic import op

revision = "unify_catalog_01"
down_revision = "alpha_bridge_01"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("distribution_types", "uri", new_column_name="distribution_uri")
    op.alter_column("resource_distributions", "import_id", new_column_name="import_distribution_id")


def downgrade():
    op.alter_column("resource_distributions", "import_distribution_id", new_column_name="import_id")
    op.alter_column("distribution_types", "distribution_uri", new_column_name="uri")
