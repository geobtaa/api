"""Separately runnable, bounded PostgreSQL worker with lease fencing."""

import argparse
import asyncio
import json
from datetime import timedelta
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, insert, or_, select, update

from app.auth import Actor
from app.config import get_settings
from app.database import get_engine
from app.domain import DomainError
from app.jobs.models import attempts, items, jobs
from app.jobs.service import REQUIRED, authorize, expire_artifacts, finish
from app.persistence import actors
from app.resources.editor import EDITABLE
from app.resources.models import distributions, resources
from app.resources.validation import VOCABULARY, normalize
from app.sets.models import sets

LEASE_SECONDS = 30
CHUNK_SIZE = 10


async def claim(engine):
    async with engine.begin() as connection:
        job = (
            (
                await connection.execute(
                    select(jobs)
                    .where(
                        or_(
                            jobs.c.state == "queued",
                            and_(
                                jobs.c.state == "running",
                                jobs.c.lease_until <= func.clock_timestamp(),
                            ),
                        )
                    )
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )
        if job is None:
            return None
        if job["state"] == "running":
            await connection.execute(
                update(attempts)
                .where(
                    attempts.c.job_id == job["job_id"], attempts.c.number == job["attempt_number"]
                )
                .values(state="expired", finished_at=func.clock_timestamp())
            )
        if job["attempt_number"] == 3:
            await connection.execute(
                update(items)
                .where(items.c.job_id == job["job_id"], items.c.disposition == "pending")
                .values(disposition="failed", details={"code": "attempts_exhausted"})
            )
            await finish(connection, job, "failed")
            return None
        token = uuid4()
        number = job["attempt_number"] + 1
        await connection.execute(
            update(jobs)
            .where(jobs.c.job_id == job["job_id"])
            .values(
                state="running",
                lease_token=token,
                attempt_number=number,
                lease_until=func.clock_timestamp() + timedelta(seconds=LEASE_SECONDS),
            )
        )
        await connection.execute(
            insert(attempts).values(
                job_id=job["job_id"], number=number, lease_token=token, state="running"
            )
        )
        return job["job_id"], token


async def step(engine, job_id, token, resolve_actor):
    """Resolve live authority each chunk. Exceptions roll back; a new lease recovers work."""
    async with engine.begin() as connection:
        # Set first, matching administrative commands and Resource services.
        set_id = await connection.scalar(select(jobs.c.set_id).where(jobs.c.job_id == job_id))
        set_state = await connection.scalar(
            select(sets.c.status).where(sets.c.set_id == set_id).with_for_update(read=True)
        )
        job = (
            (
                await connection.execute(
                    select(jobs)
                    .where(
                        jobs.c.job_id == job_id,
                        jobs.c.state == "running",
                        jobs.c.lease_token == token,
                        jobs.c.lease_until > func.clock_timestamp(),
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if job is None:
            return False
        subject = (
            (await connection.execute(select(actors).where(actors.c.id == job["actor_id"])))
            .mappings()
            .one()
        )
        actor = await resolve_actor(connection, subject)
        denied = set_state == "retired"
        try:
            authorize(
                actor,
                set_id,
                REQUIRED | ({"workflows:read"} if job["workflow_id"] else set()),
            )
            if actor.actor_id != subject["subject_key"] or actor.kind != subject["kind"]:
                denied = True
        except DomainError:
            denied = True
        if denied:
            await connection.execute(
                update(items)
                .where(items.c.job_id == job_id, items.c.disposition == "pending")
                .values(disposition="rejected", details={"code": "authorization_revoked"})
            )
            await finish(connection, job, "rejected")
            return False
        pending = (
            (
                await connection.execute(
                    select(items)
                    .where(items.c.job_id == job_id, items.c.disposition == "pending")
                    .order_by(items.c.position)
                    .limit(CHUNK_SIZE)
                )
            )
            .mappings()
            .all()
        )
        for item in pending:
            resource = (
                (
                    await connection.execute(
                        select(resources)
                        .where(
                            resources.c.id == item["resource_id"],
                            resources.c.set_id == set_id,
                        )
                        .with_for_update(read=True)
                    )
                )
                .mappings()
                .first()
            )
            if resource is None or resource["lock_version"] != item["resource_version"]:
                disposition, details = "conflicted", {"code": "resource_changed"}
            else:
                record = jsonable_encoder(
                    {k: v for k, v in resource.items() if k in EDITABLE and v is not None}
                )
                record["id"] = resource["id"]
                links = (
                    (
                        await connection.execute(
                            select(distributions)
                            .where(distributions.c.resource_id == resource["id"])
                            .order_by(distributions.c.position, distributions.c.id)
                        )
                    )
                    .mappings()
                    .all()
                )
                type_uris = {entry["id"]: entry["uri"] for entry in VOCABULARY}
                references = {}
                for link in links:
                    references.setdefault(type_uris[link["distribution_type_id"]], []).append(
                        {"url": link["url"], "label": link["label"]}
                    )
                record["dct_references_s"] = json.dumps(references)
                _, _, errors, warnings = normalize(record)
                disposition = "invalid" if errors else "unchanged"
                details = {"errors": errors, "warnings": warnings, "validation_scope": "draft"}
            await connection.execute(
                update(items)
                .where(items.c.job_id == job_id, items.c.position == item["position"])
                .values(disposition=disposition, details=details)
            )
        remaining = await connection.scalar(
            select(func.count())
            .select_from(items)
            .where(items.c.job_id == job_id, items.c.disposition == "pending")
        )
        if not remaining:
            from app.jobs.service import totals

            counts = await totals(connection, job_id)
            failed = sum(v for k, v in counts.items() if k != "unchanged")
            state = (
                "succeeded"
                if not failed
                else "partially_succeeded"
                if counts.get("unchanged")
                else "failed"
            )
            await finish(connection, job, state)
            return False
        await connection.execute(
            update(jobs)
            .where(jobs.c.job_id == job_id)
            .values(lease_until=func.clock_timestamp() + timedelta(seconds=LEASE_SECONDS))
        )
        return True


def development_resolver(settings):
    if settings.auth_mode != "development" or settings.app_env not in {"development", "test"}:
        raise RuntimeError(
            "Worker requires a live institutional actor resolver before production execution"
        )

    async def resolve(connection, subject):
        if subject["kind"] != "user" or subject["subject_key"] != settings.dev_auth_actor_id:
            return None
        return Actor(
            settings.dev_auth_actor_id,
            "user",
            settings.dev_auth_display_name,
            settings.dev_auth_email,
            frozenset(settings.dev_auth_permissions),
        )

    return resolve


async def run(once=False):
    settings = get_settings()
    if settings.auth_mode == "development":
        resolver = development_resolver(settings)
    else:
        from app.identity.service import resolve_actor

        resolver = resolve_actor
    engine = get_engine()
    try:
        while True:
            async with engine.begin() as connection:
                await expire_artifacts(connection)
            lease = await claim(engine)
            if lease:
                while await step(engine, *lease, resolver):
                    await asyncio.sleep(0)
            if once:
                return
            await asyncio.sleep(1)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process one available job and exit")
    asyncio.run(run(parser.parse_args().once))


if __name__ == "__main__":
    main()
