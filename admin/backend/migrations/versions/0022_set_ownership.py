"""Native managing Set scope; populated legacy data needs a reviewed cutover."""

from alembic import context, op

from app.sets.cutover import apply_migration, create_audit_tables, prepare_migration

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    approval = context.config.attributes.get("set_cutover")
    prepared = prepare_migration(connection, approval) if approval is not None else None
    if prepared is None:
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM resources)
                OR EXISTS (SELECT 1 FROM resource_imports)
                OR EXISTS (SELECT 1 FROM workflows)
                OR EXISTS (SELECT 1 FROM jobs)
                OR EXISTS (SELECT 1 FROM resource_selection_items)
                OR EXISTS (SELECT 1 FROM identity_accounts)
                OR EXISTS (SELECT 1 FROM identity_invitations)
            THEN
                RAISE EXCEPTION 'Reviewed Set ownership cutover required for existing data';
            END IF;
        END $$""")
    for table in ("resources", "resource_imports", "workflows", "jobs", "resource_selection_items"):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN lifecycle_id DROP NOT NULL")
        op.execute(f"ALTER TABLE {table} ADD COLUMN set_id varchar(128) REFERENCES sets(set_id)")
    op.execute("CREATE INDEX resources_set_title ON resources (set_id, dct_title_s, id)")
    op.execute("CREATE INDEX workflows_set_title ON workflows (set_id, title, workflow_id)")
    op.execute(
        "ALTER TABLE workflows ADD CONSTRAINT workflow_set_identity UNIQUE(set_id, workflow_id)"
    )
    op.execute("ALTER TABLE jobs ADD CONSTRAINT job_set_identity UNIQUE(set_id, job_id)")
    op.execute("""ALTER TABLE jobs ADD CONSTRAINT job_set_receipt
        UNIQUE(actor_id, set_id, operation, idempotency_key)""")
    op.execute("""ALTER TABLE jobs ADD CONSTRAINT job_set_workflow
        FOREIGN KEY(set_id, workflow_id) REFERENCES workflows(set_id, workflow_id)""")
    op.execute("""ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_set_workflow
        FOREIGN KEY(set_id, workflow_id) REFERENCES workflows(set_id, workflow_id)""")
    op.execute("""ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_set_job
        FOREIGN KEY(set_id, job_id) REFERENCES jobs(set_id, job_id)""")
    op.execute("""ALTER TABLE sets ADD COLUMN represented_by_id text,
        ADD CONSTRAINT set_representative FOREIGN KEY(represented_by_id)
        REFERENCES resources(id)""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created', 'source.updated',
'set.created', 'set.updated', 'set.deactivated', 'set.activated', 'set.retired',
'set.restored', 'set.representative_changed', 'set.migrated'))""")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_subject CHECK ((set_id IS NULL
AND source_id IS NULL AND lifecycle_id IS NOT NULL AND action NOT IN ('source.created',
'source.updated', 'set.created', 'set.updated', 'set.deactivated', 'set.activated',
'set.retired', 'set.restored', 'set.representative_changed', 'set.migrated')) OR (set_id IS NULL
AND source_id
IS NOT NULL AND lifecycle_id IS NULL AND action IN ('source.created', 'source.updated',
'review.completed', 'harvest.completed') AND resource_id IS NULL AND workflow_id IS NULL AND
workflow_version_id IS NULL AND job_id IS NULL) OR (set_id IS NOT NULL AND source_id IS NULL
AND lifecycle_id IS NULL AND action NOT LIKE 'lifecycle.%' AND action NOT IN
('source.created', 'source.updated')))""")

    create_audit_tables(connection)
    if prepared is not None:
        apply_migration(connection, prepared)
    for table in ("resources", "workflows", "jobs", "resource_selection_items"):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN set_id SET NOT NULL")
    # A legacy receipt may span multiple new Sets. Keep its original scope and
    # response intact; every new API import still requires one managing Set.
    op.execute("""ALTER TABLE resource_imports ADD CONSTRAINT resource_import_owner
        CHECK (set_id IS NOT NULL OR lifecycle_id IS NOT NULL)""")
    op.execute("ALTER TABLE resources RENAME COLUMN source_id TO legacy_source_id")
    op.execute("ALTER INDEX resources_source_id RENAME TO resources_legacy_source_id")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM resources)
            OR EXISTS (SELECT 1 FROM resource_imports)
            OR EXISTS (SELECT 1 FROM workflows)
            OR EXISTS (SELECT 1 FROM jobs)
            OR EXISTS (SELECT 1 FROM resource_selection_items)
            OR EXISTS (SELECT 1 FROM sets WHERE represented_by_id IS NOT NULL)
            OR EXISTS (SELECT 1 FROM set_ownership_cutovers)
        THEN RAISE EXCEPTION 'Cannot discard native Set ownership or history'; END IF;
    END $$""")
    op.execute("DROP TABLE resource_set_cutovers")
    op.execute("DROP TABLE set_ownership_cutovers")
    op.execute("DROP FUNCTION protect_set_cutover()")
    op.execute("ALTER TABLE resource_imports DROP CONSTRAINT resource_import_owner")
    op.execute("ALTER TABLE resources RENAME COLUMN legacy_source_id TO source_id")
    op.execute("ALTER INDEX resources_legacy_source_id RENAME TO resources_source_id")
    # Restore frozen typed subject constraints from the preceding revision.
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_set_job")
    op.execute("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_set_workflow")
    op.execute("ALTER TABLE jobs DROP CONSTRAINT job_set_workflow")
    op.execute("ALTER TABLE jobs DROP CONSTRAINT job_set_identity, DROP CONSTRAINT job_set_receipt")
    op.execute("ALTER TABLE workflows DROP CONSTRAINT workflow_set_identity")
    op.execute("ALTER TABLE sets DROP COLUMN represented_by_id")
    for table in ("resources", "resource_imports", "workflows", "jobs", "resource_selection_items"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN set_id")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN lifecycle_id SET NOT NULL")
    op.execute("""
ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_action""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT activity_action CHECK (action IN
('lifecycle.created', 'lifecycle.updated', 'resources.imported', 'resource.updated',
'lifecycle.paused', 'lifecycle.activated', 'lifecycle.retired', 'lifecycle.restored',
'review.completed', 'harvest.completed', 'workflow.created', 'workflow.updated',
'workflow.draft_created', 'workflow.activated', 'validation.completed',
'lifecycle.representative_changed', 'resource.associated', 'source.created', 'source.updated',
'set.created', 'set.updated', 'set.deactivated', 'set.activated', 'set.retired',
'set.restored'))""")
    op.execute("""
ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT activity_subject""")
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
