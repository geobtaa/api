"""Durable invitation-first accounts, grants, sessions and security audit."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE identity_accounts (
actor_id UUID NOT NULL,
lock_version INTEGER DEFAULT '1' NOT NULL,
active BOOLEAN DEFAULT 'true' NOT NULL,
all_lifecycles BOOLEAN DEFAULT 'false' NOT NULL,
updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
PRIMARY KEY (actor_id),
FOREIGN KEY(actor_id) REFERENCES actors (id)
)
""")
    op.execute("""
CREATE TABLE identity_permissions (
actor_id UUID NOT NULL,
permission VARCHAR(100) NOT NULL,
PRIMARY KEY (actor_id, permission),
FOREIGN KEY(actor_id) REFERENCES identity_accounts (actor_id)
)
""")
    op.execute("""
CREATE TABLE identity_lifecycle_grants (
actor_id UUID NOT NULL,
lifecycle_id UUID NOT NULL,
PRIMARY KEY (actor_id, lifecycle_id),
FOREIGN KEY(actor_id) REFERENCES identity_accounts (actor_id),
FOREIGN KEY(lifecycle_id) REFERENCES lifecycles (lifecycle_id)
)
""")
    op.execute("""
CREATE TABLE identity_invitations (
invitation_id UUID NOT NULL,
token_hash VARCHAR(64) NOT NULL,
idp_entity_id TEXT NOT NULL,
permissions TEXT[] NOT NULL,
lifecycle_ids UUID[] NOT NULL,
all_lifecycles BOOLEAN NOT NULL,
created_by_actor_id UUID NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
redeemed_by_actor_id UUID,
redeemed_at TIMESTAMP WITH TIME ZONE,
revoked_at TIMESTAMP WITH TIME ZONE,
PRIMARY KEY (invitation_id),
CONSTRAINT invitation_expiry CHECK (expires_at > created_at),
UNIQUE (token_hash),
FOREIGN KEY(created_by_actor_id) REFERENCES actors (id),
FOREIGN KEY(redeemed_by_actor_id) REFERENCES actors (id)
)
""")
    op.execute("""
CREATE TABLE identity_sessions (
token_hash VARCHAR(64) NOT NULL,
actor_id UUID NOT NULL,
authentication_context TEXT NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
revoked_at TIMESTAMP WITH TIME ZONE,
PRIMARY KEY (token_hash),
CONSTRAINT session_expiry CHECK (expires_at > created_at),
FOREIGN KEY(actor_id) REFERENCES identity_accounts (actor_id)
)
""")
    op.execute("""
CREATE TABLE security_audit (
event_id UUID NOT NULL,
actor_id UUID,
target_actor_id UUID,
action TEXT NOT NULL,
details JSONB DEFAULT '{}' NOT NULL,
occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
PRIMARY KEY (event_id),
CONSTRAINT security_action CHECK (action IN
('invitation.created','invitation.revoked','invitation.redeemed','session.created','session.revoked','account.changed','signin.rejected')),
FOREIGN KEY(actor_id) REFERENCES actors (id),
FOREIGN KEY(target_actor_id) REFERENCES actors (id)
)
""")


def downgrade():
    op.execute("""
DO $$ BEGIN IF EXISTS (SELECT 1 FROM identity_accounts)
OR EXISTS (SELECT 1 FROM security_audit)
THEN RAISE EXCEPTION 'Identity history must not be discarded'; END IF; END $$
""")
    op.drop_table("security_audit")
    op.drop_table("identity_sessions")
    op.drop_table("identity_invitations")
    op.drop_table("identity_lifecycle_grants")
    op.drop_table("identity_permissions")
    op.drop_table("identity_accounts")
