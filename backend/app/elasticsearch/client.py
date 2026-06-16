import logging
import os

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch, BadRequestError

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


def _mapping_entries(mapping_response: dict, requested_index: str) -> list[dict]:
    """Return mapping entries for an index or alias response."""
    direct_entry = mapping_response.get(requested_index)
    if direct_entry is not None:
        return [direct_entry]
    return [entry for entry in mapping_response.values() if isinstance(entry, dict)]


def _mapping_has_field(mapping_response: dict, requested_index: str, field_name: str) -> bool:
    for entry in _mapping_entries(mapping_response, requested_index):
        properties = (entry.get("mappings", {}) or {}).get("properties", {}) or {}
        if field_name in properties:
            return True
    return False


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
            try:
                await es.indices.create(
                    index=index_name,
                    mappings=INDEX_MAPPING["mappings"],
                    settings=INDEX_MAPPING["settings"],
                )
            except BadRequestError as e:
                # Race-safe: another process may create the index between exists() and create().
                error_type = ""
                try:
                    error_type = (e.body or {}).get("error", {}).get("type", "")
                except Exception:
                    error_type = ""
                if error_type == "resource_already_exists_exception":
                    logger.info(
                        "Index %s was created by another process; continuing initialization",
                        index_name,
                    )
                else:
                    raise
        else:
            logger.info(f"Index {index_name} already exists")
            # Ensure newly-added fields exist in mappings (non-destructive).
            try:
                current = await es.indices.get_mapping(index=index_name)
                if not _mapping_has_field(current, index_name, "ogm_repo"):
                    logger.info("Adding missing mapping field: ogm_repo")
                    await es.indices.put_mapping(
                        index=index_name,
                        properties={
                            "ogm_repo": INDEX_MAPPING["mappings"]["properties"]["ogm_repo"]
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not ensure mappings for {index_name}: {e}")

    except Exception as e:
        logger.error(f"Elasticsearch initialization error: {str(e)}", exc_info=True)
        raise


async def close_elasticsearch():
    """Close the Elasticsearch connection."""
    try:
        await es.close()
    except RuntimeError as e:
        # Handle event loop issues that can occur in test environments
        # when using pytest-asyncio with session-scoped fixtures
        if "attached to a different loop" in str(e):
            logger.warning(
                "Could not close Elasticsearch client due to event loop conflict. "
                "This can occur in test environments and is usually safe to ignore."
            )
            # In test environments, the fixture will handle cleanup
            return
        raise
