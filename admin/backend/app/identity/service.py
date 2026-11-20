"""Durable authorization behind a separately verified federation boundary."""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, update

from app.auth import Actor
from app.domain import DomainError
from app.identity.actors import actor_identity
from app.identity.local_schemas import CATALOG_EDITOR_PERMISSIONS
from app.identity.models import (
    accounts,
    audit,
    grants,
    invitations,
    local_credentials,
    sessions,
    set_scopes,
)
from app.persistence import actors
from app.sets.models import commands, sets

PROVIDERS = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts/incommon_identity_providers.json").read_text()
)
ALLOWED_IDPS = frozenset(item["entity_id"] for item in PROVIDERS)
COOKIE = "__Host-geomg-session"


@dataclass(frozen=True)
class VerifiedIdentity:
    """Only a trusted server adapter may construct this after validating federation evidence."""

    idp_entity_id: str
    subject_id: str
    display_name: str
    authentication_context: str


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def identity_key(identity):
    return "federated:" + token_hash(json.dumps([identity.idp_entity_id, identity.subject_id]))


async def record(connection, action, actor_id=None, target_actor_id=None, details=None):
    await connection.execute(
        insert(audit).values(
            event_id=uuid4(),
            action=action,
            actor_id=actor_id,
            target_actor_id=target_actor_id,
            details=details or {},
        )
    )


async def resolve_actor(connection, subject):
    """Current grants for sessions and workers; no authority is copied from a token or job."""
    account = (
        (
            await connection.execute(
                select(accounts)
                .where(accounts.c.actor_id == subject["id"])
                .with_for_update(read=True)
            )
        )
        .mappings()
        .first()
    )
    if account is None or not account["active"]:
        return None
    permissions = (
        (
            await connection.execute(
                select(grants.c.permission).where(grants.c.actor_id == subject["id"])
            )
        )
        .scalars()
        .all()
    )
    local = subject["kind"] == "user" and subject["subject_key"].startswith("local:")
    if local:
        local = (
            await connection.scalar(
                select(local_credentials.c.actor_id).where(
                    local_credentials.c.actor_id == subject["id"]
                )
            )
            is not None
        )
    if local:
        administrator = account["all_sets"] and "identity:manage" in permissions
        permissions = CATALOG_EDITOR_PERMISSIONS.union(permissions if administrator else ())
    return Actor(
        subject["subject_key"],
        subject["kind"],
        subject["display_name"],
        subject["display_name"] if local else None,
        frozenset(permissions),
        frozenset(),  # Archived Lifecycle grants are never current Set authority.
        None
        if local or account["all_sets"]
        else frozenset(
            (
                await connection.scalars(
                    select(set_scopes.c.set_id).where(set_scopes.c.actor_id == subject["id"])
                )
            ).all()
        ),
    )


def manage(actor, permissions):
    if (
        actor.kind != "user"
        or "identity:manage" not in actor.permissions
        or actor.set_ids is not None
    ):
        raise DomainError(403, "permission_denied", "Global identity administration required")
    if not set(permissions).issubset(actor.permissions):
        raise DomainError(403, "permission_denied", "Cannot delegate permissions you do not hold")


async def write_grants(connection, actor_id, permissions, set_ids):
    await validate_scopes(connection, set_ids)
    await connection.execute(delete(grants).where(grants.c.actor_id == actor_id))
    await connection.execute(delete(set_scopes).where(set_scopes.c.actor_id == actor_id))
    if permissions:
        await connection.execute(
            insert(grants),
            [dict(actor_id=actor_id, permission=p) for p in sorted(set(permissions))],
        )
    if set_ids:
        await connection.execute(
            insert(set_scopes),
            [dict(actor_id=actor_id, set_id=value) for value in sorted(set(set_ids))],
        )


async def validate_scopes(connection, set_ids):
    for ids, table, column, label in ((set_ids, sets, sets.c.set_id, "Set"),):
        if ids:
            count = await connection.scalar(
                select(func.count()).select_from(table).where(column.in_(ids))
            )
            if count != len(set(ids)):
                raise DomainError(404, "not_found", f"{label} not found")


async def create_invitation(engine, actor, command, key):
    manage(actor, command.permissions)
    if command.idp_entity_id not in ALLOWED_IDPS:
        raise DomainError(422, "unknown_provider", "Choose an approved institution")
    async with engine.begin() as connection:
        administrator_id = await actor_identity(connection, actor)
        # Serialize administration by the existing actor identity before checking the receipt.
        await connection.execute(
            select(actors.c.id).where(actors.c.id == administrator_id).with_for_update()
        )
        old = (
            (
                await connection.execute(
                    select(invitations).where(invitations.c.invitation_id == key)
                )
            )
            .mappings()
            .first()
        )
        if old:
            if (
                old["created_by_actor_id"] != administrator_id
                or old["idp_entity_id"] != command.idp_entity_id
                or set(old["permissions"]) != set(command.permissions)
                or set(old["set_ids"]) != set(command.set_ids or [])
                or old["all_sets"] != (command.set_ids is None)
                or old["expires_at"] != command.expires_at
            ):
                raise DomainError(409, "idempotency_conflict", "Invitation key already used")
            return {"invitation_id": key, "token": None, "expires_at": old["expires_at"]}
        now = await connection.scalar(select(func.clock_timestamp()))
        if command.expires_at <= now:
            raise DomainError(422, "expired", "Invitation expiry must be in the future")
        await validate_scopes(connection, command.set_ids)
        token = secrets.token_urlsafe(32)
        await connection.execute(
            insert(invitations).values(
                invitation_id=key,
                token_hash=token_hash(token),
                idp_entity_id=command.idp_entity_id,
                permissions=sorted(set(command.permissions)),
                # Retained historical columns must never grant new Lifecycle authority.
                lifecycle_ids=[],
                all_lifecycles=False,
                set_ids=sorted(set(command.set_ids or [])),
                all_sets=command.set_ids is None,
                created_by_actor_id=administrator_id,
                expires_at=command.expires_at,
            )
        )
        await record(connection, "invitation.created", administrator_id)
        return {"invitation_id": key, "token": token, "expires_at": command.expires_at}


async def revoke_invitation(engine, actor, invitation_id):
    manage(actor, [])
    async with engine.begin() as connection:
        administrator_id = await actor_identity(connection, actor)
        row = (
            (
                await connection.execute(
                    select(invitations)
                    .where(invitations.c.invitation_id == invitation_id)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(404, "not_found", "Invitation not found")
        if row["revoked_at"] is None:
            await connection.execute(
                update(invitations)
                .where(invitations.c.invitation_id == invitation_id)
                .values(revoked_at=func.clock_timestamp())
            )
            await record(connection, "invitation.revoked", administrator_id)


async def establish_session(engine, identity, invitation_token, ttl_seconds, accepted_contexts):
    """Issue a session after verified identity and current invitation/account checks."""
    valid = (
        isinstance(identity, VerifiedIdentity)
        and identity.idp_entity_id in ALLOWED_IDPS
        and bool(identity.subject_id)
        and len(identity.subject_id) <= 1024
        and bool(identity.display_name.strip())
        and len(identity.display_name) <= 250
        and identity.authentication_context in accepted_contexts
    )
    if not valid or not ttl_seconds or ttl_seconds <= 0:
        async with engine.begin() as connection:
            await record(connection, "signin.rejected")
        raise DomainError(401, "signin_unavailable", "Institutional sign-in unavailable")
    key = identity_key(identity)
    result = None
    async with engine.begin() as connection:
        # Same identity sign-ins serialize even before an Actor exists.
        await connection.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
        subject = (
            (
                await connection.execute(
                    select(actors)
                    .where(actors.c.kind == "user", actors.c.subject_key == key)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if subject is None:
            invitation = (
                (
                    await connection.execute(
                        select(invitations)
                        .where(
                            invitations.c.token_hash == token_hash(invitation_token or ""),
                            invitations.c.idp_entity_id == identity.idp_entity_id,
                            invitations.c.expires_at > func.clock_timestamp(),
                            invitations.c.revoked_at.is_(None),
                            invitations.c.redeemed_at.is_(None),
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if invitation:
                actor_id = uuid4()
                await connection.execute(
                    insert(actors).values(
                        id=actor_id,
                        subject_key=key,
                        kind="user",
                        display_name=identity.display_name,
                    )
                )
                await connection.execute(
                    insert(accounts).values(
                        actor_id=actor_id,
                        all_sets=invitation["all_sets"],
                    )
                )
                await write_grants(
                    connection,
                    actor_id,
                    invitation["permissions"],
                    invitation["set_ids"],
                )
                await connection.execute(
                    update(invitations)
                    .where(invitations.c.invitation_id == invitation["invitation_id"])
                    .values(redeemed_at=func.clock_timestamp(), redeemed_by_actor_id=actor_id)
                )
                await record(connection, "invitation.redeemed", actor_id, actor_id)
                subject = {
                    "id": actor_id,
                    "subject_key": key,
                    "kind": "user",
                    "display_name": identity.display_name,
                }
        current = await resolve_actor(connection, subject) if subject else None
        if current:
            result = await issue_session(
                connection, subject["id"], identity.authentication_context, ttl_seconds
            )
        else:
            await record(connection, "signin.rejected")
    if result is None:
        raise DomainError(401, "signin_unavailable", "Institutional sign-in unavailable")
    return result


async def issue_session(connection, actor_id, context, ttl_seconds):
    token = secrets.token_urlsafe(32)
    expires = await connection.scalar(
        select(func.clock_timestamp() + timedelta(seconds=ttl_seconds))
    )
    await connection.execute(
        insert(sessions).values(
            token_hash=token_hash(token),
            actor_id=actor_id,
            authentication_context=context,
            expires_at=expires,
        )
    )
    await record(connection, "session.created", actor_id)
    return token, expires


async def authenticate_session(engine, token, accepted_contexts):
    if not token or len(token) > 256:
        return None
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            subject = (
                (
                    await connection.execute(
                        select(actors)
                        .join(sessions, sessions.c.actor_id == actors.c.id)
                        .where(
                            sessions.c.token_hash == token_hash(token),
                            sessions.c.revoked_at.is_(None),
                            sessions.c.expires_at > func.clock_timestamp(),
                            sessions.c.authentication_context.in_(accepted_contexts),
                        )
                    )
                )
                .mappings()
                .first()
            )
            return await resolve_actor(connection, subject) if subject else None


async def revoke_session(engine, token):
    async with engine.begin() as connection:
        actor_id = await connection.scalar(
            update(sessions)
            .where(
                sessions.c.token_hash == token_hash(token or ""), sessions.c.revoked_at.is_(None)
            )
            .values(revoked_at=func.clock_timestamp())
            .returning(sessions.c.actor_id)
        )
        if actor_id:
            await record(connection, "session.revoked", actor_id)


async def change_account(engine, actor, target_id, command, key):
    manage(actor, command.permissions)
    async with engine.begin() as connection:
        administrator_id = await actor_identity(connection, actor)
        exists = await connection.scalar(
            select(accounts.c.lock_version)
            .where(accounts.c.actor_id == target_id)
            .with_for_update()
        )
        if exists is None:
            raise DomainError(404, "not_found", "Account not found")
        manage(
            actor,
            (
                await connection.scalars(
                    select(grants.c.permission).where(grants.c.actor_id == target_id)
                )
            ).all(),
        )
        criteria = [
            commands.c.actor_id == administrator_id,
            commands.c.operation == f"identity:account:{target_id}",
            commands.c.idempotency_key == key,
        ]
        request_hash = token_hash(json.dumps(command.model_dump(mode="json"), sort_keys=True))
        previous = (await connection.execute(select(commands).where(*criteria))).mappings().first()
        if previous:
            if previous["request_hash"] != request_hash:
                raise DomainError(409, "idempotency_conflict", "Account command key already used")
            return previous["response"]
        if exists != command.lock_version:
            raise DomainError(
                409, "stale_version", "Account grants changed. Reload before updating"
            )
        await write_grants(connection, target_id, command.permissions, command.set_ids)
        await connection.execute(
            update(accounts)
            .where(accounts.c.actor_id == target_id)
            .values(
                lock_version=accounts.c.lock_version + 1,
                active=command.active,
                all_sets=command.set_ids is None,
                updated_at=func.clock_timestamp(),
            )
        )
        if not command.active:
            await connection.execute(
                update(local_credentials)
                .where(local_credentials.c.actor_id == target_id)
                .values(setup_hash=None, setup_expires_at=None)
            )
            await connection.execute(
                update(sessions)
                .where(sessions.c.actor_id == target_id)
                .values(revoked_at=func.clock_timestamp())
            )
        await record(
            connection,
            "account.changed",
            administrator_id,
            target_id,
            command.model_dump(mode="json"),
        )
        result = {"actor_id": str(target_id), "lock_version": command.lock_version + 1}
        await connection.execute(
            insert(commands).values(
                actor_id=administrator_id,
                operation=f"identity:account:{target_id}",
                idempotency_key=key,
                request_hash=request_hash,
                response=result,
            )
        )
        return result


async def account_detail(engine, actor, target_id):
    manage(actor, [])
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            row = (
                (
                    await connection.execute(
                        select(accounts, actors.c.display_name)
                        .join(actors, actors.c.id == accounts.c.actor_id)
                        .where(accounts.c.actor_id == target_id)
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DomainError(404, "not_found", "Account not found")
            permissions = (
                (
                    await connection.execute(
                        select(grants.c.permission)
                        .where(grants.c.actor_id == target_id)
                        .order_by(grants.c.permission)
                    )
                )
                .scalars()
                .all()
            )
            return {
                "actor_id": target_id,
                "display_name": row["display_name"],
                "active": row["active"],
                "lock_version": row["lock_version"],
                "permissions": permissions,
                "set_ids": None
                if row["all_sets"]
                else list(
                    (
                        await connection.scalars(
                            select(set_scopes.c.set_id)
                            .where(set_scopes.c.actor_id == target_id)
                            .order_by(set_scopes.c.set_id)
                        )
                    ).all()
                ),
            }
