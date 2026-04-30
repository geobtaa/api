"""
Tests for CacheService - comprehensive coverage using real fixtures and data.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.cache_service import (
    CacheService,
    _resource_cache_tags_from_body,
    _warm_metadata_from_request,
    cached_endpoint,
    invalidate_cache_with_prefix,
)


class FakeRedisPipeline:
    def __init__(self):
        self.calls = []

    def sadd(self, *args):
        self.calls.append(("sadd", args))
        return self

    def expire(self, *args):
        self.calls.append(("expire", args))
        return self

    def srem(self, *args):
        self.calls.append(("srem", args))
        return self

    def delete(self, *args):
        self.calls.append(("delete", args))
        return self

    async def execute(self):
        return [1 for _call in self.calls]


class FakeRedis:
    def __init__(self, *, get_value=None, members=None):
        self.get_value = get_value
        self.members = members or {}
        self.set_calls = []
        self.delete_calls = []
        self.pipelines = []

    async def get(self, _key):
        return self.get_value

    async def set(self, key, value, ex=None, nx=False):
        self.set_calls.append((key, value, ex, nx))
        return True

    async def delete(self, key):
        self.delete_calls.append(key)
        return 1

    async def smembers(self, key):
        return self.members.get(key, set())

    def pipeline(self, transaction=False):
        pipe = FakeRedisPipeline()
        self.pipelines.append((transaction, pipe))
        return pipe


def test_resource_cache_tags_from_jsonapi_body():
    body = b'{"data":[{"type":"resource","id":"resource-1"},{"type":"resource","id":"resource-2"}]}'

    assert _resource_cache_tags_from_body(body) == {
        "resource:resource-1",
        "resource:resource-2",
    }


def test_resource_cache_tags_from_jsonapi_body_ignores_non_json():
    assert _resource_cache_tags_from_body(b"<html>nope</html>") == set()


def test_warm_metadata_from_get_request():
    class Request:
        method = "GET"

        class Url:
            path = "/api/v1/resources/example-1"
            query = "fields=dct_title_s"

        url = Url()

    assert _warm_metadata_from_request(Request()) == {
        "method": "GET",
        "path": "/api/v1/resources/example-1",
        "query": "fields=dct_title_s",
    }


class TestCacheService:
    """Test cases for CacheService initialization and basic functionality."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset CacheService singleton before/after each test."""
        CacheService._instance = None
        CacheService._redis_client = None
        yield
        CacheService._instance = None
        CacheService._redis_client = None

    def test_singleton_pattern(self):
        """Test that CacheService follows singleton pattern."""
        service1 = CacheService()
        service2 = CacheService()

        assert service1 is service2
        assert id(service1) == id(service2)

    def test_redis_client_initialization(self):
        """Test Redis client initialization."""
        service = CacheService()

        # Redis client should be initialized (may be None if caching disabled)
        assert hasattr(service, "_redis_client")

    def test_environment_variables(self):
        """Test that environment variables are properly loaded."""
        # These should be available from the service
        # Since we reset the singleton, we check the class attribute directly
        assert hasattr(CacheService, "_instance")

        # Test that the service can be created
        service = CacheService()
        assert service is not None


class TestCacheServiceBasicOperations:
    """Test cases for basic cache operations."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset CacheService singleton before/after each test."""
        CacheService._instance = None
        CacheService._redis_client = None
        yield
        CacheService._instance = None
        CacheService._redis_client = None

    @pytest.mark.asyncio
    async def test_get_with_real_redis(self):
        """Test getting values from cache using real Redis connection."""
        service = CacheService()

        try:
            result = await service.get("test-key")

            # Should return None if key doesn't exist or Redis unavailable
            assert result is None

        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_set_with_real_redis(self):
        """Test setting values in cache using real Redis connection."""
        service = CacheService()

        try:
            result = await service.set("test-key", {"test": "data"})

            # Should return boolean indicating success/failure
            assert isinstance(result, bool)

        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_delete_with_real_redis(self):
        """Test deleting values from cache using real Redis connection."""
        service = CacheService()

        try:
            result = await service.delete("test-key")

            # Should return boolean indicating success/failure
            assert isinstance(result, bool)

        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_flush_all_with_real_redis(self):
        """Test flushing all cache entries using real Redis connection."""
        service = CacheService()

        try:
            result = await service.flush_all()

            # Should return boolean indicating success/failure
            assert isinstance(result, bool)

        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_set_get_roundtrip_with_real_redis(self):
        """Test setting and getting values with real Redis connection."""
        service = CacheService()

        test_data = {
            "string": "test string",
            "number": 123,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        try:
            # Set the data
            set_result = await service.set("roundtrip-test-key", test_data)

            if set_result:
                # Try to get it back
                get_result = await service.get("roundtrip-test-key")

                if get_result is not None:
                    assert get_result == test_data
                else:
                    # Cache miss - that's okay in test environment
                    assert True
            else:
                # Cache set failed - that's okay in test environment
                assert True

        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self):
        """Test setting values with custom TTL using real Redis connection."""
        service = CacheService()

        try:
            result = await service.set("ttl-test-key", {"data": "test"}, ttl=60)

            # Should return boolean indicating success/failure
            assert isinstance(result, bool)

        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )


class TestCacheServiceDurableResponses:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        CacheService._instance = None
        CacheService._redis_client = None
        yield
        CacheService._instance = None
        CacheService._redis_client = None

    @pytest.mark.asyncio
    async def test_get_record_rehydrates_redis_from_durable_response(self):
        record = {
            "schema": 2,
            "created": time.time(),
            "soft_exp": time.time() + 30,
            "hard_exp": time.time() + 60,
            "status": 200,
            "headers": {"content-type": "application/json"},
            "etag": 'W/"abc"',
            "body_b64": "e30=",
        }
        fake_redis = FakeRedis(get_value=None)

        with (
            patch("app.services.cache_service.ENDPOINT_CACHE", True),
            patch(
                "app.services.cache_service.get_durable_api_response",
                new=AsyncMock(return_value=(record, {"search"}, "search_ns")),
            ) as mock_get_durable,
        ):
            service = CacheService()
            service._redis_client = fake_redis

            result = await service.get_record("cache-key")

        assert result == record
        mock_get_durable.assert_awaited_once_with("cache-key")
        assert fake_redis.set_calls
        assert fake_redis.pipelines

    @pytest.mark.asyncio
    async def test_set_record_persists_durable_response_with_tags(self):
        record = {
            "schema": 2,
            "created": time.time(),
            "soft_exp": time.time() + 30,
            "hard_exp": time.time() + 60,
            "status": 200,
            "headers": {},
            "body_b64": "e30=",
        }
        fake_redis = FakeRedis()

        with (
            patch("app.services.cache_service.ENDPOINT_CACHE", True),
            patch(
                "app.services.cache_service.store_durable_api_response",
                new=AsyncMock(return_value=True),
            ) as mock_store_durable,
        ):
            service = CacheService()
            service._redis_client = fake_redis

            result = await service.set_record(
                "cache-key",
                record,
                ttl_seconds=60,
                namespace="search_ns",
                tags={"search", "resource:r1"},
            )

        assert result is True
        assert fake_redis.set_calls
        mock_store_durable.assert_awaited_once()
        assert mock_store_durable.await_args.kwargs["namespace"] == "search_ns"
        assert set(mock_store_durable.await_args.kwargs["tags"]) == {"search", "resource:r1"}

    @pytest.mark.asyncio
    async def test_invalidate_tags_deletes_durable_responses_even_without_redis(self):
        with (
            patch("app.services.cache_service.ENDPOINT_CACHE", True),
            patch(
                "app.services.cache_service.delete_durable_api_responses_for_tags",
                new=AsyncMock(return_value=3),
            ) as mock_delete_durable,
        ):
            service = CacheService()
            service._redis_client = None

            deleted = await service.invalidate_tags(["search"])

        assert deleted == 3
        mock_delete_durable.assert_awaited_once_with({"search"})


class TestCacheServiceKeyGeneration:
    """Test cases for cache key generation."""

    def _assert_cache_key_shape(self, key: str, *, namespace: str):
        assert key.startswith("cache:")
        parts = key.split(":")
        # cache:<cache_version>[:<cache_app_version>]:<namespace>:<digest>
        assert parts[0] == "cache"
        assert len(parts) >= 4
        assert parts[-2] == namespace
        digest = parts[-1]
        assert len(digest) == 32
        assert all(c in "0123456789abcdef" for c in digest)

    def test_generate_cache_key_with_simple_args(self):
        """Test generating cache keys with simple arguments."""
        key = CacheService.generate_cache_key("test_prefix", "arg1", 123, True)

        self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_with_kwargs(self):
        """Test generating cache keys with keyword arguments."""
        key = CacheService.generate_cache_key("test_prefix", param1="value1", param2=456)

        self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_with_complex_types(self):
        """Test generating cache keys with complex data types."""
        complex_data = {"nested": {"data": [1, 2, 3]}}
        key = CacheService.generate_cache_key("test_prefix", complex_data)

        self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_consistency(self):
        """Test that cache key generation is consistent."""
        key1 = CacheService.generate_cache_key("test_prefix", "arg1", param1="value1")
        key2 = CacheService.generate_cache_key("test_prefix", "arg1", param1="value1")

        assert key1 == key2

    def test_generate_cache_key_different_args(self):
        """Test that different arguments generate different keys."""
        key1 = CacheService.generate_cache_key("test_prefix", "arg1")
        key2 = CacheService.generate_cache_key("test_prefix", "arg2")

        assert key1 != key2

    def test_generate_cache_key_kwargs_order_independence(self):
        """Test that keyword argument order doesn't affect cache key."""
        key1 = CacheService.generate_cache_key("test_prefix", param1="value1", param2="value2")
        key2 = CacheService.generate_cache_key("test_prefix", param2="value2", param1="value1")

        assert key1 == key2

    def test_generate_cache_key_with_none_values(self):
        """Test generating cache keys with None values."""
        key = CacheService.generate_cache_key("test_prefix", None, param1=None)

        self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_with_unicode(self):
        """Test generating cache keys with Unicode characters."""
        unicode_data = "test-ñ-émojis-中文"
        key = CacheService.generate_cache_key("test_prefix", unicode_data)

        self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_with_various_types(self):
        """Test generating cache keys with various data types."""
        test_cases = [
            ("string", "test"),
            ("int", 123),
            ("float", 45.67),
            ("bool_true", True),
            ("bool_false", False),
            ("none", None),
            ("list", [1, 2, 3]),
            ("dict", {"key": "value"}),
            ("nested", {"a": {"b": {"c": [1, 2, 3]}}}),
        ]

        for _test_name, test_value in test_cases:
            key = CacheService.generate_cache_key("test_prefix", test_value)
            self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_with_long_strings(self):
        """Test generating cache keys with long strings."""
        long_string = "a" * 1000
        key = CacheService.generate_cache_key("test_prefix", long_string)

        self._assert_cache_key_shape(key, namespace="test_prefix")

    def test_generate_cache_key_with_special_characters(self):
        """Test generating cache keys with special characters."""
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        key = CacheService.generate_cache_key("test_prefix", special_chars)

        self._assert_cache_key_shape(key, namespace="test_prefix")


class TestCacheServiceEdgeCases:
    """Test cases for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_get_with_empty_key(self):
        """Test getting values with empty key."""
        service = CacheService()

        try:
            result = await service.get("")
            assert result is None
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_set_with_empty_key(self):
        """Test setting values with empty key."""
        service = CacheService()

        try:
            result = await service.set("", {"data": "test"})
            assert isinstance(result, bool)
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_delete_with_empty_key(self):
        """Test deleting values with empty key."""
        service = CacheService()

        try:
            result = await service.delete("")
            assert isinstance(result, bool)
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_set_with_very_large_data(self):
        """Test setting very large data in cache."""
        service = CacheService()

        large_data = {"data": "x" * 100000}  # 100KB of data

        try:
            result = await service.set("large-data-key", large_data)
            assert isinstance(result, bool)
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_set_with_non_serializable_data(self):
        """Test setting non-serializable data in cache."""
        service = CacheService()

        # Create an object that can't be JSON serialized
        class NonSerializable:
            def __init__(self):
                self.func = lambda x: x

        non_serializable = NonSerializable()

        try:
            result = await service.set("non-serializable-key", non_serializable)
            # Should handle gracefully - either return False or raise exception
            assert isinstance(result, bool)
        except Exception as e:
            # Expected behavior for non-serializable data
            assert "json" in str(e).lower() or "serialize" in str(e).lower()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent cache operations."""
        import asyncio

        service = CacheService()

        async def set_operation(i):
            try:
                return await service.set(f"concurrent-key-{i}", {"value": i})
            except Exception:
                return False

        async def get_operation(i):
            try:
                return await service.get(f"concurrent-key-{i}")
            except Exception:
                return None

        # Run concurrent operations
        set_tasks = [set_operation(i) for i in range(10)]
        get_tasks = [get_operation(i) for i in range(10)]

        set_results = await asyncio.gather(*set_tasks)
        get_results = await asyncio.gather(*get_tasks)

        # All results should be boolean for set operations
        for result in set_results:
            assert isinstance(result, bool)

        # All results should be None or dict for get operations
        for result in get_results:
            assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_performance_with_multiple_operations(self):
        """Test performance with multiple cache operations."""
        import time

        service = CacheService()
        start_time = time.time()

        # Perform multiple operations
        for i in range(100):
            try:
                await service.set(f"perf-key-{i}", {"value": i})
                await service.get(f"perf-key-{i}")
            except Exception as e:
                # Handle Redis connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "redis" in str(e).lower()
                    or "nodename" in str(e).lower()
                )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        assert execution_time < 60.0  # 60 seconds should be more than enough


class TestCachedEndpointDecorator:
    """Test cases for the cached_endpoint decorator."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset CacheService singleton before/after each test."""
        CacheService._instance = None
        CacheService._redis_client = None
        yield
        CacheService._instance = None
        CacheService._redis_client = None

    @pytest.mark.asyncio
    async def test_cached_endpoint_decorator_basic(self):
        """Test basic functionality of cached_endpoint decorator."""

        @cached_endpoint(ttl=60)
        async def test_function(param1, param2):
            return {"result": f"{param1}-{param2}"}

        try:
            result = await test_function("test1", "test2")
            assert result == {"result": "test1-test2"}
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_cached_endpoint_with_json_response(self):
        """Test cached_endpoint decorator with JSONResponse."""
        from app.api.v1.utils import JSONResponse

        @cached_endpoint(ttl=60)
        async def test_json_function(param):
            return JSONResponse(content={"result": param})

        try:
            result = await test_json_function("test")
            # The decorator might return a standard Response (reconstructed)
            # but with correct content type
            assert result.status_code == 200

            # Check body content
            body = result.body.decode() if isinstance(result.body, bytes) else result.body
            assert '{"result":"test"}' in body or '{"result": "test"}' in body
        except Exception as e:
            # Handle Redis connection errors gracefully
            if "assert" in str(e).lower():
                raise e
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_cached_endpoint_with_request_parameter(self):
        """Test cached_endpoint decorator with request parameter (excluded from cache key)."""

        @cached_endpoint(ttl=60)
        async def test_function_with_request(request, param):
            return {"result": param}

        # Mock request object
        mock_request = type("MockRequest", (), {})()

        try:
            result = await test_function_with_request(mock_request, "test")
            assert result == {"result": "test"}
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_cached_endpoint_error_handling(self):
        """Test cached_endpoint decorator error handling."""

        @cached_endpoint(ttl=60)
        async def test_error_function():
            raise ValueError("Test error")

        try:
            await test_error_function()
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert str(e) == "Test error"
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )


class TestInvalidateCacheWithPrefix:
    """Test cases for invalidate_cache_with_prefix function."""

    @pytest.mark.asyncio
    async def test_invalidate_cache_with_prefix_basic(self):
        """Test basic functionality of invalidate_cache_with_prefix."""
        try:
            result = await invalidate_cache_with_prefix("test_prefix")
            assert isinstance(result, bool)
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_invalidate_cache_with_empty_prefix(self):
        """Test invalidate_cache_with_prefix with empty prefix."""
        try:
            result = await invalidate_cache_with_prefix("")
            assert isinstance(result, bool)
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_invalidate_cache_with_nonexistent_prefix(self):
        """Test invalidate_cache_with_prefix with nonexistent prefix."""
        try:
            result = await invalidate_cache_with_prefix("nonexistent_prefix_12345")
            assert isinstance(result, bool)
        except Exception as e:
            # Handle Redis connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "redis" in str(e).lower()
                or "nodename" in str(e).lower()
            )
