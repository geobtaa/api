"""Record manual draft creation against its Resource and optional managing Set."""

from alembic import op

revision = "resource_create_01"
down_revision = "intake_02"
branch_labels = None
depends_on = None

TABLE = "lifecycle_activity_entries"
PREVIOUS_ACTIONS = """
action IN ('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created', 'source.updated',
'set.created', 'set.updated', 'set.deactivated', 'set.activated', 'set.retired',
'set.restored', 'set.representative_changed', 'set.migrated')"""
PREVIOUS_SUBJECTS = """
(set_id IS NULL AND source_id IS NULL AND lifecycle_id IS NOT NULL AND action NOT IN
('source.created', 'source.updated', 'set.created', 'set.updated', 'set.deactivated',
'set.activated', 'set.retired', 'set.restored', 'set.representative_changed', 'set.migrated'))
OR (set_id IS NULL AND source_id IS NOT NULL AND lifecycle_id IS NULL AND action IN
('source.created', 'source.updated', 'review.completed', 'harvest.completed') AND resource_id
IS NULL AND workflow_id IS NULL AND workflow_version_id IS NULL AND job_id IS NULL) OR (set_id
IS NOT NULL AND source_id IS NULL AND lifecycle_id IS NULL AND action NOT LIKE 'lifecycle.%'
AND action NOT IN ('source.created', 'source.updated')) OR (set_id IS NULL AND source_id IS
NULL AND lifecycle_id IS NULL AND resource_id IS NOT NULL AND workflow_id IS NULL AND job_id IS
NULL AND action IN ('resources.imported','resource.updated'))"""
CREATE_SUBJECT = """
resource_id IS NOT NULL AND source_id IS NULL AND lifecycle_id IS NULL AND workflow_id IS NULL
AND workflow_version_id IS NULL AND job_id IS NULL"""


def replace_checks(actions, subjects):
    for name, condition in (("activity_action", actions), ("activity_subject", subjects)):
        op.drop_constraint(name, TABLE, type_="check")
        op.create_check_constraint(name, TABLE, condition)


def upgrade():
    replace_checks(
        f"({PREVIOUS_ACTIONS}) OR action = 'resource.created'",
        f"CASE WHEN action = 'resource.created' THEN ({CREATE_SUBJECT}) "
        f"ELSE ({PREVIOUS_SUBJECTS}) END",
    )


def downgrade():
    # Restoring the previous constraints refuses a downgrade if create events exist.
    replace_checks(PREVIOUS_ACTIONS, PREVIOUS_SUBJECTS)
