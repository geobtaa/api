"""Provision the first local administrator. Run interactively in the GEOMG environment."""

import argparse
import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.identity.local_schemas import LocalAccount
from app.identity.passwords import provision


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--permission", action="append", default=[])
    args = parser.parse_args()
    settings = get_settings()
    if settings.auth_mode != "local-password":
        parser.error("Bootstrap requires AUTH_MODE=local-password")
    engine = create_async_engine(settings.database_url)
    try:
        account = LocalAccount(
            email=args.email, permissions=["identity:manage", *args.permission], set_ids=None
        )
        result = await provision(engine, None, account, uuid4(), bootstrap=True)
        print(f"Setup code (expires {result['expires_at']}): {result['setup_code']}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
