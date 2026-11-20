"""Independent Source identity and typed Source mutation evidence."""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

LEGACY_ACTIONS = """'lifecycle.created', 'lifecycle.updated',
'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated'"""


def upgrade():
    op.execute("""CREATE TABLE sources (
        source_id varchar(128) PRIMARY KEY,
        title varchar(250) NOT NULL,
        description text NOT NULL DEFAULT '',
        landing_page varchar(2048),
        admin_notes text NOT NULL DEFAULT '',
        lock_version integer NOT NULL DEFAULT 1,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        created_by_actor_id uuid NOT NULL REFERENCES actors(id),
        updated_by_actor_id uuid NOT NULL REFERENCES actors(id),
        CONSTRAINT source_id_format CHECK (source_id ~ '^[A-Za-z0-9_-]{1,128}$'),
        CONSTRAINT source_title CHECK (length(btrim(title)) > 0),
        CONSTRAINT source_description_bound CHECK (length(description) <= 5000),
        CONSTRAINT source_notes_bound CHECK (length(admin_notes) <= 10000),
        CONSTRAINT source_version CHECK (lock_version > 0))""")
    op.execute("CREATE INDEX sources_title_id ON sources (lower(title), source_id)")
    op.execute("""CREATE TABLE source_commands (
        actor_id uuid NOT NULL REFERENCES actors(id),
        operation text NOT NULL,
        idempotency_key uuid NOT NULL,
        request_hash varchar(64) NOT NULL,
        response jsonb,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(actor_id, operation, idempotency_key))""")
    op.execute("""CREATE FUNCTION source_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.source_id IS DISTINCT FROM OLD.source_id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.created_by_actor_id IS DISTINCT FROM OLD.created_by_actor_id THEN
                RAISE EXCEPTION 'Source identity and creation attribution are immutable';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER source_identity_immutable BEFORE UPDATE ON sources
        FOR EACH ROW EXECUTE FUNCTION source_identity_guard()""")
    op.execute("""ALTER TABLE lifecycle_activity_entries
        ADD COLUMN source_id varchar(128) REFERENCES sources(source_id),
        ALTER COLUMN lifecycle_id DROP NOT NULL""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute(
        "ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK "
        "(action IN (" + LEGACY_ACTIONS + ", 'source.created', 'source.updated'))"
    )
    # Source events cannot bypass composite Lifecycle/Workflow/job foreign keys with NULL.
    op.execute("""ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK (
        (source_id IS NULL AND lifecycle_id IS NOT NULL
         AND action NOT IN ('source.created', 'source.updated')) OR
        (source_id IS NOT NULL AND lifecycle_id IS NULL
         AND action IN ('source.created', 'source.updated')
         AND resource_id IS NULL AND workflow_id IS NULL
         AND workflow_version_id IS NULL AND job_id IS NULL))""")
    op.execute("""ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_source_replay
        UNIQUE(actor_id, source_id, action, idempotency_key)""")
    op.execute("""CREATE INDEX activity_source_time
        ON lifecycle_activity_entries (source_id, occurred_at, id)""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM sources)
        OR EXISTS (SELECT 1 FROM source_commands)
        OR EXISTS (SELECT 1 FROM lifecycle_activity_entries WHERE source_id IS NOT NULL)
        THEN RAISE EXCEPTION 'Cannot discard Source identity or history'; END IF; END $$""")
    op.execute("DROP INDEX activity_source_time")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_source_replay")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute(
        "ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK "
        "(action IN (" + LEGACY_ACTIONS + "))"
    )
    op.execute("""ALTER TABLE lifecycle_activity_entries DROP COLUMN source_id,
        ALTER COLUMN lifecycle_id SET NOT NULL""")
    op.drop_table("source_commands")
    op.drop_table("sources")
    op.execute("DROP FUNCTION source_identity_guard()")
