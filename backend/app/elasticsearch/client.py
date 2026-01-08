import logging
import os

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

try:
    load_dotenv()
except (OSError, PermissionError):
    # In sandboxed environments, .env may be unreadable. Continue with defaults/env.
    pass

# Create the AsyncElasticsearch client with proper timeout and retry settings
# Note: Connection pooling is handled automatically by the elasticsearch library
# The "too many open files" issue is addressed by configuring ulimits on the host system
# See scripts/setup_elasticsearch_ulimits.sh for host-level configuration
es = AsyncElasticsearch(
    os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"),
    verify_certs=False,  # For development only
    ssl_show_warn=False,  # For development only
    request_timeout=60,  # Increase timeout to 60 seconds
    retry_on_timeout=True,  # Retry on timeout
    max_retries=3,  # Maximum number of retries
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def init_elasticsearch():
    """Initialize Elasticsearch index and mappings."""
    from .mappings import INDEX_MAPPING

    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    try:
        # Test the connection
        info = await es.info()
        logger.info(f"Connected to Elasticsearch cluster: {info['cluster_name']}")

        # Check if index exists
        exists = await es.indices.exists(index=index_name)
        if not exists:
            logger.info(f"Creating index {index_name}")
            await es.indices.create(
                index=index_name,
                mappings=INDEX_MAPPING["mappings"],
                settings=INDEX_MAPPING["settings"],
            )
        else:
            logger.info(f"Index {index_name} already exists")
            # Ensure newly-added fields exist in mappings (non-destructive).
            try:
                current = await es.indices.get_mapping(index=index_name)
                props = (
                    (current.get(index_name, {}) or {}).get("mappings", {}) or {}
                ).get("properties", {}) or {}
                if "ogm_repo" not in props:
                    logger.info("Adding missing mapping field: ogm_repo")
                    await es.indices.put_mapping(
                        index=index_name, properties={"ogm_repo": {"type": "keyword"}}
                    )
            except Exception as e:
                logger.warning(f"Could not ensure mappings for {index_name}: {e}")

    except Exception as e:
        logger.error(f"Elasticsearch initialization error: {str(e)}", exc_info=True)
        raise


async def close_elasticsearch():
    """Close the Elasticsearch connection."""
    await es.close()
