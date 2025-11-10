#!/usr/bin/env python3
"""
Diagnose why resources are missing from Elasticsearch index.
"""

import asyncio
import logging
import os
import sys
from urllib.parse import unquote

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from app.elasticsearch.client import es
from db.database import database
from db.models import resources

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "t", "yes", "y"}


async def main():
    """Check discrepancy between database and index."""
    try:
        await database.connect()

        # Flags
        published_only = _env_bool("PUBLISHED_ONLY", True)
        use_b1g_pub_state = _env_bool("USE_B1G_PUBLICATION_STATE", False)
        check_id = os.getenv("CHECK_ID")  # Optional: explicitly verify a single ID

        # Get count from database
        if published_only:
            if use_b1g_pub_state:
                db_count_query = (
                    "SELECT COUNT(*) FROM resources "
                    "WHERE coalesce(b1g_publication_state_s, '') = 'published'"
                )
            else:
                db_count_query = (
                    "SELECT COUNT(*) FROM resources WHERE publication_state = 'published'"
                )
        else:
            db_count_query = "SELECT COUNT(*) FROM resources"
        db_result = await database.fetch_one(db_count_query)
        db_count = db_result[0]

        # Get count from Elasticsearch
        index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_data_api")
        es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        es_count_result = await es.count(index=index_name)
        es_count = es_count_result.get("count", 0)

        logger.info("=" * 70)
        logger.info(f"Database resources: {db_count:,}")
        logger.info(f"Elasticsearch docs: {es_count:,}")
        logger.info(f"Missing from index: {db_count - es_count:,}")
        logger.info(f"ES URL: {es_url}")
        logger.info(f"ES index: {index_name}")
        logger.info("=" * 70)

        # If a specific ID was requested, verify it directly and exit early
        if check_id:
            from elasticsearch.exceptions import NotFoundError

            try:
                exists = await es.exists(index=index_name, id=check_id)
                logger.info(f"ES exists({check_id}) = {bool(exists)}")
                if not exists:
                    # Try with percent-encoded colon for sanity check
                    encoded = check_id.replace(":", "%3A")
                    exists_enc = await es.exists(index=index_name, id=encoded)
                    logger.info(f"ES exists({encoded}) = {bool(exists_enc)}")
            except NotFoundError:
                logger.info(f"ES reports {check_id} not found")
            return

        # Get all resource IDs from database (optionally only published)
        logger.info(
            f"Fetching resource IDs from database (published_only={published_only}, "
            f"use_b1g_pub_state={use_b1g_pub_state})..."
        )
        if published_only:
            if use_b1g_pub_state:
                db_ids_query = (
                    "SELECT id FROM resources "
                    "WHERE coalesce(b1g_publication_state_s, '') = 'published' "
                    "ORDER BY id"
                )
            else:
                db_ids_query = (
                    "SELECT id FROM resources "
                    "WHERE publication_state = 'published' "
                    "ORDER BY id"
                )
        else:
            db_ids_query = "SELECT id FROM resources ORDER BY id"
        db_rows = await database.fetch_all(db_ids_query)
        db_ids = {row["id"] for row in db_rows}
        logger.info(f"Found {len(db_ids):,} unique IDs in database")

        # Get all document IDs from Elasticsearch
        logger.info("Fetching all document IDs from Elasticsearch...")
        es_ids = set()

        # Use scroll API to get all IDs
        response = await es.search(
            index=index_name,
            query={"match_all": {}},
            _source=False,
            size=1000,
            scroll="2m",
            sort=["_doc"],
        )

        response_dict = response.body if hasattr(response, "body") else response
        scroll_id = response_dict.get("_scroll_id")
        hits = response_dict.get("hits", {}).get("hits", [])

        for hit in hits:
            # Normalize ES _id by URL-decoding (indexing may percent-encode colons)
            es_ids.add(unquote(hit["_id"]))

        while len(hits) > 0:
            response = await es.scroll(scroll_id=scroll_id, scroll="2m")
            response_dict = response.body if hasattr(response, "body") else response
            scroll_id = response_dict.get("_scroll_id")
            hits = response_dict.get("hits", {}).get("hits", [])

            for hit in hits:
                es_ids.add(unquote(hit["_id"]))

            if len(hits) > 0:
                logger.info(f"Fetched {len(es_ids):,} IDs so far...")

        # Clear scroll
        await es.clear_scroll(scroll_id=scroll_id)

        logger.info(f"Found {len(es_ids):,} unique IDs in Elasticsearch")

        # Find missing IDs (in DB but not in ES)
        missing_ids = db_ids - es_ids

        if missing_ids:
            logger.info("=" * 70)
            logger.info(f"Found {len(missing_ids):,} resources missing from index")
            logger.info("=" * 70)

            # Write missing IDs to a file for downstream triage
            out_path = os.getenv("MISSING_IDS_FILE", "logs/missing_resource_ids.txt")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as fh:
                for rid in sorted(missing_ids):
                    fh.write(f"{rid}\n")
            logger.info(f"Wrote missing IDs to {out_path}")

            # Sample some missing IDs to investigate
            sample_size = min(int(os.getenv("SAMPLE_SIZE", "15")), len(missing_ids))
            sample_ids = list(missing_ids)[:sample_size]

            logger.info(f"Sample of missing resource IDs: {sample_ids}")

            # Check if these have any special characteristics
            for missing_id in sample_ids:
                query = resources.select().where(resources.c.id == missing_id)
                resource = await database.fetch_one(query)
                if resource:
                    resource_dict = dict(resource)
                    logger.info(f"\nResource ID {missing_id}:")
                    logger.info(f"  Title: {resource_dict.get('dct_title_s', 'N/A')}")
                    logger.info(f"  Provider: {resource_dict.get('schema_provider_s', 'N/A')}")
                    logger.info(f"  Has geometry: {bool(resource_dict.get('locn_geometry'))}")
                    logger.info(
                        f"  publication_state: {resource_dict.get('publication_state')}, "
                        f"b1g_publication_state_s: {resource_dict.get('b1g_publication_state_s')}"
                    )
        else:
            logger.info("No missing resources found - all are indexed!")

    except Exception as e:
        logger.error(f"Diagnostic failed: {str(e)}", exc_info=True)
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
