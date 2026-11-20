"""Durable staff CSV intake before managing Set assignment."""

from alembic import op

revision = "intake_01"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE resource_intake_batches (
        id uuid PRIMARY KEY, actor_id uuid NOT NULL REFERENCES actors(id),
        receipt_key uuid NOT NULL, original_csv text NOT NULL, headings jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(actor_id, receipt_key))""")
    op.execute(
        """CREATE INDEX intake_owner_date ON resource_intake_batches(actor_id, created_at)"""
    )
    op.execute("""CREATE TABLE resource_intake_drafts (
        batch_id uuid NOT NULL REFERENCES resource_intake_batches(id),
        row_number integer NOT NULL CHECK(row_number > 0),
        resource_id text NOT NULL, title text NOT NULL, cells jsonb NOT NULL,
        version integer NOT NULL DEFAULT 1 CHECK(version > 0),
        assigned_import uuid REFERENCES resource_imports(id),
        PRIMARY KEY(batch_id, row_number))""")
    op.execute("""CREATE TABLE resource_intake_activity (
        id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES resource_intake_batches(id),
        actor_id uuid NOT NULL REFERENCES actors(id), action text NOT NULL
        CHECK(action IN ('saved','edited','assigned')), details jsonb NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT now())""")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM resource_intake_batches) THEN
            RAISE EXCEPTION 'Cannot discard saved intake uploads';
        END IF;
    END $$""")
    op.drop_table("resource_intake_activity")
    op.drop_table("resource_intake_drafts")
    op.drop_table("resource_intake_batches")
