"""Explicit current-account Set grants, independent of archived Lifecycle scope."""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE identity_accounts ADD COLUMN all_sets boolean NOT NULL DEFAULT false")
    op.execute(
        "ALTER TABLE identity_invitations ADD COLUMN all_sets boolean NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE identity_invitations ADD COLUMN set_ids text[] NOT NULL DEFAULT '{}'")
    op.execute("""CREATE TABLE identity_set_grants (
        actor_id uuid NOT NULL REFERENCES identity_accounts(actor_id),
        set_id varchar(128) NOT NULL REFERENCES sets(set_id),
        PRIMARY KEY (actor_id, set_id)
    )""")
    # Before this migration, every Set permission was global. Preserve that
    # exact catalog access for existing accounts/invitations; do not copy any
    # Lifecycle grants or confer Resource scope. New grants default to no Sets.
    op.execute("UPDATE identity_accounts SET all_sets = true")
    op.execute("UPDATE identity_invitations SET all_sets = true")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM identity_accounts WHERE NOT all_sets)
            OR EXISTS (SELECT 1 FROM identity_invitations WHERE NOT all_sets)
            OR EXISTS (SELECT 1 FROM identity_set_grants)
        THEN RAISE EXCEPTION 'Cannot discard scoped Set grants and broaden access';
        END IF;
    END $$""")
    op.execute("DROP TABLE identity_set_grants")
    op.execute("ALTER TABLE identity_invitations DROP COLUMN set_ids, DROP COLUMN all_sets")
    op.execute("ALTER TABLE identity_accounts DROP COLUMN all_sets")
