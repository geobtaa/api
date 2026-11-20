"""Immutable Resource search selections."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE resource_selections (
	selection_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	idempotency_key UUID NOT NULL,
	request_hash VARCHAR(64) NOT NULL,
	sealed BOOLEAN DEFAULT 'false' NOT NULL,
	query JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (selection_id),
	UNIQUE (actor_id, idempotency_key),
	FOREIGN KEY(actor_id) REFERENCES actors (id)
)""")
    op.execute("""CREATE TABLE resource_selection_items (
	selection_id UUID NOT NULL,
	resource_id VARCHAR(512) NOT NULL,
	lifecycle_id UUID NOT NULL,
	resource_version INTEGER NOT NULL,
	PRIMARY KEY (selection_id, resource_id),
	FOREIGN KEY(selection_id) REFERENCES resource_selections (selection_id),
	FOREIGN KEY(lifecycle_id) REFERENCES lifecycles (lifecycle_id)
)""")
    op.execute("""
CREATE FUNCTION seal_resource_selection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Selections are retained'; END IF;
    IF OLD.sealed OR NOT NEW.sealed OR (to_jsonb(OLD) - 'sealed') IS DISTINCT FROM
    (to_jsonb(NEW) - 'sealed') THEN RAISE EXCEPTION 'Selections are immutable'; END IF;
    RETURN NEW;
END $$
""")
    op.execute("""CREATE TRIGGER seal_resource_selection BEFORE UPDATE OR DELETE
        ON resource_selections FOR EACH ROW EXECUTE FUNCTION seal_resource_selection()""")
    op.execute("""
CREATE FUNCTION protect_resource_selection_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE frozen boolean;
BEGIN
    IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Selected versions are immutable'; END IF;
    SELECT sealed INTO frozen FROM resource_selections
    WHERE selection_id = NEW.selection_id FOR SHARE;
    IF frozen THEN RAISE EXCEPTION 'Selection is sealed'; END IF;
    RETURN NEW;
END $$
""")
    op.execute("""CREATE TRIGGER protect_resource_selection_item BEFORE INSERT OR UPDATE OR DELETE
        ON resource_selection_items FOR EACH ROW
        EXECUTE FUNCTION protect_resource_selection_item()""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM resource_selections) THEN
        RAISE EXCEPTION 'Cannot discard selected version history'; END IF; END $$""")
    op.drop_table("resource_selection_items")
    op.drop_table("resource_selections")
    op.execute("DROP FUNCTION protect_resource_selection_item()")
    op.execute("DROP FUNCTION seal_resource_selection()")
