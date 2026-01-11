import pytest


def make_row(mapping: dict):
    class R:
        def __init__(self, m):
            self._mapping = m

    return R(mapping)


class DummySession:
    def __init__(self, fetchall_rows=None, fetchone_row=None, raise_on=None):
        self._fetchall_rows = fetchall_rows
        self._fetchone_row = fetchone_row
        self._raise_on = raise_on

    async def execute(self, *args, **kwargs):
        if self._raise_on == "execute":
            raise Exception("db error")

        class Res:
            def __init__(self, rows, one):
                self._rows = rows
                self._one = one

            def fetchall(self):
                return self._rows or []

            def fetchone(self):
                return self._one

        return Res(self._fetchall_rows, self._fetchone_row)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_list_resources_success(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    # Two fake rows
    rows = [make_row({"id": "r1"}), make_row({"id": "r2"})]
    res.async_session = lambda: DummySession(fetchall_rows=rows)

    async def fake_process_resource(resource_dict, session):
        return {"id": resource_dict["id"], "type": "resource", "attributes": resource_dict}

    monkeypatch.setattr(res, "process_resource", fake_process_resource)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/resources/?skip=0&limit=10")

        @property
        def url(self):
            return self._url

    resp = await res.list_resources(skip=0, limit=10, callback=None, request=DummyRequest())
    assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_list_resources_error(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(raise_on="execute")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await res.list_resources(skip=0, limit=10, callback=None, request=None)
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_get_resource_found(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    row = make_row({"id": "r1"})
    res.async_session = lambda: DummySession(fetchone_row=row)

    async def fake_process_resource(resource_dict, session):
        return {"id": resource_dict["id"], "type": "resource", "attributes": resource_dict}

    monkeypatch.setattr(res, "process_resource", fake_process_resource)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/resources/r1")

        @property
        def url(self):
            return self._url

    resp = await res.get_resource("r1", callback=None, request=DummyRequest())
    assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_get_resource_not_found(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(fetchone_row=None)
    resp = await res.get_resource("missing", callback=None, request=None)
    assert hasattr(resp, "body")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_resource_error(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    row = make_row({"id": "r1"})
    res.async_session = lambda: DummySession(fetchone_row=row)

    async def raise_process(resource_dict, session):
        raise Exception("processing")

    monkeypatch.setattr(res, "process_resource", raise_process)
    resp = await res.get_resource("r1", callback=None, request=None)
    assert hasattr(resp, "body")
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_get_resource_ogm_success(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    row = make_row({"id": "r1", "empty": "", "arr": [None, ""], "ok": ["x"]})
    res.async_session = lambda: DummySession(fetchone_row=row)

    class FakeMapper:
        @staticmethod
        def map_resource_fields(resource_dict):
            return resource_dict

    monkeypatch.setattr(res, "OGMFieldMapper", FakeMapper)
    resp = await res.get_resource_ogm("r1", callback="cb")
    # JSONP-like acceptable as JSONResponse/str body exists
    assert resp is not None


@pytest.mark.asyncio
async def test_get_resource_ogm_not_found(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(fetchone_row=None)
    resp = await res.get_resource_ogm("x", callback=None)
    assert hasattr(resp, "body")
    assert resp.status_code == 404


# Summaries endpoint tests removed - endpoint is commented out and not available
# If the endpoint is re-enabled, these tests should be restored

@pytest.mark.asyncio
async def test_get_resource_viewer_found(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    row = make_row({"id": "r1"})
    res.async_session = lambda: DummySession(fetchone_row=row)
    resp = await res.get_resource_viewer("r1", embed=False)
    # HTMLResponse
    assert hasattr(resp, "body")
    assert b"ogm-viewer" in resp.body


@pytest.mark.asyncio
async def test_get_resource_viewer_not_found(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(fetchone_row=None)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await res.get_resource_viewer("x", embed=False)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_resource_viewer_error(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(raise_on="execute")
    resp = await res.get_resource_viewer("r1", embed=False)
    assert hasattr(resp, "body")
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_get_resource_spatial_facets_exists(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    row = make_row({"id": "r1", "dcat_bbox": "BOX(0 0,1 1)"})
    res.async_session = lambda: DummySession(fetchone_row=row)

    class FakeSpatial:
        def __init__(self, rd):
            pass

        async def get_spatial_facets_with_wof_ids(self, session, debug=False):
            return {"country": "X"}

    monkeypatch.setattr(res, "SpatialFacetService", FakeSpatial)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/resources/r1/spatial_facets")

        @property
        def url(self):
            return self._url

    resp = await res.get_resource_spatial_facets(
        "r1", callback=None, debug=False, request=DummyRequest()
    )
    # Response should be a JSONResponse, check body content
    assert hasattr(resp, "body")
    import json

    data = json.loads(resp.body.decode())
    assert "id" in data
    assert "spatial_facets" in data


@pytest.mark.asyncio
async def test_get_resource_spatial_facets_missing(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(fetchone_row=None)

    class DummyRequest:
        def __init__(self):
            from starlette.datastructures import URL

            self._url = URL("http://test/resources/x/spatial_facets")

        @property
        def url(self):
            return self._url

    resp = await res.get_resource_spatial_facets(
        "x", callback=None, debug=False, request=DummyRequest()
    )
    # Response should be a JSONResponse, check body content
    assert hasattr(resp, "body")
    import json

    data = json.loads(resp.body.decode())
    assert "id" in data
    assert data["id"] == "x"
    assert "spatial_facets" in data
    assert data["spatial_facets"] == {}


@pytest.mark.asyncio
async def test_get_resource_spatial_facets_error(monkeypatch):
    from app.api.v1.endpoint_modules import resources as res

    res.async_session = lambda: DummySession(raise_on="execute")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await res.get_resource_spatial_facets("x", callback=None, debug=False, request=None)
    assert exc.value.status_code == 500
