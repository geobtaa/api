from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        app_name="GEOMG Admin",
        app_version="0.1.0-test",
        cors_origins=("http://localhost:3000",),
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
    )


async def database_available() -> None:
    return None


def test_liveness_and_readiness(tmp_path: Path) -> None:
    application = create_app(
        readiness_check=database_available,
        frontend_dist=tmp_path,
        settings=make_settings(),
    )

    with TestClient(application) as client:
        health = client.get("/api/v1/health")
        ready = client.get("/api/v1/ready")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "GEOMG Admin",
        "version": "0.1.0-test",
    }
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "database": "available"}


def test_readiness_failure_returns_503(tmp_path: Path) -> None:
    async def database_unavailable() -> None:
        raise OSError("database offline")

    application = create_app(
        readiness_check=database_unavailable,
        frontend_dist=tmp_path,
        settings=make_settings(),
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"code": "database_unavailable", "message": "Database unavailable", "errors": []}
    }


def test_api_metadata_is_returned_without_a_frontend_build(tmp_path: Path) -> None:
    application = create_app(frontend_dist=tmp_path, settings=make_settings())

    with TestClient(application) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "GEOMG Admin",
        "version": "0.1.0-test",
        "docs": "/api/docs",
    }


def test_built_frontend_files_and_client_routes_are_served(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>GEOMG Admin</h1>", encoding="utf-8")
    (tmp_path / "asset.txt").write_text("asset", encoding="utf-8")
    application = create_app(frontend_dist=tmp_path, settings=make_settings())

    with TestClient(application) as client:
        asset = client.get("/asset.txt")
        client_route = client.get("/resources/example")

    assert asset.text == "asset"
    assert client_route.text == "<h1>GEOMG Admin</h1>"


def test_frontend_only_serves_files_in_the_build(tmp_path: Path) -> None:
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("frontend")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (build / "external-link.txt").symlink_to(outside)
    with TestClient(create_app(frontend_dist=build, settings=make_settings())) as client:
        assert client.get("/external-link.txt").text == "frontend"
        assert client.get("/api/unknown").status_code == 404
