import os
import importlib
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

