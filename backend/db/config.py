import os
from dotenv import load_dotenv

# Load environment variables from .env file
try:
    load_dotenv()
except (OSError, PermissionError):
    # In sandboxed environments, .env may be unreadable. Continue with defaults/env.
    pass

# Get database configuration from environment variables
# Use DATABASE_URL if provided, otherwise construct from individual components
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
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
    # Convert Docker hostnames to localhost when running outside Docker
    # This handles cases where DATABASE_URL is set from .env with Docker service names
    is_docker = os.getenv("IS_DOCKER") == "true"
    if not is_docker and DATABASE_URL:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(DATABASE_URL)
        docker_hostnames = ["paradedb", "btaa-geospatial-api-paradedb", "btaa-geospatial-api-paradedb-1"]
        if parsed.hostname in docker_hostnames:
            # Replace Docker hostname with localhost and use port 2345 (Docker mapped port)
            new_netloc = f"{parsed.username}:{parsed.password}@localhost:2345"
            DATABASE_URL = urlunparse(parsed._replace(netloc=new_netloc))

print(f"Using database URL: {DATABASE_URL}")
