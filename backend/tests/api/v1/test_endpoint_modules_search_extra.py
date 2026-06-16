import json

import pytest


@pytest.fixture(autouse=True)
def disable_endpoint_cache(monkeypatch):
    from app.services import cache_service

    monkeypatch.setattr(cache_service, "ENDPOINT_CACHE", False)


@pytest.mark.asyncio
async def test_suggest_success(monkeypatch):
    from app.api.v1.endpoint_modules import search as se

    captured = {}

    class FakeSearchService:
        async def suggest(self, q, include_non_public=False):
            captured["include_non_public"] = include_non_public
            return {"data": ["a", "b"]}

    monkeypatch.setattr(se, "SearchService", lambda: FakeSearchService())
    resp = await se.suggest(q="abc", callback=None, request=None)
    assert hasattr(resp, "body")
    data = json.loads(resp.body)
    assert data.get("data") == ["a", "b"]
    assert captured["include_non_public"] is False


@pytest.mark.asyncio
async def test_search_error(monkeypatch):
    from app.api.v1.endpoint_modules import search as se

    class FakeSearchService:
        async def search(self, **kwargs):
            raise Exception("es error")

    monkeypatch.setattr(se, "SearchService", lambda: FakeSearchService())
    from starlette.datastructures import URL

    class DummyScope(dict):
        pass

    # Minimal Request-like object
    class DummyRequest:
        def __init__(self):
            self._url = URL("http://test/")
            self.query_params = ""

        @property
        def url(self):
            return self._url

    resp = await se.search(DummyRequest(), q=None, page=1, per_page=10, sort=None, callback=None)
    assert hasattr(resp, "body")
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_search_success(monkeypatch):
    from app.api.v1.endpoint_modules import search as se

    class FakeSearchService:
        async def search(self, **kwargs):
            # Minimal structure used by endpoint
            return {
                "data": [
                    {"id": "r1", "score": 0.9, "attributes": {"id": "r1"}},
                    {"id": "r2", "score": 0.8, "attributes": {"id": "r2"}},
                ],
                "meta": {"pages": {"total_count": 2, "total_pages": 1}, "suggestions": []},
                "queryTime": {},
                "included": [{"type": "agg", "id": "f"}],
            }

    # Patch DB session helpers to return simple lookups

    monkeypatch.setattr(se, "SearchService", lambda: FakeSearchService())

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/search?q=a")
            self.query_params = "q=a"

        @property
        def url(self):
            return self._url

    # Patch async_session used within module to avoid real DB
    class DummySession:
        async def execute(self, *args, **kwargs):
            class R:
                def fetchall(self_inner):
                    return []

            return R()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

    se.async_session = lambda: DummySession()

    resp = await se.search(DummyRequest(), q="a", page=1, per_page=10, sort=None, callback=None)
    assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_suggest_jsonp(monkeypatch):
    from app.api.v1.endpoint_modules import search as se

    captured = {}

    class FakeSearchService:
        async def suggest(self, q, include_non_public=False):
            captured["include_non_public"] = include_non_public
            return {"data": ["a"]}

    monkeypatch.setattr(se, "SearchService", lambda: FakeSearchService())

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/suggest?q=a&callback=cb")

        @property
        def url(self):
            return self._url

    resp = await se.suggest(
        q="a",
        callback="cb",
        request=DummyRequest(),
        include_non_public=True,
    )
    assert hasattr(resp, "body")
    assert captured["include_non_public"] is True
