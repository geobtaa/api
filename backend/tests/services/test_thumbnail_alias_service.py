from unittest.mock import patch

from app.services.thumbnail_alias_service import ThumbnailAliasService


def test_get_hash_waits_through_redis_loading(monkeypatch):
    image_hash = "a" * 64
    service = ThumbnailAliasService()

    class LoadingOnceCache:
        calls = 0

        def get(self, _key):
            self.calls += 1
            if self.calls == 1:
                raise Exception("Redis is loading the dataset in memory")
            return image_hash

    cache = LoadingOnceCache()
    service.cache = cache
    monkeypatch.setenv("VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS", "1")
    monkeypatch.setenv("VISUAL_ASSET_REDIS_LOADING_RETRY_SECONDS", "0.05")

    with patch("app.services.visual_asset_cache.time.sleep") as mock_sleep:
        assert service.get_hash_sync("resource-1") == image_hash

    assert cache.calls == 2
    mock_sleep.assert_called_once()
