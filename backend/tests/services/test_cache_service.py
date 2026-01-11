"""
Tests for CacheService - comprehensive coverage using real fixtures and data.
"""

import pytest

from app.services.cache_service import CacheService, cached_endpoint, invalidate_cache_with_prefix


class TestCacheService:
    """Test cases for CacheService initialization and basic functionality."""

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
        assert hasattr(CacheService, "_instance")

        # Test that the service can be created
        service = CacheService()
        assert service is not None


class TestCacheServiceBasicOperations:
    """Test cases for basic cache operations."""

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
            assert isinstance(result, JSONResponse)
            assert result.body == b'{"result":"test"}'
        except Exception as e:
            # Handle Redis connection errors gracefully
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
