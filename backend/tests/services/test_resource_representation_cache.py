from unittest.mock import AsyncMock

import pytest

import app.services.resource_representation_cache as resource_cache
from app.services.resource_representation_cache import (
    delete_durable_resource_representations,
    get_cached_resource_representations,
    get_or_build_resource_representation,
    resource_representation_cache_key,
    store_resource_representation,
    store_resource_representations,
)


class FakeCacheService:
    def __init__(self, values=None):
        self.values = values or {}
        self.set_calls = []
        self.set_many_calls = []
        self.tag_calls = []

    async def get_many(self, keys):
        return {key: self.values[key] for key in keys if key in self.values}

    async def set(self, key, value, ttl):
        self.set_calls.append((key, value, ttl))
        self.values[key] = value
        return True

    async def set_many(self, values, ttl):
        self.set_many_calls.append((values, ttl))
        self.values.update(values)
        return True

    async def tag_cache_key(self, key, tags, ttl_seconds):
        self.tag_calls.append((key, set(tags), ttl_seconds))


@pytest.mark.asyncio
async def test_get_cached_resource_representations_returns_copies():
    key = resource_representation_cache_key("r1", profile="api-full")
    cache_service = FakeCacheService(
        {
            key: {
                "id": "r1",
                "meta": {"ui": {"citation": "Original"}},
            }
        }
    )

    first = await get_cached_resource_representations(
        ["r1"],
        profile="api-full",
        cache_service=cache_service,
    )
    first["r1"]["meta"]["ui"]["citation"] = "Mutated"

    second = await get_cached_resource_representations(
        ["r1"],
        profile="api-full",
        cache_service=cache_service,
    )

    assert second["r1"]["meta"]["ui"]["citation"] == "Original"


@pytest.mark.asyncio
async def test_get_cached_resource_representations_rehydrates_redis_from_durable_store():
    cache_service = FakeCacheService()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            resource_cache,
            "get_durable_resource_representations",
            AsyncMock(return_value={"r1": {"id": "r1", "attributes": {"title": "Durable"}}}),
        )

        cached = await get_cached_resource_representations(
            ["r1"],
            cache_service=cache_service,
        )

    assert cached["r1"]["attributes"]["title"] == "Durable"
    assert len(cache_service.set_calls) == 0
    assert len(cache_service.tag_calls) == 1
    key = resource_representation_cache_key("r1", profile="api-full")
    assert cache_service.values[key]["attributes"]["title"] == "Durable"


@pytest.mark.asyncio
async def test_get_or_build_resource_representation_stores_miss():
    cache_service = FakeCacheService()

    async def builder(resource_dict):
        return {"id": resource_dict["id"], "attributes": {"title": "Built"}}

    with pytest.MonkeyPatch.context() as monkeypatch:
        mock_store_durable = AsyncMock(return_value=True)
        monkeypatch.setattr(
            resource_cache,
            "store_durable_resource_representation",
            mock_store_durable,
        )

        resource = await get_or_build_resource_representation(
            {"id": "r1"},
            builder,
            cache_service=cache_service,
        )

    assert resource["attributes"]["title"] == "Built"
    assert len(cache_service.set_calls) == 1
    assert len(cache_service.tag_calls) == 1
    assert "resource:r1" in cache_service.tag_calls[0][1]
    mock_store_durable.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_resource_representation_persists_durable_when_redis_set_fails():
    class FailingCacheService(FakeCacheService):
        async def set(self, key, value, ttl):
            self.set_calls.append((key, value, ttl))
            return False

    cache_service = FailingCacheService()

    with pytest.MonkeyPatch.context() as monkeypatch:
        mock_store_durable = AsyncMock(return_value=True)
        monkeypatch.setattr(
            resource_cache,
            "store_durable_resource_representation",
            mock_store_durable,
        )

        await store_resource_representation(
            "r1",
            {"id": "r1"},
            cache_service=cache_service,
        )

    assert len(cache_service.set_calls) == 1
    assert cache_service.tag_calls == []
    mock_store_durable.assert_awaited_once_with(
        "r1",
        {"id": "r1"},
        profile="api-full",
        source_updated_at=None,
    )


@pytest.mark.asyncio
async def test_store_resource_representations_bulk_persists_and_tags_each_resource():
    cache_service = FakeCacheService()

    with pytest.MonkeyPatch.context() as monkeypatch:
        mock_store_durable = AsyncMock(return_value=True)
        monkeypatch.setattr(
            resource_cache,
            "store_durable_resource_representations",
            mock_store_durable,
        )

        await store_resource_representations(
            {
                "r1": {"id": "r1"},
                "r2": {"id": "r2"},
            },
            cache_service=cache_service,
        )

    assert len(cache_service.set_many_calls) == 1
    stored_values, ttl = cache_service.set_many_calls[0]
    assert ttl == resource_cache.RESOURCE_REPRESENTATION_CACHE_TTL
    assert stored_values[resource_representation_cache_key("r1", profile="api-full")] == {
        "id": "r1"
    }
    assert len(cache_service.tag_calls) == 2
    assert {"resource:r1", "resource:r2"} == {
        next(tag for tag in tags if tag.startswith("resource:"))
        for _key, tags, _ttl in cache_service.tag_calls
    }
    mock_store_durable.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_durable_resource_representations_noops_when_disabled(monkeypatch):
    monkeypatch.setattr(resource_cache, "RESOURCE_REPRESENTATION_DURABLE_STORE", "off")

    result = await delete_durable_resource_representations()

    assert result is False
