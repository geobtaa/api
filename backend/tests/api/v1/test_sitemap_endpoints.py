from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_connection():
    yield


@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    yield


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_sitemap_xml_serves_cached_document(async_client, monkeypatch):
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""

    monkeypatch.setattr("app.main.get_sitemap_document", AsyncMock(return_value=sitemap_xml))

    response = await async_client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.text == sitemap_xml
    assert response.headers["content-type"].startswith("application/xml")


@pytest.mark.asyncio
async def test_sitemap_part_rejects_invalid_names(async_client):
    response = await async_client.get("/sitemaps/not-a-real-part.xml")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_robots_txt_uses_application_url(async_client, monkeypatch):
    monkeypatch.setenv("APPLICATION_URL", "https://geo.example.org")
    monkeypatch.setenv("SEARCH_ENGINE_INDEXING_ENABLED", "true")

    response = await async_client.get("/robots.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Disallow: /api/" in response.text
    assert "Disallow: /search?" in response.text
    assert "Sitemap: https://geo.example.org/sitemap.xml" in response.text


@pytest.mark.asyncio
async def test_robots_txt_blocks_indexing_when_feature_flag_is_disabled(async_client, monkeypatch):
    monkeypatch.delenv("SEARCH_ENGINE_INDEXING_ENABLED", raising=False)

    response = await async_client.get("/robots.txt")

    assert response.status_code == 200
    assert "User-agent: Googlebot" in response.text
    assert "User-agent: YandexBot" in response.text
    assert "Sitemap:" not in response.text
