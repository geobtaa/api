"""Direct optional Resource Source membership without inferred backfill."""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE resources ADD COLUMN source_id varchar(128) REFERENCES sources(source_id)"
    )
    op.execute("CREATE INDEX resources_source_id ON resources (source_id)")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM resources WHERE source_id IS NOT NULL)
        THEN RAISE EXCEPTION 'Cannot discard Resource Source associations'; END IF; END $$""")
    op.execute("DROP INDEX resources_source_id")
    op.execute("ALTER TABLE resources DROP COLUMN source_id")
