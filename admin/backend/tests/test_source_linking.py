import asyncio
import importlib.util
import io
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError, URLError

import httpx2
import pytest
import test_resources
from test_api import make_settings
from test_managing_sets import create, headers
from test_resource_sources import setup
from test_resources import BASE, preview
from test_sources_api import UnavailableDatabase

from app.auth import Actor
from app.main import create_app

spec = importlib.util.spec_from_file_location(
    "local_admin_api", Path(__file__).parents[2] / "scripts/local_admin_api.py"
)
linker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linker)
api = test_resources.api
PERMISSIONS = {"resources:read", "resources:associate", "sets:read", "sources:read"}


def candidate(**changes):
    return {
        "id": "resource",
        "set_id": "set",
        "lock_version": 1,
        "source_id": "parent",
        "b1g_code_s": "01a-01",
        "code_origin": "import_evidence",
        "editable": True,
        **changes,
    }


@pytest.mark.parametrize(
    "url",
    ["https://example.org", "http://user@localhost", "http://localhost/path", "file:///tmp/x"],
)
def test_client_rejects_nonlocal_origins(url):
    with pytest.raises(ValueError):
        linker.Api(url)


def test_network_retry_preserves_payload_and_key_and_refuses_redirects(monkeypatch):
    api = linker.Api("http://127.0.0.1:8000", cookie="geomg_session=private")
    seen = []

    def open_request(request, timeout):
        seen.append((request.data, dict(request.headers)))
        if len(seen) == 1:
            raise URLError("offline")
        return io.BytesIO(b'{"items": []}')

    monkeypatch.setattr(api.opener, "open", open_request)
    monkeypatch.setattr(linker.time, "sleep", lambda _: None)
    assert api.request("/resources/csv/import", {"csv": "example"}, "same-key") == {"items": []}
    assert seen[0] == seen[1]
    assert seen[0][1]["X-geomg-request"] == "1"
    assert linker.NoRedirect().redirect_request(None, None, 302, None, None, None) is None

    def denied(*args, **kwargs):
        raise HTTPError("http://localhost", 403, "Denied", {}, None)

    monkeypatch.setattr(api.opener, "open", denied)
    with pytest.raises(linker.ApiError, match="HTTP 403") as caught:
        api.request("/sources")
    assert caught.value.status == 403


@pytest.mark.parametrize(
    "missing", sorted(PERMISSIONS) + ["anonymous", "service_account", "database"]
)
async def test_candidate_permission_and_dependency_failures(missing):
    actor = Actor("staff", "user", "Staff", None, frozenset(PERMISSIONS - {missing}))
    if missing == "service_account":
        actor = replace(actor, kind="service_account")

    async def authenticate(_):
        return None if missing == "anonymous" else actor

    app = create_app(authenticator=authenticate, settings=make_settings())
    app.state.database_engine = UnavailableDatabase()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(BASE + "/source-candidates")
    assert response.status_code == (
        503 if missing == "database" else 401 if missing == "anonymous" else 403
    )
    assert "private database" not in response.text


class LocalApi:
    """Exercise the actual script against the protected ASGI API and disposable PostgreSQL."""

    base = "http://127.0.0.1:8000"

    def __init__(self, client, loop):
        self.client, self.loop = client, loop
        self.writes = []

    def request(self, path, body=None, key=None, *, method=None):
        async def request():
            if key:
                self.writes.append((path, body, key))
            response = await self.client.request(
                method or ("POST" if body is not None else "GET"),
                linker.PREFIX + path,
                json=body,
                headers=headers(key),
            )
            if response.status_code >= 400:
                raise linker.ApiError(response.text, response.status_code)
            return response.json()

        return asyncio.run_coroutine_threadsafe(request(), self.loop).result(timeout=30)


@pytest.mark.integration
async def test_candidates_are_scoped_derived_and_bounded(api):
    client, actors, scope, _ = await setup(api)
    hidden = await create(client, code="hidden")
    for target, rid in [(scope, "visible"), (hidden, "hidden")]:
        body, _ = await preview(
            client, target, [{"id": rid, "dct_title_s": rid, "b1g_code_s": "01a-01"}]
        )
        assert (await client.post(BASE + "/imports", json=body, headers=headers())).json()[
            "created"
        ] == 1
    actors[0] = replace(actors[0], set_ids=frozenset({scope["set_id"]}))
    first = (await client.get(BASE + "/source-candidates", params={"limit": 1})).json()
    assert first["items"][0]["source_id"] == "parent"
    next_page = (
        await client.get(
            BASE + "/source-candidates", params={"limit": 1, "after": first["next_cursor"]}
        )
    ).json()
    assert next_page["items"][0]["id"] == "visible"
    assert next_page["items"][0]["b1g_code_s"] == "01a-01"
    assert next_page["items"][0]["code_origin"] == "import_evidence"
    assert next_page["next_cursor"] is None
