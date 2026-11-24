import pytest

from app.config import get_settings


def test_settings_are_loaded_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "Test Admin")
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    monkeypatch.setenv("CORS_ORIGINS", "https://one.example, https://two.example, ")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://example/test")
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("DEV_AUTH_ACTOR_ID", "local-actor")
    monkeypatch.setenv("DEV_AUTH_DISPLAY_NAME", "Local Actor")
    monkeypatch.setenv("DEV_AUTH_EMAIL", "local@example.org")
    monkeypatch.setenv(
        "DEV_AUTH_PERMISSIONS",
        "admin.session:read, resources:read, admin.session:read",
    )
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "test"
    assert settings.app_name == "Test Admin"
    assert settings.app_version == "9.9.9"
    assert settings.cors_origins == ("https://one.example", "https://two.example")
    assert settings.database_url == "postgresql+asyncpg://example/test"
    assert settings.auth_mode == "development"
    assert settings.dev_auth_actor_id == "local-actor"
    assert settings.dev_auth_display_name == "Local Actor"
    assert settings.dev_auth_email == "local@example.org"
    assert settings.dev_auth_permissions == ("admin.session:read", "resources:read")
    get_settings.cache_clear()


def test_development_authentication_requires_an_explicit_identity(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.delenv("DEV_AUTH_ACTOR_ID", raising=False)
    monkeypatch.delenv("DEV_AUTH_DISPLAY_NAME", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="requires DEV_AUTH_ACTOR_ID"):
        get_settings()

    get_settings.cache_clear()


def test_unsupported_authentication_mode_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "basic")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Unsupported AUTH_MODE: basic"):
        get_settings()

    get_settings.cache_clear()
