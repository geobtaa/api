"""Bounded durable report chunks and larger server-owned job selections."""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE job_artifacts ALTER COLUMN byte_count TYPE bigint")
    op.execute("""CREATE TABLE job_artifact_chunks (
        artifact_id uuid NOT NULL REFERENCES job_artifacts(artifact_id),
        position integer NOT NULL, content bytea NOT NULL,
        PRIMARY KEY(artifact_id, position),
        CONSTRAINT artifact_chunk_bound CHECK
        (position > 0 AND octet_length(content) BETWEEN 1 AND 65536))""")
    op.execute("""CREATE FUNCTION protect_report_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_state text; expires timestamptz;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Report bytes are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                SELECT expires_at INTO expires FROM job_artifacts
                    WHERE artifact_id = OLD.artifact_id;
                IF expires > clock_timestamp() THEN
                    RAISE EXCEPTION 'Report retention has not elapsed';
                END IF;
                RETURN OLD;
            END IF;
            SELECT j.state INTO parent_state FROM jobs j JOIN job_artifacts a
                ON a.job_id = j.job_id WHERE a.artifact_id = NEW.artifact_id;
            IF parent_state NOT IN ('queued', 'running') THEN
                RAISE EXCEPTION 'Completed report bytes are immutable';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER protect_report_chunk BEFORE INSERT OR UPDATE OR DELETE
        ON job_artifact_chunks FOR EACH ROW EXECUTE FUNCTION protect_report_chunk()""")
    op.execute("ALTER TABLE job_items DROP CONSTRAINT job_item_bounds")
    op.execute("""ALTER TABLE job_items ADD CONSTRAINT job_item_bounds
        CHECK (position > 0 AND resource_version > 0)""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM job_artifacts)
        OR EXISTS (SELECT 1 FROM job_items WHERE position > 500)
        THEN RAISE EXCEPTION 'Cannot discard chunked report history'; END IF; END $$""")
    op.drop_table("job_artifact_chunks")
    op.execute("DROP FUNCTION protect_report_chunk()")
    op.execute("ALTER TABLE job_artifacts ALTER COLUMN byte_count TYPE integer")
    op.execute("ALTER TABLE job_items DROP CONSTRAINT job_item_bounds")
    op.execute("""ALTER TABLE job_items ADD CONSTRAINT job_item_bounds
        CHECK (position BETWEEN 1 AND 500 AND resource_version > 0)""")
