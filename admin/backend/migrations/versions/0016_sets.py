"""Source-owned Set catalog and typed atomic mutation evidence; no backfill."""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE sets (
        set_id VARCHAR(128) NOT NULL,
        source_id VARCHAR(128) NOT NULL,
        title VARCHAR(250) NOT NULL,
        description TEXT DEFAULT '' NOT NULL,
        endpoint_url VARCHAR(2048),
        admin_notes TEXT DEFAULT '' NOT NULL,
        legacy_code TEXT DEFAULT '' NOT NULL,
        set_scope TEXT DEFAULT '' NOT NULL,
        endpoint_description TEXT DEFAULT '' NOT NULL,
        workflow TEXT DEFAULT '' NOT NULL,
        review_interval TEXT DEFAULT '' NOT NULL,
        harvest_interval TEXT DEFAULT '' NOT NULL,
        tags TEXT DEFAULT '' NOT NULL,
        status VARCHAR(16) DEFAULT 'active' NOT NULL,
        lock_version INTEGER DEFAULT '1' NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        created_by_actor_id UUID NOT NULL,
        updated_by_actor_id UUID NOT NULL,
        PRIMARY KEY (set_id),
        CONSTRAINT set_id_format CHECK (set_id ~ '^[A-Za-z0-9_-]{1,128}$'),
        CONSTRAINT set_title CHECK (length(btrim(title)) > 0),
        CONSTRAINT set_description_bound CHECK (length(description) <= 5000),
        CONSTRAINT set_notes_bound CHECK (length(admin_notes) <= 10000),
        CONSTRAINT set_version CHECK (lock_version > 0),
        CONSTRAINT set_legacy_code_bound CHECK (length(legacy_code) <= 128),
        CONSTRAINT set_set_scope_bound CHECK (length(set_scope) <= 5000),
        CONSTRAINT set_endpoint_description_bound CHECK (length(endpoint_description) <=
1000),
        CONSTRAINT set_workflow_bound CHECK (length(workflow) <= 128),
        CONSTRAINT set_review_interval_bound CHECK (length(review_interval) <= 64),
        CONSTRAINT set_harvest_interval_bound CHECK (length(harvest_interval) <= 64),
        CONSTRAINT set_tags_bound CHECK (length(tags) <= 2000),
        CONSTRAINT set_status CHECK (status IN ('active', 'inactive', 'retired')),
        FOREIGN KEY(source_id) REFERENCES sources (source_id),
        FOREIGN KEY(created_by_actor_id) REFERENCES actors (id),
        FOREIGN KEY(updated_by_actor_id) REFERENCES actors (id)
)""")
    op.execute("""CREATE INDEX sets_source_id ON sets (source_id)""")
    op.execute("""CREATE INDEX sets_title_id ON sets (lower(title), set_id)""")
    op.execute("""CREATE TABLE set_commands (
        actor_id UUID NOT NULL,
        operation TEXT NOT NULL,
        idempotency_key UUID NOT NULL,
        request_hash VARCHAR(64) NOT NULL,
        response JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (actor_id, operation, idempotency_key),
        FOREIGN KEY(actor_id) REFERENCES actors (id)
)""")
    op.execute("""CREATE FUNCTION set_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
IF NEW.set_id IS DISTINCT FROM OLD.set_id OR NEW.source_id IS DISTINCT FROM OLD.source_id
 OR NEW.created_at IS DISTINCT FROM OLD.created_at
 OR NEW.created_by_actor_id IS DISTINCT FROM OLD.created_by_actor_id THEN
 RAISE EXCEPTION 'Set identity, parent Source and creation attribution are immutable';
END IF; RETURN NEW; END $$""")
    op.execute("""CREATE TRIGGER set_identity_immutable BEFORE UPDATE ON sets
FOR EACH ROW EXECUTE FUNCTION set_identity_guard()""")
    op.execute("""ALTER TABLE lifecycle_activity_entries
ADD COLUMN set_id varchar(128) REFERENCES sets(set_id)""")
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created',
'source.updated', 'set.created', 'set.updated'))""")
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ((set_id IS
NULL AND source_id IS NULL AND lifecycle_id IS NOT NULL AND action NOT IN ('source.created',
'source.updated', 'set.created', 'set.updated')) OR (set_id IS NULL AND source_id IS NOT
NULL AND lifecycle_id IS NULL AND action IN ('source.created', 'source.updated',
'review.completed', 'harvest.completed') AND resource_id IS NULL AND workflow_id IS NULL AND
workflow_version_id IS NULL AND job_id IS NULL) OR (set_id IS NOT NULL AND source_id IS NULL
AND lifecycle_id IS NULL AND action IN ('set.created', 'set.updated') AND resource_id IS
NULL AND workflow_id IS NULL AND workflow_version_id IS NULL AND job_id IS NULL))""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_set_replay
UNIQUE(actor_id, set_id, action, idempotency_key)""")
    op.execute(
        """CREATE INDEX activity_set_time ON lifecycle_activity_entries (set_id, occurred_at, id)"""
    )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM sets) OR EXISTS (SELECT 1 FROM set_commands)
OR EXISTS (SELECT 1 FROM lifecycle_activity_entries WHERE set_id IS NOT NULL)
THEN RAISE EXCEPTION 'Cannot discard Set identity or history'; END IF; END $$""")
    op.execute("""DROP INDEX activity_set_time""")
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_set_replay""")
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated',
'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created',
'source.updated'))""")
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ((source_id IS
NULL AND lifecycle_id IS NOT NULL
AND action NOT IN ('source.created', 'source.updated')) OR
(source_id IS NOT NULL AND lifecycle_id IS NULL
AND action IN ('source.created', 'source.updated', 'review.completed', 'harvest.completed')
AND resource_id IS NULL AND workflow_id IS NULL
AND workflow_version_id IS NULL AND job_id IS NULL))""")
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP COLUMN set_id""")
    op.execute("""DROP TABLE set_commands""")
    op.execute("""DROP TABLE sets""")
    op.execute("""DROP FUNCTION set_identity_guard()""")
