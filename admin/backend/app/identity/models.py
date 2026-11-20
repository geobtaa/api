"""Invitation-first accounts, current grants and hashed server sessions."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.persistence import metadata

accounts = Table(
    "identity_accounts",
    metadata,
    Column("actor_id", Uuid, ForeignKey("actors.id"), primary_key=True),
    Column("lock_version", Integer, nullable=False, server_default="1"),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("all_lifecycles", Boolean, nullable=False, server_default="false"),
    Column("all_sets", Boolean, nullable=False, server_default="false"),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
grants = Table(
    "identity_permissions",
    metadata,
    Column("actor_id", Uuid, ForeignKey("identity_accounts.actor_id"), primary_key=True),
    Column("permission", String(100), primary_key=True),
)
scopes = Table(
    "identity_lifecycle_grants",
    metadata,
    Column("actor_id", Uuid, ForeignKey("identity_accounts.actor_id"), primary_key=True),
    Column("lifecycle_id", Uuid, ForeignKey("lifecycles.lifecycle_id"), primary_key=True),
)
set_scopes = Table(
    "identity_set_grants",
    metadata,
    Column("actor_id", Uuid, ForeignKey("identity_accounts.actor_id"), primary_key=True),
    Column("set_id", String(128), ForeignKey("sets.set_id"), primary_key=True),
)
invitations = Table(
    "identity_invitations",
    metadata,
    Column("invitation_id", Uuid, primary_key=True),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("idp_entity_id", Text, nullable=False),
    Column("permissions", ARRAY(Text), nullable=False),
    Column("lifecycle_ids", ARRAY(Uuid), nullable=False),
    Column("all_lifecycles", Boolean, nullable=False),
    Column("set_ids", ARRAY(Text), nullable=False, server_default="{}"),
    Column("all_sets", Boolean, nullable=False, server_default="false"),
    Column("created_by_actor_id", Uuid, ForeignKey("actors.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("redeemed_by_actor_id", Uuid, ForeignKey("actors.id")),
    Column("redeemed_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("expires_at > created_at", name="invitation_expiry"),
)
sessions = Table(
    "identity_sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("actor_id", Uuid, ForeignKey("identity_accounts.actor_id"), nullable=False),
    Column("authentication_context", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("expires_at > created_at", name="session_expiry"),
)
audit = Table(
    "security_audit",
    metadata,
    Column("event_id", Uuid, primary_key=True),
    Column("actor_id", Uuid, ForeignKey("actors.id")),
    Column("target_actor_id", Uuid, ForeignKey("actors.id")),
    Column("action", Text, nullable=False),
    Column("details", JSONB, nullable=False, server_default="{}"),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "action IN ('invitation.created','invitation.revoked','invitation.redeemed',"
        "'session.created','session.revoked','account.changed','signin.rejected')",
        name="security_action",
    ),
)

local_credentials = Table(
    "identity_local_credentials",
    metadata,
    Column("actor_id", Uuid, ForeignKey("identity_accounts.actor_id"), primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", Text),
    Column("setup_hash", String(64), unique=True),
    Column("setup_expires_at", DateTime(timezone=True)),
)

login_limits = Table(
    "identity_login_limits",
    metadata,
    Column("bucket", String(64), primary_key=True),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column("attempts", Integer, nullable=False),
)
