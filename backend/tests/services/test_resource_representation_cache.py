import pytest

from app.services.resource_representation_cache import (
    get_cached_resource_representations,
    get_or_build_resource_representation,
    resource_representation_cache_key,
    store_resource_representation,
)


class FakeCacheService:
    def __init__(self, values=None):
        self.values = values or {}
        self.set_calls = []
        self.tag_calls = []

    async def get_many(self, keys):
        return {key: self.values[key] for key in keys if key in self.values}

    async def set(self, key, value, ttl):
        self.set_calls.append((key, value, ttl))
        self.values[key] = value
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
async def test_get_or_build_resource_representation_stores_miss():
    cache_service = FakeCacheService()

    async def builder(resource_dict):
        return {"id": resource_dict["id"], "attributes": {"title": "Built"}}

    resource = await get_or_build_resource_representation(
        {"id": "r1"},
        builder,
        cache_service=cache_service,
    )

    assert resource["attributes"]["title"] == "Built"
    assert len(cache_service.set_calls) == 1
    assert len(cache_service.tag_calls) == 1
    assert "resource:r1" in cache_service.tag_calls[0][1]


@pytest.mark.asyncio
async def test_store_resource_representation_skips_tags_when_set_fails():
    class FailingCacheService(FakeCacheService):
        async def set(self, key, value, ttl):
            self.set_calls.append((key, value, ttl))
            return False

    cache_service = FailingCacheService()

    await store_resource_representation(
        "r1",
        {"id": "r1"},
        cache_service=cache_service,
    )

    assert len(cache_service.set_calls) == 1
    assert cache_service.tag_calls == []
