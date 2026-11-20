"""Allow staff-reported review/harvest evidence directly against Sources."""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def subject_constraint(actions):
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject")
    op.execute(
        """ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK (
        (source_id IS NULL AND lifecycle_id IS NOT NULL
         AND action NOT IN ('source.created', 'source.updated')) OR
        (source_id IS NOT NULL AND lifecycle_id IS NULL
         AND action IN ("""
        + actions
        + """)
         AND resource_id IS NULL AND workflow_id IS NULL
         AND workflow_version_id IS NULL AND job_id IS NULL))"""
    )


def upgrade():
    subject_constraint(
        "'source.created', 'source.updated', 'review.completed', 'harvest.completed'"
    )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM lifecycle_activity_entries
        WHERE source_id IS NOT NULL AND action IN ('review.completed', 'harvest.completed'))
        THEN RAISE EXCEPTION 'Cannot discard Source work history'; END IF; END $$""")
    subject_constraint("'source.created', 'source.updated'")
