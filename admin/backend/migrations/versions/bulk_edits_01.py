"""Retain bulk action previews, execution history and versioned reversal evidence."""

from alembic import op

revision = "bulk_edits_01"
down_revision = "intake_02"
branch_labels = None
depends_on = None

TABLES = (
    "resource_bulk_actions",
    "resource_bulk_items",
    "resource_bulk_executions",
    "resource_bulk_results",
)


def upgrade():
    op.execute("""CREATE TABLE resource_bulk_actions (
        id uuid PRIMARY KEY, selection_id uuid NOT NULL REFERENCES resource_selections,
        reverts uuid REFERENCES resource_bulk_actions, actor_id uuid NOT NULL REFERENCES actors,
        actor_name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), key uuid NOT NULL,
        request_hash varchar(64) NOT NULL, fields jsonb NOT NULL, UNIQUE(actor_id,key))""")
    op.execute(
        """CREATE INDEX resource_bulk_history ON resource_bulk_actions(actor_id,created_at,id)"""
    )
    op.execute("""CREATE TABLE resource_bulk_items (
        action_id uuid REFERENCES resource_bulk_actions, resource_id text,
        set_id varchar(128) REFERENCES sets,
        before_version integer NOT NULL CHECK(before_version>0),
        status text NOT NULL
        CHECK(status IN ('ready','unchanged','conflict','read_only','active_job')),
        changes jsonb NOT NULL, PRIMARY KEY(action_id,resource_id))""")
    op.execute("""CREATE TABLE resource_bulk_executions (
        action_id uuid PRIMARY KEY REFERENCES resource_bulk_actions,
        actor_id uuid NOT NULL REFERENCES actors, actor_name text NOT NULL,
        applied_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("""CREATE TABLE resource_bulk_results (
        action_id uuid REFERENCES resource_bulk_executions, resource_id text, status text NOT NULL
        CHECK(status IN ('changed','unchanged','conflict','read_only','active_job')),
        after_version integer, CHECK ((status='changed')=(after_version IS NOT NULL)),
        PRIMARY KEY(action_id,resource_id),
        FOREIGN KEY(action_id,resource_id) REFERENCES resource_bulk_items)""")
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER immutable_bulk_history BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION lifecycle_activity_immutable()"
        )


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM resource_bulk_actions) THEN
        RAISE EXCEPTION 'Cannot discard bulk edit history'; END IF; END $$""")
    for table in reversed(TABLES):
        op.drop_table(table)
