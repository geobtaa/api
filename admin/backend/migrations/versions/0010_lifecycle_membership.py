"""Explicit representative and current association evidence."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

ACTIONS = """'lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed'"""


def upgrade():
    op.execute("""ALTER TABLE lifecycles ADD COLUMN represented_by_id text
        CONSTRAINT lifecycle_representative REFERENCES resources(id)""")
    op.execute("""ALTER TABLE lifecycle_activity_entries ADD COLUMN resource_id text
        CONSTRAINT activity_resource_identity REFERENCES resources(id)""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute(
        "ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK "
        "(action IN (" + ACTIONS + ", 'lifecycle.representative_changed', 'resource.associated'))"
    )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM lifecycles
        WHERE represented_by_id IS NOT NULL)
        OR EXISTS (SELECT 1 FROM lifecycle_activity_entries WHERE action IN
        ('lifecycle.representative_changed','resource.associated'))
        THEN RAISE EXCEPTION 'Cannot discard association history'; END IF; END $$""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP COLUMN resource_id")
    op.execute("ALTER TABLE lifecycles DROP COLUMN represented_by_id")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute(
        "ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK "
        "(action IN (" + ACTIONS + "))"
    )
