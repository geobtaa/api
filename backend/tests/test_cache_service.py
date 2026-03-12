import importlib
import os

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient


def _cache_test_redis_db() -> str:
    """Use a worker-specific Redis DB to avoid xdist tests flushing each other."""
    worker = os.getenv("PYTEST_XDIST_WORKER", "master")
    if worker == "master":
        return "15"
    try:
        worker_num = int(worker.removeprefix("gw"))
    except ValueError:
        return "15"
    # Redis commonly exposes 16 logical DBs (0-15). Reserve DB 15 for master and
    # use DBs 2-14 for xdist workers to avoid the session fixture's default DB 1.
    return str(2 + (worker_num % 13))


@pytest.mark.asyncio
async def test_success_response_caching_and_etag(monkeypatch):
    # Ensure cache_service module reads envs at import-time with caching enabled.
    monkeypatch.setenv("ENDPOINT_CACHE", "true")
    monkeypatch.setenv("CACHE_DEBUG_HEADERS", "true")
    monkeypatch.setenv("REDIS_DB", _cache_test_redis_db())

    import app.services.cache_service as cache_service_mod

    importlib.reload(cache_service_mod)

    cache_service = cache_service_mod.CacheService()
    if not cache_service._redis_client:
        pytest.skip("Redis client not initialized")
    try:
        await cache_service_mod._redis_call(cache_service._redis_client.ping())
    except Exception:
        pytest.skip("Redis not available")

    await cache_service.flush_all()

    app = FastAPI()

    @app.get("/test-success")
    @cache_service_mod.cached_endpoint(ttl=60)
    async def success_route(request: Request):
        return JSONResponse(content={"status": "success"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/test-success")
        assert r1.status_code == 200
        assert r1.headers.get("x-cache") == "MISS"
        etag = r1.headers.get("etag")
        assert etag

        r2 = await client.get("/test-success")
        assert r2.status_code == 200
        assert r2.headers.get("x-cache") in {"HIT", "STALE", "WAIT_HIT"}
        assert r2.headers.get("etag") == etag

        r3 = await client.get("/test-success", headers={"If-None-Match": etag})
        assert r3.status_code == 304
        assert r3.headers.get("etag") == etag


@pytest.mark.asyncio
async def test_query_string_normalization(monkeypatch):
    monkeypatch.setenv("ENDPOINT_CACHE", "true")
    monkeypatch.setenv("CACHE_DEBUG_HEADERS", "true")
    monkeypatch.setenv("REDIS_DB", _cache_test_redis_db())

    import app.services.cache_service as cache_service_mod

    importlib.reload(cache_service_mod)

    cache_service = cache_service_mod.CacheService()
    if not cache_service._redis_client:
        pytest.skip("Redis client not initialized")
    try:
        await cache_service_mod._redis_call(cache_service._redis_client.ping())
    except Exception:
        pytest.skip("Redis not available")

    await cache_service.flush_all()

    app = FastAPI()

    @app.get("/test-qs")
    @cache_service_mod.cached_endpoint(ttl=60)
    async def qs_route(request: Request):
        return JSONResponse(content={"ok": True})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/test-qs?a=1&b=2")
        assert r1.status_code == 200
        assert r1.headers.get("x-cache") == "MISS"

        r2 = await client.get("/test-qs?b=2&a=1")
        assert r2.status_code == 200
        assert r2.headers.get("x-cache") in {"HIT", "STALE", "WAIT_HIT"}


@pytest.mark.asyncio
async def test_error_response_not_cached(monkeypatch):
    monkeypatch.setenv("ENDPOINT_CACHE", "true")
    monkeypatch.setenv("CACHE_DEBUG_HEADERS", "true")
    monkeypatch.setenv("REDIS_DB", _cache_test_redis_db())

    import app.services.cache_service as cache_service_mod

    importlib.reload(cache_service_mod)

    cache_service = cache_service_mod.CacheService()
    if not cache_service._redis_client:
        pytest.skip("Redis client not initialized")
    try:
        await cache_service_mod._redis_call(cache_service._redis_client.ping())
    except Exception:
        pytest.skip("Redis not available")

    await cache_service.flush_all()

    app = FastAPI()

    @app.get("/test-error")
    @cache_service_mod.cached_endpoint(ttl=60)
    async def error_route(request: Request):
        raise HTTPException(status_code=404, detail="Not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/test-error")
        assert r1.status_code == 404

        r2 = await client.get("/test-error")
        assert r2.status_code == 404
