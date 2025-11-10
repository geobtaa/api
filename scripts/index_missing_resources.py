#!/usr/bin/env python3
"""
Index only the resources listed in logs/missing_resource_ids.txt.
Intended to be run after scripts/diagnose_missing_resources.py generates the list.
"""

import asyncio
import logging
import os
import sys
from typing import List

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from app.elasticsearch.client import es
from app.elasticsearch.index import process_resource
from db.database import database

# Load environment
load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _read_missing_ids(path: str) -> List[str]:
    try:
        with open(path, "r") as fh:
            return [line.strip() for line in fh if line.strip()]
    except FileNotFoundError:
        return []


async def main():
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_data_api")
    ids_file = os.getenv("MISSING_IDS_FILE", "logs/missing_resource_ids.txt")

    missing_ids = _read_missing_ids(ids_file)
    if not missing_ids:
        logger.info(f"No missing IDs found at {ids_file}. Nothing to index.")
        return

    logger.info(f"Indexing {len(missing_ids):,} missing resources into index '{index_name}'")

    ok = 0
    err = 0

    try:
        await database.connect()
        for rid in missing_ids:
            row = await database.fetch_one("SELECT * FROM resources WHERE id = :id", {"id": rid})
            if not row:
                logger.warning(f"DB row not found for ID: {rid}")
                continue
            try:
                document = await process_resource(dict(row))
                await es.index(index=index_name, id=rid, document=document, refresh=False)
                ok += 1
            except Exception as e:
                logger.error(f"INDEX ERROR {rid}: {e}")
                err += 1

        # Final refresh so documents are immediately searchable
        try:
            await es.indices.refresh(index=index_name)
        except Exception as e:
            logger.warning(f"Index refresh failed: {e}")

        logger.info(f"Indexed {ok:,}, errors {err:,}, total attempted {len(missing_ids):,}")

    except Exception as e:
        logger.error(f"Indexing missing resources failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            await database.disconnect()
        except Exception:
            pass
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())


