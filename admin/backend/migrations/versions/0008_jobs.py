"""Durable Resource validation jobs; production gates remain unchanged."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE jobs (
job_id UUID NOT NULL,
lifecycle_id UUID NOT NULL,
actor_id UUID NOT NULL,
operation TEXT NOT NULL,
idempotency_key UUID NOT NULL,
request_hash VARCHAR(64) NOT NULL,
workflow_id UUID,
workflow_version_id UUID,
state TEXT DEFAULT 'queued' NOT NULL,
attempt_number INTEGER DEFAULT '0' NOT NULL,
lease_token UUID,
lease_until TIMESTAMP WITH TIME ZONE,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
finished_at TIMESTAMP WITH TIME ZONE,
software_version VARCHAR(100) NOT NULL,
PRIMARY KEY (job_id),
UNIQUE (actor_id, lifecycle_id, operation, idempotency_key),
UNIQUE (lifecycle_id, job_id),
FOREIGN KEY(lifecycle_id, workflow_id) REFERENCES workflows (lifecycle_id, workflow_id),
FOREIGN KEY(workflow_id, workflow_version_id) REFERENCES workflow_versions (workflow_id,
version_id),
CONSTRAINT job_workflow_pair CHECK ((workflow_id IS NULL) = (workflow_version_id IS
NULL)),
CONSTRAINT job_operation CHECK (operation = 'resources.validate'),
CONSTRAINT job_state CHECK (state IN ('queued' ,'running' ,'succeeded'
,'partially_succeeded' ,'failed' ,'cancelled' ,'rejected')),
CONSTRAINT job_attempt_limit CHECK (attempt_number BETWEEN 0 AND 3),
CONSTRAINT job_lease CHECK ((state = 'running') = (lease_token IS NOT NULL AND
lease_until IS NOT NULL)),
FOREIGN KEY(lifecycle_id) REFERENCES lifecycles (lifecycle_id),
FOREIGN KEY(actor_id) REFERENCES actors (id)
)
""")
    op.execute("""CREATE INDEX jobs_claim ON jobs (state, lease_until, created_at, job_id)""")
    op.execute("""
CREATE TABLE job_items (
job_id UUID NOT NULL,
position INTEGER NOT NULL,
resource_id VARCHAR(512) NOT NULL,
resource_version INTEGER NOT NULL,
disposition TEXT DEFAULT 'pending' NOT NULL,
details JSONB DEFAULT '{}' NOT NULL,
PRIMARY KEY (job_id, position),
UNIQUE (job_id, resource_id),
CONSTRAINT job_item_bounds CHECK (position BETWEEN 1 AND 500 AND resource_version > 0),
CONSTRAINT job_item_disposition CHECK (disposition IN ('pending' ,'unchanged'
,'conflicted' ,'invalid' ,'failed' ,'cancelled' ,'rejected')),
CONSTRAINT job_item_details_bound CHECK (octet_length(details::text) <= 16384),
FOREIGN KEY(job_id) REFERENCES jobs (job_id)
)
""")
    op.execute("""
CREATE TABLE job_attempts (
job_id UUID NOT NULL,
number INTEGER NOT NULL,
lease_token UUID NOT NULL,
state TEXT NOT NULL,
started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
finished_at TIMESTAMP WITH TIME ZONE,
PRIMARY KEY (job_id, number),
CONSTRAINT job_attempt_state CHECK (state IN ('running' ,'expired' ,'succeeded'
,'partially_succeeded' ,'failed' ,'cancelled' ,'rejected')),
FOREIGN KEY(job_id) REFERENCES jobs (job_id),
UNIQUE (lease_token)
)
""")
    op.execute("""
CREATE TABLE job_artifacts (
artifact_id UUID NOT NULL,
job_id UUID NOT NULL,
checksum VARCHAR(64) NOT NULL,
byte_count INTEGER NOT NULL,
content BYTEA,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
expired_at TIMESTAMP WITH TIME ZONE,
PRIMARY KEY (artifact_id),
CONSTRAINT job_artifact_size CHECK (byte_count >= 0 AND (content IS NULL OR
octet_length(content) = byte_count)),
UNIQUE (job_id),
FOREIGN KEY(job_id) REFERENCES jobs (job_id)
)
""")
    op.execute("""ALTER TABLE lifecycle_activity_entries ADD COLUMN job_id UUID""")
    op.execute(
        """
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_job_lifecycle FOREIGN KEY
(lifecycle_id, job_id) REFERENCES jobs (lifecycle_id, job_id)
"""
    )
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action""")
    op.execute(
        """
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed'))
"""
    )

    op.execute("""
CREATE FUNCTION protect_job() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Job history is permanent'; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.workflow_version_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM workflow_versions WHERE version_id = NEW.workflow_version_id
            AND state = 'active'
        ) THEN RAISE EXCEPTION 'Jobs require an active version at submission'; END IF;
        RETURN NEW;
    END IF;
    IF OLD.state NOT IN ('queued', 'running') OR
        (to_jsonb(OLD) - ARRAY['state','attempt_number','lease_token','lease_until','finished_at'])
        IS DISTINCT FROM
        (to_jsonb(NEW) - ARRAY['state','attempt_number','lease_token','lease_until','finished_at'])
    THEN RAISE EXCEPTION 'Job identity and terminal history are immutable'; END IF;
    RETURN NEW;
END $$
""")
    op.execute("""
CREATE TRIGGER protect_job BEFORE INSERT OR UPDATE OR DELETE ON jobs
FOR EACH ROW EXECUTE FUNCTION protect_job()
""")
    op.execute("""
CREATE FUNCTION protect_job_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_state text;
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Job results are permanent'; END IF;
    SELECT state INTO parent_state FROM jobs WHERE job_id = NEW.job_id FOR UPDATE;
    IF parent_state NOT IN ('queued', 'running') THEN
        RAISE EXCEPTION 'Terminal job results are immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND (OLD.disposition <> 'pending' OR
        (to_jsonb(OLD) - ARRAY['disposition','details']) IS DISTINCT FROM
        (to_jsonb(NEW) - ARRAY['disposition','details'])) THEN
        RAISE EXCEPTION 'Selected versions and completed results are immutable';
    END IF;
    RETURN NEW;
END $$
""")
    op.execute("""
CREATE TRIGGER protect_job_item BEFORE INSERT OR UPDATE OR DELETE ON job_items
FOR EACH ROW EXECUTE FUNCTION protect_job_item()
""")


def downgrade():
    op.execute(
        """
DO $$ BEGIN IF EXISTS (SELECT 1 FROM jobs) THEN RAISE EXCEPTION 'Cannot discard job
history'; END IF; END $$
"""
    )
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_job_lifecycle")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP COLUMN job_id")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute(
        """
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated'))
"""
    )
    op.drop_table("job_artifacts")
    op.drop_table("job_attempts")
    op.drop_table("job_items")
    op.drop_table("jobs")
    op.execute("DROP FUNCTION protect_job_item()")
    op.execute("DROP FUNCTION protect_job()")
