import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Literal, cast

AuthMode = Literal["saml", "oidc", "development", "local-password"]


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_name: str
    app_version: str
    cors_origins: tuple[str, ...]
    database_url: str
    auth_mode: AuthMode = "saml"
    bridge_token_sha256: str | None = None
    bridge_token_expires_at: datetime | None = None
    dev_auth_actor_id: str | None = None
    dev_auth_display_name: str | None = None
    dev_auth_email: str | None = None
    dev_auth_permissions: tuple[str, ...] = ()
    auth_session_ttl_seconds: int | None = None
    auth_accepted_contexts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.bridge_token_expires_at and not self.bridge_token_expires_at.tzinfo:
            raise ValueError("Bridge credential expiry requires a timezone")
        if self.auth_session_ttl_seconds is not None and self.auth_session_ttl_seconds <= 0:
            raise ValueError("Session lifetime must be positive")
        if self.auth_mode not in {"saml", "oidc", "development", "local-password"}:
            raise ValueError(f"Unsupported AUTH_MODE: {self.auth_mode}")

        if self.auth_mode == "local-password" and self.app_env not in {
            "development",
            "test",
            "dev2",
        }:
            raise ValueError("Local passwords are restricted to development, test and dev2")

        if "local-password" in self.auth_accepted_contexts:
            raise ValueError("Local passwords cannot be an institutional authentication context")

        if self.auth_mode != "development":
            return

        if self.app_env not in {"development", "test"}:
            raise ValueError("Development authentication is forbidden outside development and test")

        if not self.dev_auth_actor_id or not self.dev_auth_display_name:
            raise ValueError(
                "Development authentication requires DEV_AUTH_ACTOR_ID and DEV_AUTH_DISPLAY_NAME"
            )


def _optional_environment_value(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _csv_environment_value(name: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(value.strip() for value in os.getenv(name, "").split(",") if value.strip())
    )


@lru_cache
def get_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    auth_mode = os.getenv("AUTH_MODE", "saml").strip().lower()
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_name=os.getenv("APP_NAME", "GEOMG Admin"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:2345/geomg",
        ),
        bridge_token_sha256=_optional_environment_value("ALPHA_BRIDGE_TOKEN_SHA256"),
        bridge_token_expires_at=datetime.fromisoformat(expiry)
        if (expiry := _optional_environment_value("ALPHA_BRIDGE_TOKEN_EXPIRES_AT"))
        else None,
        auth_mode=cast(AuthMode, auth_mode),
        dev_auth_actor_id=_optional_environment_value("DEV_AUTH_ACTOR_ID"),
        dev_auth_display_name=_optional_environment_value("DEV_AUTH_DISPLAY_NAME"),
        dev_auth_email=_optional_environment_value("DEV_AUTH_EMAIL"),
        dev_auth_permissions=_csv_environment_value("DEV_AUTH_PERMISSIONS"),
        auth_session_ttl_seconds=int(os.environ["AUTH_SESSION_TTL_SECONDS"])
        if _optional_environment_value("AUTH_SESSION_TTL_SECONDS")
        else None,
        auth_accepted_contexts=_csv_environment_value("AUTH_ACCEPTED_CONTEXTS"),
    )


def get_test_database_url() -> str | None:
    """Integration tests use an explicitly supplied, dedicated local database."""
    from sqlalchemy.engine import make_url

    value = _optional_environment_value("TEST_DATABASE_URL")
    if value:
        url = make_url(value)
        if url.database != "geomg_test" or url.host not in {"localhost", "127.0.0.1"}:
            raise ValueError("Tests require the local geomg_test database")
    return value
