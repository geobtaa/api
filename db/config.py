import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database configuration from environment variables
# Use DATABASE_URL if provided, otherwise construct from individual components
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "paradedb")
    DB_PORT = os.getenv("DB_PORT", "5432")
    # Always default to the btaa_geospatial_api database for this application
    DB_NAME = os.getenv("DB_NAME", "btaa_geospatial_api")

    # Construct database URL with asyncpg driver, always targeting btaa_geospatial_api
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"Using database URL: {DATABASE_URL}")
