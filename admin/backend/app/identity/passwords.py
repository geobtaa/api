"""Provision local alpha identities and issue opaque server-side sessions."""

import asyncio
import secrets
from datetime import timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.auth import SESSION_READ_PERMISSION
from app.domain import DomainError
from app.identity import service
from app.identity.actors import actor_identity
from app.identity.models import accounts, grants, local_credentials, login_limits, sessions
from app.persistence import actors
from app.sets.models import commands

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


async def provision(engine, actor, command, key, *, reset=False, bootstrap=False):
    """Only the operator bootstrap may omit an authenticated administrator."""
    if not bootstrap:
        service.manage(actor, [] if reset else {*command.permissions, SESSION_READ_PERMISSION})
    operation = "local-password:reset" if reset else "local-password:provision"
    digest = service.token_hash(command.model_dump_json())
    async with engine.begin() as conn:
        if bootstrap:
            await conn.execute(select(func.pg_advisory_xact_lock(829163305)))
            if await conn.scalar(select(local_credentials.c.actor_id).limit(1)):
                raise DomainError(409, "already_initialized", "Alpha accounts already initialized")
        administrator = None if bootstrap else await actor_identity(conn, actor)
        await conn.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(command.email, 0)))
        )
        row = (
            (
                await conn.execute(
                    select(local_credentials)
                    .where(local_credentials.c.email == command.email)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if reset and row:
            target_id = row["actor_id"]
            active = await conn.scalar(
                select(accounts.c.active).where(accounts.c.actor_id == target_id).with_for_update()
            )
            if not active:
                raise DomainError(409, "inactive_account", "The account is inactive")
            service.manage(
                actor,
                (
                    await conn.scalars(
                        select(grants.c.permission).where(grants.c.actor_id == target_id)
                    )
                ).all(),
            )
        if administrator:
            receipt = (
                (
                    await conn.execute(
                        select(commands).where(
                            commands.c.actor_id == administrator,
                            commands.c.idempotency_key == key,
                            commands.c.operation == operation,
                        )
                    )
                )
                .mappings()
                .first()
            )
            if receipt:
                if receipt["request_hash"] != digest:
                    raise DomainError(409, "idempotency_conflict", "Request key already used")
                return {**receipt["response"], "setup_code": None}
        if reset and not row:
            raise DomainError(404, "not_found", "Local account not found")
        if row and not reset:
            raise DomainError(409, "existing_account", "Local account already exists")
        if not reset:
            target_id = uuid4()
            await conn.execute(
                insert(actors).values(
                    id=target_id,
                    kind="user",
                    subject_key=f"local:{target_id}",
                    display_name=command.email,
                )
            )
            await conn.execute(
                insert(accounts).values(actor_id=target_id, all_sets=command.set_ids is None)
            )
            await service.write_grants(
                conn, target_id, {*command.permissions, SESSION_READ_PERMISSION}, command.set_ids
            )
            await conn.execute(
                insert(local_credentials).values(actor_id=target_id, email=command.email)
            )
        code = secrets.token_urlsafe(32)
        expires = await conn.scalar(select(func.now() + timedelta(minutes=30)))
        await conn.execute(
            update(local_credentials)
            .where(local_credentials.c.actor_id == target_id)
            .values(
                password_hash=None, setup_hash=service.token_hash(code), setup_expires_at=expires
            )
        )
        await conn.execute(
            update(sessions)
            .where(sessions.c.actor_id == target_id, sessions.c.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await service.record(
            conn, "account.changed", administrator, target_id, {"operation": operation}
        )
        result = {"actor_id": str(target_id), "expires_at": expires.isoformat()}
        if administrator:
            await conn.execute(
                insert(commands).values(
                    actor_id=administrator,
                    idempotency_key=key,
                    operation=operation,
                    request_hash=digest,
                    response=result,
                )
            )
        return {**result, "setup_code": code}


async def throttle(engine, email, peer):
    async with engine.begin() as conn:
        await conn.execute(delete(login_limits).where(login_limits.c.expires_at <= func.now()))
        # Count the peer first to bound both password work and per-email storage.
        for value, maximum in ((f"peer:{peer}", 100), (f"email:{email}", 10)):
            bucket = service.token_hash(value)
            stmt = pg_insert(login_limits).values(
                bucket=bucket, expires_at=func.now() + timedelta(minutes=15), attempts=1
            )
            count = await conn.scalar(
                stmt.on_conflict_do_update(
                    index_elements=["bucket"], set_={"attempts": login_limits.c.attempts + 1}
                ).returning(login_limits.c.attempts)
            )
            if count > maximum:
                return False
    return True


async def login(engine, command, peer, ttl):
    if not await throttle(engine, command.email, peer):
        raise DomainError(429, "rate_limited", "Too many attempts. Try again later.")
    result = None
    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    select(local_credentials, accounts.c.active)
                    .join(accounts)
                    .where(local_credentials.c.email == command.email)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        password = command.password.get_secret_value()
        if command.setup_code is not None:
            code_hash = service.token_hash(command.setup_code.get_secret_value())
            valid = (
                row
                and row["active"]
                and row["setup_hash"]
                and secrets.compare_digest(code_hash, row["setup_hash"])
                and row["setup_expires_at"] > await conn.scalar(select(func.clock_timestamp()))
            )
            if valid:
                encoded = await asyncio.to_thread(hasher.hash, password)
                await conn.execute(
                    update(local_credentials)
                    .where(local_credentials.c.actor_id == row["actor_id"])
                    .values(password_hash=encoded, setup_hash=None, setup_expires_at=None)
                )
                await service.record(
                    conn,
                    "account.changed",
                    row["actor_id"],
                    row["actor_id"],
                    {"operation": "password.set"},
                )
        else:
            encoded = (
                row["password_hash"]
                if row and row["active"] and row["password_hash"]
                else dummy_hash
            )
            try:
                valid = (
                    await asyncio.to_thread(hasher.verify, encoded, password)
                    and encoded != dummy_hash
                )
            except VerifyMismatchError:
                valid = False
        if valid:
            result = await service.issue_session(conn, row["actor_id"], "local-password", ttl)
        else:
            await service.record(conn, "signin.rejected")
    if not result:
        raise DomainError(401, "invalid_credentials", "Sign-in details are incorrect or expired")
    return result
