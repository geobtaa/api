"""Deliver committed GEOMG versions through the existing search and cache services."""

import asyncio
import logging
import os
from urllib.parse import quote

import httpx
from sqlalchemy import text

from app.elasticsearch.client import es
from app.services.bridge_sync.cache_refresh import refresh_cache_for_changed_resources
from app.services.bridge_sync.search_index import index_changed_resources
from app.services.relationship_sync import sync_relationships_for_resource_ids
from db.database import database

logger = logging.getLogger(__name__)


async def visible(client, resource_id, version, *, published, searchable):
    detail = await client.get("/api/v1/resources/" + quote(resource_id, safe=""))
    search = await client.post(
        "/api/v1/search",
        json={
            "adv_q": [{"op": "AND", "f": "id", "q": resource_id}],
            "per_page": 10,
        },
    )
    search.raise_for_status()

    def current(record):
        return (
            record.get("id") == resource_id
            and record.get("meta", {}).get("catalogVersion") == version
        )

    hits = search.json()["data"]
    if published:
        detail.raise_for_status()
        if not current(detail.json()["data"]):
            return False
    elif detail.status_code != 404:
        return False
    if not searchable:
        return not any(hit.get("id") == resource_id for hit in hits)
    indexed = await es.get(
        index=os.environ["ELASTICSEARCH_INDEX"], id=resource_id, source_includes=["lock_version"]
    )
    return indexed["_source"].get("lock_version") == version and any(current(hit) for hit in hits)


async def deliver_one(client):
    row = await database.fetch_one(
        text("""
        WITH claim AS (
            SELECT p.resource_id, p.resource_version, r.publication_state, r.gbl_suppressed_b
            FROM public.resource_projection_requests p
            JOIN public.resources r ON r.id=p.resource_id AND r.lock_version=p.resource_version
            WHERE p.visible_at IS NULL AND p.next_attempt_at<=now()
            ORDER BY p.next_attempt_at,p.created_at LIMIT 1 FOR UPDATE OF p SKIP LOCKED
        )
        UPDATE public.resource_projection_requests p SET next_attempt_at=now()+interval '5 minutes'
        FROM claim WHERE p.resource_id=claim.resource_id
        AND p.resource_version=claim.resource_version
        RETURNING claim.*,p.next_attempt_at AS lease
    """)
    )
    if not row:
        return False
    rid, version = row["resource_id"], row["resource_version"]
    delivered = False
    try:
        async with database.transaction():
            await sync_relationships_for_resource_ids([rid])
        index = await index_changed_resources([rid])
        if index.get("enabled") and not index.get("errors"):
            cache = await refresh_cache_for_changed_resources(
                [rid],
                warm_generated_assets=False,
                representation_version=os.environ["RESOURCE_REPRESENTATION_CACHE_VERSION"],
            )
            if cache.get("enabled") and not cache.get("errors"):
                published = row["publication_state"] == "published"
                delivered = await visible(
                    client,
                    rid,
                    version,
                    published=published,
                    searchable=published and not row["gbl_suppressed_b"],
                )
    except Exception:
        logger.exception("GEOMG projection retry for resource %s version %s", rid, version)
    await database.execute(
        text("""
        UPDATE public.resource_projection_requests p
        SET visible_at=CASE WHEN :delivered THEN clock_timestamp() ELSE NULL END,
            next_attempt_at=now()+interval '30 seconds'
        FROM public.resources r WHERE p.resource_id=:rid AND p.resource_version=:version
        AND r.id=p.resource_id AND r.lock_version=p.resource_version AND p.next_attempt_at=:lease
    """).bindparams(delivered=delivered, rid=rid, version=version, lease=row["lease"])
    )
    return True


async def main():
    if os.getenv("KAMAL_DEST") != "dev2" or os.getenv("GEOMG_CATALOG_ENABLED") != "true":
        raise RuntimeError("GEOMG projection requires the dev2 candidate catalog")
    if not os.environ.get("ELASTICSEARCH_INDEX", "").startswith("geomg_alpha_"):
        raise RuntimeError("Candidate index required")
    await database.connect()
    if not await database.fetch_val("SELECT EXISTS(SELECT FROM public.alpha_catalog_seed)"):
        raise RuntimeError("The unified catalog migration must complete first")
    try:
        async with httpx.AsyncClient(
            base_url=os.environ["GEOMG_CANDIDATE_API_ORIGIN"], timeout=20
        ) as client:
            while True:
                if not await deliver_one(client):
                    await asyncio.sleep(1)
    finally:
        await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
