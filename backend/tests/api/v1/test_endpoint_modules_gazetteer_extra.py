import json

import pytest


@pytest.mark.asyncio
async def test_list_gazetteers_success(monkeypatch):
    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def fake_fetch_val(query):
        return 1

    monkeypatch.setattr(gaz.database, "fetch_val", fake_fetch_val)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers")

        @property
        def url(self):
            return self._url

    resp = await gaz.list_gazetteers(request=DummyRequest())
    assert hasattr(resp, "body")
    data = json.loads(resp.body)
    assert "data" in data
    assert any(item.get("id") == "wof" for item in data.get("data", []))


@pytest.mark.asyncio
async def test_search_all_gazetteers_invalid():
    from fastapi import HTTPException

    from app.api.v1.endpoint_modules import gazetteer as gaz

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/search")

        @property
        def url(self):
            return self._url

    with pytest.raises(HTTPException) as exc:
        await gaz.search_all_gazetteers(
            request=DummyRequest(), q="x", gazetteer="bad", limit=10, offset=0
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_search_all_gazetteers_combined(monkeypatch):
    from starlette.responses import JSONResponse

    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def fake_resp(name):
        return JSONResponse({"data": [{"id": name}]})

    monkeypatch.setattr(gaz, "search_geonames", lambda request, q, limit, o: fake_resp("geonames"))
    monkeypatch.setattr(gaz, "search_wof", lambda request, q, limit, o: fake_resp("wof"))
    monkeypatch.setattr(gaz, "search_btaa", lambda request, q, limit, o: fake_resp("btaa"))

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/search")

        @property
        def url(self):
            return self._url

    combined = await gaz.search_all_gazetteers(
        request=DummyRequest(), q="x", gazetteer=None, limit=10, offset=0
    )
    # Function may be cached and return JSONResponse; handle both
    if hasattr(combined, "body"):
        data = json.loads(combined.body)
        assert set(data.keys()) == {"geonames", "wof", "btaa"}
    else:
        assert set(combined.keys()) == {"geonames", "wof", "btaa"}


@pytest.mark.asyncio
async def test_search_geonames_success(monkeypatch):
    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def fake_fetch_all(query):
        # one row with expected fields for geonames path
        return [{"geonameid": 1, "name": "X", "asciiname": "X", "alternatenames": ""}]

    monkeypatch.setattr(gaz.database, "fetch_all", fake_fetch_all)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/geonames/search?q=abc")
            self.query_params = "q=abc&limit=10&offset=0"

        @property
        def url(self):
            return self._url

    resp = await gaz.search_geonames(request=DummyRequest(), q="abc", limit=10, offset=0)
    assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_search_geonames_pagination(monkeypatch):
    import json

    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def fake_fetch_all(query):
        # two rows to trigger next link when limit=1
        return [
            {"geonameid": 1, "name": "A", "asciiname": "A", "alternatenames": ""},
            {"geonameid": 2, "name": "B", "asciiname": "B", "alternatenames": ""},
        ]

    monkeypatch.setattr(gaz.database, "fetch_all", fake_fetch_all)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/geonames/search?q=abc&limit=1&offset=0")
            self.query_params = "q=abc&limit=1&offset=0"

        @property
        def url(self):
            return self._url

    resp = await gaz.search_geonames(request=DummyRequest(), q="abc", limit=1, offset=0)
    body = json.loads(resp.body)
    assert "links" in body


@pytest.mark.asyncio
async def test_search_wof_success(monkeypatch):
    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def fake_fetch_all(query):
        return [{"wok_id": 2, "name": "Y", "placetype": "place"}]

    monkeypatch.setattr(gaz.database, "fetch_all", fake_fetch_all)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/wof/search?q=abc")
            self.query_params = "q=abc&limit=10&offset=0"

        @property
        def url(self):
            return self._url

    resp = await gaz.search_wof(request=DummyRequest(), q="abc", limit=10, offset=0)
    assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_search_btaa_success(monkeypatch):
    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def fake_fetch_all(query):
        return [{"id": 3, "fast_area": "Area"}]

    monkeypatch.setattr(gaz.database, "fetch_all", fake_fetch_all)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/btaa/search?q=abc")
            self.query_params = "q=abc&limit=10&offset=0"

        @property
        def url(self):
            return self._url

    resp = await gaz.search_btaa(request=DummyRequest(), q="abc", limit=10, offset=0)
    assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_search_btaa_error(monkeypatch):
    from fastapi import HTTPException

    from app.api.v1.endpoint_modules import gazetteer as gaz

    async def raise_exc(query):
        raise Exception("db")

    monkeypatch.setattr(gaz.database, "fetch_all", raise_exc)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/gazetteers/btaa/search")

        @property
        def url(self):
            return self._url

    with pytest.raises(HTTPException) as exc:
        await gaz.search_btaa(request=DummyRequest(), q="x", limit=10, offset=0)
    assert exc.value.status_code == 500
