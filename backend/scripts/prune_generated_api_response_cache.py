#!/usr/bin/env python3
"""Prune expired durable API response cache rows."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from app.services.durable_response_cache import (  # noqa: E402
    delete_expired_durable_api_responses,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> int:
    deleted = await delete_expired_durable_api_responses()
    logger.info("Pruned %s expired durable API response cache rows", deleted)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
