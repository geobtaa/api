import os
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

_POOL_OPTION_KEYS = {
    "pool_pre_ping",
    "pool_recycle",
    "pool_size",
    "max_overflow",
    "pool_timeout",
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _running_under_pytest() -> bool:
    return "pytest" in sys.modules


def _null_pool_kwargs(overrides: dict[str, Any]) -> dict[str, Any]:
    kwargs = {key: value for key, value in overrides.items() if key not in _POOL_OPTION_KEYS}
    kwargs["poolclass"] = NullPool
    return kwargs


def create_app_async_engine(database_url: str, **overrides: Any) -> AsyncEngine:
    """Create an async SQLAlchemy engine with env-controlled pool bounds."""
    if os.getenv("APP_ENV") == "test" or _running_under_pytest():
        # asyncpg pooled connections are bound to the event loop that creates them.
        # pytest/TestClient creates multiple loops, so tests must never reuse a pool.
        return create_async_engine(database_url, **_null_pool_kwargs(overrides))

    use_null_pool = _env_bool("SQLALCHEMY_ASYNC_USE_NULLPOOL", False)

    kwargs: dict[str, Any] = {
        "pool_pre_ping": _env_bool("SQLALCHEMY_ASYNC_POOL_PRE_PING", True),
        "pool_recycle": _env_int("SQLALCHEMY_ASYNC_POOL_RECYCLE", 1800),
    }

    if use_null_pool:
        return create_async_engine(
            database_url,
            **_null_pool_kwargs({**kwargs, **overrides}),
        )
    else:
        kwargs.update(
            {
                "pool_size": _env_int("SQLALCHEMY_ASYNC_POOL_SIZE", 5),
                "max_overflow": _env_int("SQLALCHEMY_ASYNC_MAX_OVERFLOW", 10),
                "pool_timeout": _env_float("SQLALCHEMY_ASYNC_POOL_TIMEOUT", 10.0),
            }
        )

    kwargs.update(overrides)
    return create_async_engine(database_url, **kwargs)
