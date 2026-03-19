import pytest


@pytest.mark.asyncio
async def test_home_blog_posts_endpoint(async_client, monkeypatch):
    from app.api.v1.endpoint_modules import home as home_module

    async def mock_list_home_posts(*, limit, pinned_slugs, tag):
        assert limit == 2
        assert pinned_slugs == []
        assert tag is None
        return {
            "data": [
                {
                    "slug": "latest-slug",
                    "url": "https://gin.btaa.org/updates/pinned-slug/",
                    "title": "Pinned Story",
                    "excerpt": "Pinned excerpt",
                    "published_at": "2026-02-02T00:00:00",
                    "category": "update",
                    "authors": ["BTAA-GIN Staff"],
                    "tags": ["Program Updates"],
                    "image_url": None,
                    "image_alt": None,
                }
            ],
            "meta": {
                "pinned_slugs": [],
                "total_count": 1,
                "fetched_at": "2026-02-02T00:00:00",
            },
        }

    monkeypatch.setattr(home_module.gin_blog_service, "list_home_posts", mock_list_home_posts)

    response = await async_client.get("/api/v1/home/blog-posts?limit=2&theme=btaa")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total_count"] == 1
    assert payload["data"][0]["slug"] == "latest-slug"
