import hashlib
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_api import make_settings

from app import fixtures
from app.auth import Actor
from app.main import create_app


def test_snapshot_and_starter_collection():
    catalog = fixtures.load_catalog()
    assert len(catalog.items) == 14
    assert len({item.metadata["id"] for item in catalog.items}) == 14
    manifest = json.loads((fixtures.ROOT / "manifest.json").read_text())
    assert len(manifest["entries"]) == 111
    assert {p.relative_to(fixtures.ROOT).as_posix() for p in fixtures.ROOT.glob("*/*.json")} == {
        entry["path"] for entry in manifest["entries"]
    }
    for item in catalog.items:
        if references := item.metadata.get("dct_references_s"):
            assert isinstance(json.loads(references), dict)
    assert any(item.metadata.get("gbl_suppressed_b") for item in catalog.items)
    assert any(
        item.metadata.get("b1g_publication_state_s") == "unpublished" for item in catalog.items
    )


@pytest.mark.parametrize("problem", ["checksum", "identity", "duplicate", "title", "path"])
def test_invalid_snapshot_fails_closed(tmp_path, problem):
    record = {"id": "example", "dct_title_s": "Example"}
    if problem == "title":
        record["dct_title_s"] = None
    raw = json.dumps(record).encode()
    (tmp_path / "example.json").write_bytes(raw)
    entry = {
        "path": "example.json",
        "resource_id": "example",
        "starter": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "purpose": "test",
    }
    if problem == "checksum":
        entry["sha256"] = "bad"
    if problem == "identity":
        entry["resource_id"] = "different"
    if problem == "path":
        entry["path"] = "../outside.json"
    entries = [entry, entry] if problem == "duplicate" else [entry]
    (tmp_path / "manifest.json").write_text(
        json.dumps({"source_commit": "test", "entries": entries})
    )
    with pytest.raises(ValueError):
        fixtures.load_catalog(tmp_path)


@pytest.mark.parametrize(
    "environment,permissions,authenticated,status",
    [
        ("development", {"admin.session:read"}, True, 200),
        ("test", {"admin.session:read"}, True, 200),
        ("production", {"admin.session:read"}, True, 404),
        ("test", set(), True, 403),
        ("test", set(), False, 401),
    ],
)
def test_catalog_access(tmp_path, environment, permissions, authenticated, status):
    async def authenticate(_):
        return (
            Actor("tester", "user", "Tester", None, frozenset(permissions))
            if authenticated
            else None
        )

    app = create_app(
        settings=replace(make_settings(), app_env=environment),
        authenticator=authenticate,
        frontend_dist=tmp_path,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/resource-fixtures")
        assert response.status_code == status
        if status == 200:
            assert len(response.json()["items"]) == 14


def test_catalog_dependency_failure(tmp_path, monkeypatch):
    def unavailable():
        raise OSError("missing")

    monkeypatch.setattr(fixtures, "load_catalog", unavailable)

    async def authenticate(_):
        return Actor("tester", "user", "Tester", None, frozenset({"admin.session:read"}))

    with TestClient(
        create_app(settings=make_settings(), authenticator=authenticate, frontend_dist=tmp_path)
    ) as client:
        assert client.get("/api/v1/admin/resource-fixtures").status_code == 503


def test_fixtures_do_not_embed_url_authentication_material():
    import re

    from app.fixtures import ROOT

    sensitive = re.compile(
        r"(?:[;?&]|&amp;)(?:jsessionid|phpsessid|access_token|api_key|apikey|signature)="
        r"[^&\s\"\\]+",
        re.IGNORECASE,
    )
    for path in ROOT.rglob("*.json"):
        assert not sensitive.search(path.read_text()), f"Credential-bearing fixture: {path.name}"
