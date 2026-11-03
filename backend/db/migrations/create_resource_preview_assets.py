"""Add shared preview manifests. Safe to repeat in local development."""

from db.config import DATABASE_URL
from db.models import resource_preview_assets
from db.sync_engine import create_app_sync_engine


def main():
    engine = create_app_sync_engine(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    resource_preview_assets.create(engine, checkfirst=True)
    engine.dispose()


if __name__ == "__main__":
    main()
