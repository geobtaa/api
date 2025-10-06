import importlib
import os

import pytest


def _load_dotenv_if_available(path: str) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    if os.path.exists(path):
        try:
            load_dotenv(path, override=False)
        except Exception:
            pass


@pytest.fixture(autouse=True, scope="session")
def configure_admin_auth_env() -> None:
    # Load test env files if present
    _load_dotenv_if_available(".env.test.local")
    _load_dotenv_if_available(".env.test")

    # Ensure ADMIN creds exist (fallback to defaults used in tests)
    os.environ.setdefault("ADMIN_USERNAME", os.getenv("ADMIN_USERNAME", "admin"))
    os.environ.setdefault("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", "changeme"))

    # Reload auth module so constants pick up env during tests
    try:
        import app.api.v1.auth as auth

        importlib.reload(auth)
    except Exception:
        # If not importable yet, it's fine; later import will read env
        pass

    yield


@pytest.fixture(scope="session", autouse=True)
def flush_redis_between_sessions() -> None:
    """Flush Redis logical DB used for tests at session start/end."""
    try:
        import redis

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "1")),
        )
        try:
            client.flushdb()
        except Exception:
            pass
        yield
        try:
            client.flushdb()
        except Exception:
            pass
    except Exception:
        yield
