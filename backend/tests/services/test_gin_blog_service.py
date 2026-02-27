from datetime import datetime

from app.services.gin_blog_service import GINBlogService


def test_normalize_item_from_frontmatter():
    service = GINBlogService()
    raw = """---
title: Test Story
date: 2026-02-02T15:22:00.000-06:00
excerpt: Story excerpt.
authors:
  - name: BTAA-GIN Staff
tags:
  - Program Updates
cover:
  image: "@images/aerialneighborhood.jpg"
  alt: Example alt text
draft: false
---
Body content.
"""
    item = {
        "path": "src/content/docs/updates/2026-02-02-january-2026-program-update.mdx",
        "sha": "abc123",
    }
    normalized = service._normalize_item(item, raw)
    assert normalized is not None
    assert normalized["slug"] == "2026-02-02-january-2026-program-update"
    assert normalized["category"] == "update"
    assert normalized["url"].endswith("/updates/2026-02-02-january-2026-program-update/")
    assert normalized["authors_json"] == ["BTAA-GIN Staff"]
    assert normalized["tags_json"] == ["Program Updates"]
    assert normalized["image_alt"] == "Example alt text"
    assert normalized["image_url"] == (
        "https://raw.githubusercontent.com/geobtaa/geobtaa.github.io/main/src/assets/images/"
        "aerialneighborhood.jpg"
    )
    assert isinstance(normalized["published_at"], datetime)


def test_normalize_item_ignores_drafts():
    service = GINBlogService()
    raw = """---
title: Draft Story
date: 2026-02-02
draft: true
---
Hidden content.
"""
    item = {"path": "src/content/docs/posts/draft-post.mdx", "sha": "def456"}
    assert service._normalize_item(item, raw) is None
