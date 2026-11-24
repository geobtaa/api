"""Versioned Workflow authoring and typed Activity links; production gates remain."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
CREATE TABLE workflow_process_types (
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        definition TEXT NOT NULL,
        PRIMARY KEY (key)
)
"""
    )
    op.execute(
        """
CREATE TABLE workflows (
        workflow_id UUID NOT NULL,
        lifecycle_id UUID NOT NULL,
        title VARCHAR(250) NOT NULL,
        lock_version INTEGER DEFAULT '1' NOT NULL,
        created_by_actor_id UUID NOT NULL,
        updated_by_actor_id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (workflow_id),
        UNIQUE (lifecycle_id, workflow_id),
        CONSTRAINT workflow_title CHECK (length(btrim(title)) > 0),
        CONSTRAINT workflow_lock_version CHECK (lock_version > 0),
        FOREIGN KEY(lifecycle_id) REFERENCES lifecycles (lifecycle_id),
        FOREIGN KEY(created_by_actor_id) REFERENCES actors (id),
        FOREIGN KEY(updated_by_actor_id) REFERENCES actors (id)
)
"""
    )
    op.execute(
        "CREATE INDEX workflows_lifecycle_title ON workflows (lifecycle_id, title, workflow_id)"
    )
    op.execute(
        """
CREATE TABLE workflow_versions (
        version_id UUID NOT NULL,
        workflow_id UUID NOT NULL,
        number INTEGER NOT NULL,
        state TEXT DEFAULT 'draft' NOT NULL,
        checksum VARCHAR(64),
        created_by_actor_id UUID NOT NULL,
        activated_by_actor_id UUID,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        activated_at TIMESTAMP WITH TIME ZONE,
        PRIMARY KEY (version_id),
        UNIQUE (workflow_id, number),
        UNIQUE (workflow_id, version_id),
        CONSTRAINT workflow_version_number CHECK (number > 0),
        CONSTRAINT workflow_version_state CHECK (state IN ('draft', 'active', 'superseded')),
        CONSTRAINT workflow_activation_evidence CHECK (state = 'draft' OR (checksum IS NOT NULL
    AND activated_at IS NOT NULL AND activated_by_actor_id IS NOT NULL)),
        FOREIGN KEY(workflow_id) REFERENCES workflows (workflow_id),
        FOREIGN KEY(created_by_actor_id) REFERENCES actors (id),
        FOREIGN KEY(activated_by_actor_id) REFERENCES actors (id)
)
"""
    )
    op.execute(
        "CREATE UNIQUE INDEX workflow_one_active ON workflow_versions "
        "(workflow_id) WHERE state = 'active'"
    )
    op.execute(
        "CREATE UNIQUE INDEX workflow_one_draft ON workflow_versions "
        "(workflow_id) WHERE state = 'draft'"
    )
    op.execute(
        """
CREATE TABLE workflow_processes (
        process_id UUID NOT NULL,
        version_id UUID NOT NULL,
        position INTEGER NOT NULL,
        process_type TEXT NOT NULL,
        name VARCHAR(200) NOT NULL,
        configuration_schema_version INTEGER DEFAULT '1' NOT NULL,
        configuration JSONB NOT NULL,
        PRIMARY KEY (process_id),
        UNIQUE (version_id, position),
        CONSTRAINT workflow_process_position CHECK (position BETWEEN 1 AND 100),
        CONSTRAINT workflow_configuration_version CHECK (configuration_schema_version = 1),
        CONSTRAINT workflow_configuration_bound CHECK (jsonb_typeof(configuration) = 'object'
    AND octet_length(configuration::text) <= 8192),
        FOREIGN KEY(version_id) REFERENCES workflow_versions (version_id),
        FOREIGN KEY(process_type) REFERENCES workflow_process_types (key)
)
"""
    )
    op.bulk_insert(
        sa.table(
            "workflow_process_types",
            sa.column("key", sa.Text),
            sa.column("label", sa.Text),
            sa.column("definition", sa.Text),
        ),
        [
            {
                "key": "template_children",
                "label": "Template children",
                "definition": "Create child metadata from a named template.",
            },
            {
                "key": "template_csv",
                "label": "CSV template",
                "definition": "Construct metadata using a named CSV template.",
            },
            {
                "key": "template_website",
                "label": "Website template",
                "definition": "Construct website metadata using a named template.",
            },
            {
                "key": "template_json",
                "label": "JSON template",
                "definition": "Construct metadata using a named JSON template.",
            },
            {
                "key": "harvest",
                "label": "Harvest",
                "definition": "Acquire source candidates for validation and review.",
            },
            {
                "key": "transform",
                "label": "Transform",
                "definition": "Apply a named, versioned metadata mapping.",
            },
            {
                "key": "validate",
                "label": "Validate",
                "definition": "Check metadata against the managed validation contract.",
            },
            {
                "key": "review",
                "label": "Review",
                "definition": "Review candidates before accepting managed changes.",
            },
            {
                "key": "publish",
                "label": "Publish",
                "definition": "Deliver accepted metadata through managed publication.",
            },
        ],
    )
    op.add_column("lifecycle_activity_entries", sa.Column("workflow_id", sa.Uuid()))
    op.add_column("lifecycle_activity_entries", sa.Column("workflow_version_id", sa.Uuid()))
    op.create_foreign_key(
        "activity_workflow_lifecycle",
        "lifecycle_activity_entries",
        "workflows",
        ["lifecycle_id", "workflow_id"],
        ["lifecycle_id", "workflow_id"],
    )
    op.create_foreign_key(
        "activity_workflow_version",
        "lifecycle_activity_entries",
        "workflow_versions",
        ["workflow_id", "workflow_version_id"],
        ["workflow_id", "version_id"],
    )
    op.create_check_constraint(
        "activity_workflow_pair",
        "lifecycle_activity_entries",
        "(workflow_id IS NULL) = (workflow_version_id IS NULL)",
    )
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', "
        "'resources.imported', 'resource.updated', 'lifecycle.paused', "
        "'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',"
        " 'review.completed', 'harvest.completed', 'workflow.created', "
        "'workflow.updated', 'workflow.draft_created', "
        "'workflow.activated')",
    )
    op.execute("""
        CREATE FUNCTION workflow_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'draft' THEN RAISE EXCEPTION 'Versions begin as drafts'; END IF;
                RETURN NEW;
            END IF;
            IF OLD.state = 'superseded' THEN
                RAISE EXCEPTION 'Superseded versions are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.state <> 'draft' THEN
                    RAISE EXCEPTION 'Active versions are immutable';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.state = 'active' THEN
                IF NEW.state <> 'superseded' OR
                   (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state') THEN
                    RAISE EXCEPTION 'Active definitions are immutable';
                END IF;
            ELSE
                IF NEW.version_id <> OLD.version_id OR NEW.workflow_id <> OLD.workflow_id OR
                   NEW.number <> OLD.number OR NEW.created_at <> OLD.created_at OR
                   NEW.created_by_actor_id <> OLD.created_by_actor_id THEN
                    RAISE EXCEPTION 'Version identity is immutable';
                END IF;
                IF NEW.state NOT IN ('draft', 'active') THEN
                    RAISE EXCEPTION 'Invalid version transition';
                END IF;
                IF NEW.state = 'active' AND NOT EXISTS (
                    SELECT 1 FROM workflow_processes WHERE version_id = OLD.version_id
                ) THEN RAISE EXCEPTION 'Activation requires a process'; END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER workflow_version_immutable BEFORE INSERT OR UPDATE"
        " OR DELETE ON workflow_versions FOR EACH ROW EXECUTE FUNCTION "
        "workflow_version_guard()"
    )
    op.execute("""
        CREATE FUNCTION workflow_process_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_state text;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.version_id <> OLD.version_id THEN
                RAISE EXCEPTION 'Processes cannot move between versions';
            END IF;
            IF TG_OP = 'DELETE' THEN
                SELECT state INTO parent_state FROM workflow_versions
                WHERE version_id = OLD.version_id FOR UPDATE;
            ELSE
                SELECT state INTO parent_state FROM workflow_versions
                WHERE version_id = NEW.version_id FOR UPDATE;
            END IF;
            IF parent_state IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'Only draft processes can change';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER workflow_process_immutable BEFORE INSERT OR UPDATE"
        " OR DELETE ON workflow_processes FOR EACH ROW EXECUTE FUNCTION "
        "workflow_process_guard()"
    )
    op.execute("""
        CREATE FUNCTION workflow_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.workflow_id <> OLD.workflow_id OR NEW.lifecycle_id <> OLD.lifecycle_id THEN
                RAISE EXCEPTION 'Workflow identity and Lifecycle are immutable';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER workflow_identity_immutable BEFORE UPDATE ON "
        "workflows FOR EACH ROW EXECUTE FUNCTION workflow_identity_guard()"
    )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM workflows) THEN
        RAISE EXCEPTION 'Preserve Workflow history: reconcile before downgrade'; END IF; END $$""")
    op.drop_constraint("activity_workflow_lifecycle", "lifecycle_activity_entries")
    op.drop_constraint("activity_workflow_version", "lifecycle_activity_entries")
    op.drop_constraint("activity_workflow_pair", "lifecycle_activity_entries", type_="check")
    op.drop_column("lifecycle_activity_entries", "workflow_version_id")
    op.drop_column("lifecycle_activity_entries", "workflow_id")
    op.drop_constraint("activity_action", "lifecycle_activity_entries", type_="check")
    op.create_check_constraint(
        "activity_action",
        "lifecycle_activity_entries",
        "action IN ('lifecycle.created', 'lifecycle.updated', "
        "'resources.imported', 'resource.updated', 'lifecycle.paused', "
        "'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',"
        " 'review.completed', 'harvest.completed')",
    )
    op.drop_table("workflow_processes")
    op.drop_table("workflow_versions")
    op.drop_table("workflows")
    op.drop_table("workflow_process_types")
    op.execute("DROP FUNCTION workflow_process_guard()")
    op.execute("DROP FUNCTION workflow_version_guard()")
    op.execute("DROP FUNCTION workflow_identity_guard()")
