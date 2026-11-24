"""Reviewed exact-ID scope, upstream versions and durable alpha Bridge receipts."""

from alembic import op

revision = "alpha_bridge_01"
down_revision = "alpha_projection_01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE alpha_bridge_membership (
        resource_id text PRIMARY KEY, set_id varchar(128) NOT NULL REFERENCES sets(set_id),
        origin text NOT NULL CHECK (origin IN ('production','pilot')))""")
    op.execute("""CREATE TABLE alpha_bridge_state (
        resource_id text PRIMARY KEY REFERENCES resources(id), resource_version integer NOT NULL,
        source_hash text NOT NULL, source_updated_at timestamptz NOT NULL,
        source_record jsonb NOT NULL)""")
    op.execute("""CREATE TABLE alpha_bridge_receipts (
        batch_id uuid PRIMARY KEY, request_hash text NOT NULL, result jsonb NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE alpha_bridge_evidence (
        batch_id uuid NOT NULL REFERENCES alpha_bridge_receipts(batch_id), ordinal integer NOT NULL,
        resource_id text, outcome text NOT NULL, source_record jsonb NOT NULL,
        PRIMARY KEY(batch_id,ordinal))""")
    op.execute("""CREATE TABLE alpha_catalog_seed (
        singleton boolean PRIMARY KEY CHECK(singleton), scope_hash text NOT NULL,
        pilot_hash text NOT NULL, pilot_count integer NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("CREATE INDEX alpha_bridge_review ON alpha_bridge_evidence(outcome,resource_id)")


def downgrade():
    for table in (
        "alpha_catalog_seed",
        "alpha_bridge_evidence",
        "alpha_bridge_receipts",
        "alpha_bridge_state",
        "alpha_bridge_membership",
    ):
        op.drop_table(table)
