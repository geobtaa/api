import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.v1.endpoint_modules.sources import router, source_adapter
from app.services import source_projection as service

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures/source-projection-v1.example.json").read_text()
)
SETTINGS = service.ProjectionSettings(
    origin="https://geomg.example.test", session_token="synthetic-session"
)


def application(handler):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[source_adapter] = lambda: service.SourceAdapter(
        SETTINGS, httpx.MockTransport(handler)
    )
    return app


async def get(app, path="/api/v1/sources", **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        return await client.get(path, **kwargs)


@pytest.mark.parametrize(
    "path,key",
    [
        ("/sources", "list"),
        ("/sources/Source_A", "detail"),
        ("/sources/Source_A/resources", "resources"),
    ],
)
async def test_consumer_fixture_and_server_owned_credentials(path, key):
    calls = []

    def upstream(request):
        calls.append(request)
        return httpx.Response(
            200,
            json=FIXTURE[key],
            headers={"Set-Cookie": "upstream=PRIVATE", "X-Private": "PRIVATE"},
        )

    response = await get(
        application(upstream),
        "/api/v1" + path,
        headers={"Cookie": "attacker=PRIVATE", "Authorization": "Bearer PRIVATE"},
        params={"include_non_public": "true", "url": "https://attacker.example"},
    )
    assert response.status_code == 200 and response.json() == FIXTURE[key]
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers and "x-private" not in response.headers
    assert "PRIVATE" not in response.text
    request = calls[0]
    assert request.url.host == "geomg.example.test"
    assert request.url.path == "/api/v1/admin/projections" + path
    assert request.headers["cookie"] == "__Host-geomg-session=synthetic-session"
    assert "authorization" not in request.headers
    assert "include_non_public" not in request.url.params and "url" not in request.url.params


async def test_search_and_paging_forward_only_bounded_contract_parameters():
    calls = []
    payload = copy.deepcopy(FIXTURE["list"])
    payload.update(items=[payload["items"][1]], offset=1, limit=1)

    def upstream(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    response = await get(application(upstream), params={"q": " Source_A ", "offset": 1, "limit": 1})
    assert response.status_code == 200 and response.json() == payload
    assert dict(calls[0].url.params) == {"q": "Source_A", "offset": "1", "limit": "1"}
    payload.update(items=[], offset=2)
    assert (await get(application(upstream), params={"offset": 2, "limit": 1})).json()[
        "items"
    ] == []


async def test_changed_data_reassociation_and_visibility_have_no_stale_cache():
    payload = copy.deepcopy(FIXTURE["resources"])
    calls = []

    def upstream(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    app = application(upstream)
    first = await get(app, "/api/v1/sources/Source_A/resources")
    assert first.json()["total"] == 2
    # GEOMG applies visibility and membership; adapter never hydrates via local Resource detail.
    payload["items"].pop()
    payload["total"] = 1
    current = await get(app, "/api/v1/sources/Source_A/resources")
    assert current.json()["items"] == payload["items"] and current.json()["total"] == 1
    payload.update(items=[], total=0)
    assert (await get(app, "/api/v1/sources/Source_A/resources")).json()["total"] == 0
    payload = copy.deepcopy(FIXTURE["detail"])
    payload["source"].update(
        title="Updated", description="Changed description", landing_page="https://example.org"
    )
    assert (await get(app, "/api/v1/sources/Source_A")).json()["source"]["title"] == "Updated"
    assert len(calls) == 4


@pytest.mark.parametrize("status", [301, 302, 401, 403, 429, 500, 503])
async def test_upstream_errors_and_redirects_never_leak_or_become_empty(status):
    calls = []

    def upstream(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="PRIVATE credential and host",
            headers={"Location": "https://attacker.example"},
        )

    response = await get(application(upstream))
    assert response.status_code == 502
    assert response.json() == {"detail": "Source service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "path,expected",
    [("/sources", 502), ("/sources/missing", 404), ("/sources/missing/resources", 404)],
)
async def test_not_found_is_distinct_from_empty_source(path, expected):
    response = await get(
        application(lambda _: httpx.Response(404, text="PRIVATE")), "/api/v1" + path
    )
    assert response.status_code == expected
    assert "PRIVATE" not in response.text


@pytest.mark.parametrize(
    "failure,status",
    [
        (httpx.ReadTimeout("PRIVATE"), 504),
        (TimeoutError("PRIVATE"), 504),
        (httpx.ConnectError("PRIVATE"), 502),
    ],
)
async def test_failure_then_retry_fetches_current_data(failure, status):
    calls = []

    def upstream(request):
        calls.append(request)
        if len(calls) == 1:
            raise failure
        return httpx.Response(200, json=FIXTURE["list"])

    app = application(upstream)
    failed = await get(app)
    assert failed.status_code == status and failed.json() == {
        "detail": "Source service unavailable"
    }
    assert (await get(app)).json() == FIXTURE["list"]


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(schema_version="2"),
        lambda p: p.update(total="2"),
        lambda p: p.update(total=True),
        lambda p: p.update(total=99),
        lambda p: p.update(offset=1),
        lambda p: p.update(limit=1),
        lambda p: p["items"][0].update(admin_notes="PRIVATE"),
        lambda p: p["items"][0].update(landing_page="javascript:alert(1)"),
        lambda p: p["items"][0].update(landing_page="https://user:secret@example.org"),
        lambda p: p["items"][0].update(resource_count=-1),
        lambda p: p["items"][0].update(source_id="../private"),
        lambda p: p["items"].reverse(),
        lambda p: p["items"].__setitem__(1, p["items"][0]),
    ],
)
async def test_rejects_malformed_or_private_upstream_payload(change):
    payload = copy.deepcopy(FIXTURE["list"])
    change(payload)
    response = await get(application(lambda _: httpx.Response(200, json=payload)))
    assert response.status_code == 502 and response.json() == {
        "detail": "Source service unavailable"
    }


@pytest.mark.parametrize(
    "key,path", [("detail", "/sources/wrong"), ("resources", "/sources/wrong/resources")]
)
async def test_rejects_wrong_source_response(key, path):
    response = await get(
        application(lambda _: httpx.Response(200, json=FIXTURE[key])), "/api/v1" + path
    )
    assert response.status_code == 502


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b"not json", "application/json"),
        (b'{"schema_version":"1","schema_version":"2"}', "application/json"),
        (b"<html>PRIVATE</html>", "text/html"),
    ],
)
async def test_invalid_json_and_html_are_not_forwarded(body, content_type):
    response = await get(
        application(
            lambda _: httpx.Response(200, content=body, headers={"Content-Type": content_type})
        )
    )
    assert response.status_code == 502 and "PRIVATE" not in response.text


async def test_response_bytes_are_bounded(monkeypatch):
    monkeypatch.setattr(service, "MAX_RESPONSE_BYTES", 10)
    response = await get(application(lambda _: httpx.Response(200, json=FIXTURE["list"])))
    assert response.status_code == 502


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"offset": 1000001}, {"q": "x" * 201}]
)
async def test_bad_public_query_does_not_contact_upstream(params):
    def upstream(_):
        pytest.fail("Invalid request reached upstream")

    assert (await get(application(upstream), params=params)).status_code == 422


async def test_bad_source_id_is_rejected_before_upstream():
    def upstream(_):
        pytest.fail("Invalid Source ID reached upstream")

    assert (await get(application(upstream), "/api/v1/sources/bad%20id")).status_code == 422


async def test_unconfigured_adapter_fails_closed_and_uses_current_server_configuration(monkeypatch):
    monkeypatch.delenv("GEOMG_SOURCE_ORIGIN", raising=False)
    monkeypatch.delenv("GEOMG_SOURCE_SESSION_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    response = await get(app)
    assert response.status_code == 503 and response.json() == {
        "detail": "Source service unavailable"
    }
    monkeypatch.setenv("GEOMG_SOURCE_ORIGIN", "https://geomg.example.test")
    monkeypatch.setenv("GEOMG_SOURCE_SESSION_TOKEN", "synthetic-session")
    loaded = service.ProjectionSettings.from_environment()
    assert loaded.origin == SETTINGS.origin
    assert "synthetic-session" not in repr(loaded)
    app.dependency_overrides[source_adapter] = lambda: service.SourceAdapter(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=FIXTURE["list"]))
    )
    assert (await get(app)).status_code == 200
    monkeypatch.setenv("GEOMG_SOURCE_SESSION_TOKEN", "")
    assert (await get(app)).status_code == 503


@pytest.mark.parametrize(
    "origin",
    [
        "http://remote.example",
        "https://user:secret@example.org",
        "https://example.org/path",
        "https://example.org?query=x",
        "https://example.org#fragment",
        "https://example.org\\bad",
        "https://example.org:bad",
        "https://example.org\n",
    ],
)
def test_configuration_rejects_unsafe_destinations(origin):
    with pytest.raises(ValidationError):
        service.ProjectionSettings(origin=origin, session_token="synthetic-session")


@pytest.mark.parametrize("token", ["", "x; another=bad", "x\r\nX-Header: bad"])
def test_configuration_rejects_invalid_cookie_values(token):
    with pytest.raises(ValidationError):
        service.ProjectionSettings(origin="https://example.org", session_token=token)


def test_local_origin_and_contract():
    assert (
        service.ProjectionSettings(
            origin="http://127.0.0.1:8000/", session_token="local-test"
        ).origin
        == "http://127.0.0.1:8000"
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    schema = app.openapi()
    assert set(schema["components"]["schemas"]["Source"]["properties"]) == {
        "source_id",
        "title",
        "description",
        "landing_page",
        "resource_count",
    }
    assert set(schema["components"]["schemas"]["ResourceReference"]["properties"]) == {
        "id",
        "title",
    }
    assert set(schema["paths"]) == {
        "/api/v1/sources",
        "/api/v1/sources/{source_id}",
        "/api/v1/sources/{source_id}/resources",
    }


async def test_empty_source_detail_and_resource_page():
    source = copy.deepcopy(FIXTURE["list"]["items"][0])
    payloads = [
        {"schema_version": "1", "source": source},
        {**FIXTURE["resources"], "source_id": "Source-B", "items": [], "total": 0},
    ]
    app = application(lambda _: httpx.Response(200, json=payloads.pop(0)))
    detail = await get(app, "/api/v1/sources/Source-B")
    resources = await get(app, "/api/v1/sources/Source-B/resources")
    assert detail.status_code == resources.status_code == 200
    assert detail.json()["source"]["resource_count"] == resources.json()["total"] == 0
    assert resources.json()["items"] == []


async def test_resource_reference_rejects_private_fields():
    payload = copy.deepcopy(FIXTURE["resources"])
    payload["items"][0]["staff_notes"] = "PRIVATE"
    response = await get(
        application(lambda _: httpx.Response(200, json=payload)),
        "/api/v1/sources/Source_A/resources",
    )
    assert response.status_code == 502 and "PRIVATE" not in response.text


async def test_overall_deadline_closes_stalled_response(monkeypatch):
    import asyncio

    closed = []

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(10)
            yield b"{}"

        async def aclose(self):
            closed.append(True)

    monkeypatch.setattr(service, "READ_TIMEOUT_SECONDS", 0.01)
    response = await get(
        application(
            lambda _: httpx.Response(
                200, headers={"content-type": "application/json"}, stream=SlowStream()
            )
        )
    )
    assert response.status_code == 504
    assert closed == [True]
