import os
from urllib.parse import quote, urlparse, urlunparse

from dotenv import load_dotenv

# Load environment variables from .env file
try:
    load_dotenv()
except (OSError, PermissionError):
    # In sandboxed environments, .env may be unreadable. Continue with defaults/env.
    pass

def _repair_placeholder_database_password(database_url: str | None) -> str | None:
    """Replace placeholder `postgres` password with the configured env password."""
    if not database_url:
        return database_url

    parsed = urlparse(database_url)
    env_password = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD")

    # Only repair the common local-dev placeholder case so we do not unexpectedly
    # rewrite intentionally different DATABASE_URL values.
    if not env_password or parsed.password != "postgres" or env_password == "postgres":
        return database_url

    username = parsed.username or ""
    password = quote(env_password, safe="")
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:{password}@{hostname}{port}" if username else f"{hostname}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


# Get database configuration from environment variables
# Use DATABASE_URL if provided, otherwise construct from individual components
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD", "postgres")
    # Default to localhost when running outside Docker (e.g., tests)
    # Use paradedb (Docker service name) when running inside Docker
    is_docker = os.getenv("IS_DOCKER") == "true"
    DB_HOST = os.getenv("DB_HOST", "localhost" if not is_docker else "paradedb")
    DB_PORT = os.getenv("DB_PORT", "2345" if not is_docker else "5432")
    # Always default to the btaa_geospatial_api database for this application
    DB_NAME = os.getenv("DB_NAME", "btaa_geospatial_api")

    # Construct database URL with asyncpg driver, always targeting btaa_geospatial_api
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = _repair_placeholder_database_password(DATABASE_URL)

    # Convert Docker hostnames to localhost when running outside Docker
    # This handles cases where DATABASE_URL is set from .env with Docker service names
    is_docker = os.getenv("IS_DOCKER") == "true"
    if not is_docker and DATABASE_URL:
        parsed = urlparse(DATABASE_URL)
        docker_hostnames = [
            "paradedb",
            "btaa-geospatial-api-paradedb",
            "btaa-geospatial-api-paradedb-1",
        ]
        if parsed.hostname in docker_hostnames:
            # Replace Docker hostname with localhost and use port 2345 (Docker mapped port)
            new_netloc = f"{parsed.username}:{parsed.password}@localhost:2345"
            DATABASE_URL = urlunparse(parsed._replace(netloc=new_netloc))


def _mask_database_url(url: str | None) -> str:
    """Mask password in DB URL before logging."""
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.password is None:
        return url

    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{hostname}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


print("Using configured database connection")
