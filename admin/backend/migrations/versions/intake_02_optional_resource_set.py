"""Resources may be imported and curated before assignment to a managing Set."""

from alembic import op

revision = "intake_02"
down_revision = "intake_01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE resources ALTER COLUMN set_id DROP NOT NULL")
    op.execute("ALTER TABLE resource_selection_items ALTER COLUMN set_id DROP NOT NULL")
    op.execute("""ALTER TABLE resource_imports ADD COLUMN intake_batch_id uuid
               REFERENCES resource_intake_batches(id)""")
    op.execute("ALTER TABLE resource_imports DROP CONSTRAINT resource_import_owner")
    op.execute("""ALTER TABLE resource_imports ADD CONSTRAINT resource_import_owner
        CHECK(set_id IS NOT NULL OR lifecycle_id IS NOT NULL OR intake_batch_id IS NOT NULL)""")
    op.execute("""ALTER TABLE resource_intake_drafts ADD COLUMN catalog_id text
               UNIQUE REFERENCES resources(id)""")
    op.execute("""ALTER TABLE lifecycle_activity_entries RENAME CONSTRAINT activity_subject
               TO activity_subject_before_intake""")
    op.execute("""DO $$ DECLARE previous text; BEGIN
        SELECT pg_get_expr(conbin, conrelid) INTO previous FROM pg_constraint
        WHERE conrelid='lifecycle_activity_entries'::regclass
          AND conname='activity_subject_before_intake';
        EXECUTE 'ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ('
        || previous || ' OR (set_id IS NULL AND source_id IS NULL AND lifecycle_id IS NULL
        AND resource_id IS NOT NULL AND workflow_id IS NULL AND job_id IS NULL
        AND action IN (''resources.imported'',''resource.updated'')))';
        END $$""")
    op.execute(
        "ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject_before_intake"
    )
    from app.resources.intake import import_pending_batches

    op.run_async(import_pending_batches)


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM resources WHERE set_id IS NULL)
          OR EXISTS (SELECT 1 FROM resource_imports WHERE intake_batch_id IS NOT NULL)
          OR EXISTS (SELECT 1 FROM resource_selection_items WHERE set_id IS NULL)
        THEN RAISE EXCEPTION 'Cannot discard setless Resource history'; END IF; END $$""")
    op.execute("ALTER TABLE resource_intake_drafts DROP COLUMN catalog_id")
    op.execute("ALTER TABLE resource_imports DROP CONSTRAINT resource_import_owner")
    op.execute("ALTER TABLE resource_imports DROP COLUMN intake_batch_id")
    op.execute("""ALTER TABLE resource_imports ADD CONSTRAINT resource_import_owner
               CHECK(set_id IS NOT NULL OR lifecycle_id IS NOT NULL)""")
    op.execute("ALTER TABLE resources ALTER COLUMN set_id SET NOT NULL")
    op.execute("ALTER TABLE resource_selection_items ALTER COLUMN set_id SET NOT NULL")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject")
    from app.activity import MANAGED_SUBJECT

    op.execute(
        "ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ("
        + MANAGED_SUBJECT
        + ")"
    )
