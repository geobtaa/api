import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables with support for test environment
BASE_DIR = Path(__file__).resolve().parents[2]
APP_ENV = os.getenv("APP_ENV", "development")

if APP_ENV == "test":
    # In test mode, layer .env.test over .env
    load_dotenv(BASE_DIR / ".env", override=False)
    load_dotenv(BASE_DIR / ".env.test", override=True)
else:
    # Default: behave like original script, loading .env from project root
    load_dotenv(BASE_DIR / ".env", override=False)

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_api_tiers():
    """Initialize the six service tiers with their rate limits."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        
        # Convert asyncpg URL to sync URL
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Handle Docker hostnames for local development
        # If running locally and DATABASE_URL points to a Docker service, convert to localhost:2345
        parsed = urlparse(sync_database_url)
        if parsed.hostname and ("paradedb" in parsed.hostname or "btaa-geospatial-api" in parsed.hostname):
            # Replace Docker hostname with localhost and use port 2345 for local development
            # Use local database credentials from environment or defaults
            local_port = os.getenv("DB_PORT", "2345")
            local_user = os.getenv("DB_USER", "postgres")
            local_password = os.getenv("DB_PASSWORD", "postgres")
            local_db = os.getenv("DB_NAME", parsed.path.lstrip("/") if parsed.path else "btaa_geospatial_api")
            
            # Build new netloc with local credentials
            new_netloc = f"{local_user}:{local_password}@localhost:{local_port}"
            sync_database_url = urlunparse(parsed._replace(netloc=new_netloc, path=f"/{local_db}"))
            logger.info(f"Converted Docker hostname to localhost:{local_port} with local credentials")
        
        # Create engine
        engine = create_engine(sync_database_url)

        # Current timestamp
        now = datetime.utcnow()

        # Define tiers
        tiers = [
            {
                "tier_name": "btaa_primary",
                "display_name": "BTAA Primary",
                "requests_per_minute": None,  # Unlimited
                "description": "BTAA Geoportal Frontend - highest priority, unlimited access",
            },
            {
                "tier_name": "btaa_secondary",
                "display_name": "BTAA Secondary",
                "requests_per_minute": None,  # Unlimited
                "description": "BTAA Secondary Applications - high priority, unlimited access",
            },
            {
                "tier_name": "btaa_member_primary",
                "display_name": "BTAA Member Primary",
                "requests_per_minute": 1000,
                "description": "Big Ten Member University Primary Keys - high priority, 1000 requests/minute",
            },
            {
                "tier_name": "btaa_member_affiliated",
                "display_name": "BTAA Member Affiliated",
                "requests_per_minute": 500,
                "description": "BTAA Member Affiliated Applications - standard priority, 500 requests/minute",
            },
            {
                "tier_name": "general_registered",
                "display_name": "General Registered",
                "requests_per_minute": 100,
                "description": "General Registered Users - lower priority, 100 requests/minute",
            },
            {
                "tier_name": "anonymous",
                "display_name": "Anonymous",
                "requests_per_minute": 10,
                "description": "No API Key - lowest priority, 10 requests/minute, encourages registration",
            },
        ]

        with engine.connect() as conn:
            for tier in tiers:
                # Check if tier already exists
                check_stmt = text(
                    "SELECT id FROM api_service_tiers WHERE tier_name = :tier_name"
                )
                result = conn.execute(check_stmt, {"tier_name": tier["tier_name"]})
                existing = result.first()

                if existing:
                    logger.info(f"Tier '{tier['tier_name']}' already exists, skipping")
                    continue

                # Insert tier
                insert_stmt = text(
                    """
                    INSERT INTO api_service_tiers 
                    (tier_name, display_name, requests_per_minute, description, created_at, updated_at)
                    VALUES (:tier_name, :display_name, :requests_per_minute, :description, :created_at, :updated_at)
                    """
                )
                conn.execute(
                    insert_stmt,
                    {
                        "tier_name": tier["tier_name"],
                        "display_name": tier["display_name"],
                        "requests_per_minute": tier["requests_per_minute"],
                        "description": tier["description"],
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                logger.info(f"Created tier: {tier['tier_name']}")

            conn.commit()
            logger.info("Successfully initialized all API service tiers")

    except Exception as e:
        logger.error(f"Error initializing API tiers: {e}")
        raise


if __name__ == "__main__":
    initialize_api_tiers()


