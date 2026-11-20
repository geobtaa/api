"""Confirmed Set state transitions with immutable typed evidence."""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created', 'source.updated',
'set.created', 'set.updated', 'set.deactivated', 'set.activated', 'set.retired',
'set.restored'))""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ((set_id IS NULL
AND source_id IS NULL AND lifecycle_id IS NOT NULL AND action NOT IN ('source.created',
'source.updated', 'set.created', 'set.updated', 'set.deactivated', 'set.activated',
'set.retired', 'set.restored')) OR (set_id IS NULL AND source_id IS NOT NULL AND lifecycle_id
IS NULL AND action IN ('source.created', 'source.updated', 'review.completed',
'harvest.completed') AND resource_id IS NULL AND workflow_id IS NULL AND workflow_version_id
IS NULL AND job_id IS NULL) OR (set_id IS NOT NULL AND source_id IS NULL AND lifecycle_id IS
NULL AND action IN ('set.created', 'set.updated', 'set.deactivated', 'set.activated',
'set.retired', 'set.restored') AND resource_id IS NULL AND workflow_id IS NULL AND
workflow_version_id IS NULL AND job_id IS NULL))""")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM lifecycle_activity_entries WHERE action IN
            ('set.deactivated', 'set.activated', 'set.retired', 'set.restored'))
        THEN RAISE EXCEPTION 'Cannot discard Set state history'; END IF;
    END $$""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created', 'source.updated',
'set.created', 'set.updated'))""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ((set_id IS NULL
AND source_id IS NULL AND lifecycle_id IS NOT NULL AND action NOT IN ('source.created',
'source.updated', 'set.created', 'set.updated')) OR (set_id IS NULL AND source_id IS NOT NULL
AND lifecycle_id IS NULL AND action IN ('source.created', 'source.updated',
'review.completed', 'harvest.completed') AND resource_id IS NULL AND workflow_id IS NULL AND
workflow_version_id IS NULL AND job_id IS NULL) OR (set_id IS NOT NULL AND source_id IS NULL
AND lifecycle_id IS NULL AND action IN ('set.created', 'set.updated') AND resource_id IS NULL
AND workflow_id IS NULL AND workflow_version_id IS NULL AND job_id IS NULL))""")
