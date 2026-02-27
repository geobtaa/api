import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_gin_blog_posts_table() -> None:
    """Create gin_blog_posts table (idempotent)."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
    )
    sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_database_url)
    inspector = inspect(engine)

    if inspector.has_table("gin_blog_posts"):
        logger.info("gin_blog_posts already exists; skipping table creation")
        return

    create_sql = """
    CREATE TABLE IF NOT EXISTS gin_blog_posts (
      id SERIAL PRIMARY KEY,
      slug VARCHAR(255) NOT NULL,
      source_path VARCHAR(500) NOT NULL UNIQUE,
      url VARCHAR(500) NOT NULL,
      title VARCHAR(500) NOT NULL,
      excerpt TEXT NOT NULL,
      published_at TIMESTAMP NOT NULL,
      category VARCHAR(20) NOT NULL,
      authors_json JSONB NOT NULL,
      tags_json JSONB NOT NULL,
      image_url VARCHAR(1000),
      image_alt TEXT,
      source_sha VARCHAR(64),
      synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
      is_active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMP NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
      CONSTRAINT uq_gin_blog_posts_slug UNIQUE (slug)
    );
    CREATE INDEX IF NOT EXISTS idx_gin_blog_posts_source_path ON gin_blog_posts(source_path);
    CREATE INDEX IF NOT EXISTS idx_gin_blog_posts_published_at ON gin_blog_posts(published_at);
    CREATE INDEX IF NOT EXISTS idx_gin_blog_posts_category ON gin_blog_posts(category);
    CREATE INDEX IF NOT EXISTS idx_gin_blog_posts_is_active ON gin_blog_posts(is_active);
    CREATE INDEX IF NOT EXISTS idx_gin_blog_posts_slug ON gin_blog_posts(slug);
    """

    with engine.begin() as conn:
        conn.execute(text(create_sql))
    logger.info("Created gin_blog_posts table and indexes")


if __name__ == "__main__":
    create_gin_blog_posts_table()
