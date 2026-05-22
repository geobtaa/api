from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from db.async_engine import get_app_async_engine
from db.config import DATABASE_URL
from db.sync_engine import get_app_sync_engine


def sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async_engine = get_app_async_engine(DATABASE_URL)
async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
sync_engine = get_app_sync_engine(sync_database_url())


def get_async_session():
    return async_session()
