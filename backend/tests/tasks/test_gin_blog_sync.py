from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.gin_blog_sync import HOME_BLOG_CACHE_TAGS, run_gin_blog_sync


@pytest.mark.asyncio
async def test_run_gin_blog_sync_connects_and_invalidates_cache():
    mock_service = MagicMock()
    mock_service.sync_posts_from_github = AsyncMock(return_value={"upserted": 1})
    mock_cache = MagicMock()
    mock_cache.invalidate_tags = AsyncMock(return_value=2)

    with (
        patch("app.tasks.gin_blog_sync.database") as mock_database,
        patch("app.tasks.gin_blog_sync.GINBlogService", return_value=mock_service),
        patch("app.tasks.gin_blog_sync.CacheService", return_value=mock_cache),
    ):
        mock_database.is_connected = False
        mock_database.connect = AsyncMock()

        result = await run_gin_blog_sync()

    assert result == {"upserted": 1}
    mock_database.connect.assert_awaited_once()
    mock_service.sync_posts_from_github.assert_awaited_once_with()
    mock_cache.invalidate_tags.assert_awaited_once_with(HOME_BLOG_CACHE_TAGS)


@pytest.mark.asyncio
async def test_run_gin_blog_sync_returns_result_when_cache_invalidation_fails():
    mock_service = MagicMock()
    mock_service.sync_posts_from_github = AsyncMock(return_value={"upserted": 3})
    mock_cache = MagicMock()
    mock_cache.invalidate_tags = AsyncMock(side_effect=Exception("redis unavailable"))

    with (
        patch("app.tasks.gin_blog_sync.database") as mock_database,
        patch("app.tasks.gin_blog_sync.GINBlogService", return_value=mock_service),
        patch("app.tasks.gin_blog_sync.CacheService", return_value=mock_cache),
    ):
        mock_database.is_connected = True
        mock_database.connect = AsyncMock()

        result = await run_gin_blog_sync()

    assert result == {"upserted": 3}
    mock_database.connect.assert_not_called()
    mock_service.sync_posts_from_github.assert_awaited_once_with()
    mock_cache.invalidate_tags.assert_awaited_once_with(HOME_BLOG_CACHE_TAGS)
