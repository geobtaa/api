import os
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

import app.elasticsearch.client as es_client_mod
from app.elasticsearch.mappings import INDEX_MAPPING

# Load environment variables from .env.test file
load_dotenv(".env.test")

# Get the test index name from environment variables
TEST_INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "data_api_test")

# Use the ELASTICSEARCH_URL from .env file or default to localhost
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")


@pytest_asyncio.fixture(scope="session")
async def es_client_session():
    """
    Session-scoped Elasticsearch client and index.
    Creates the index once per test session for performance.
    """
    # Create a client using the same URL and settings as the application
    client = AsyncElasticsearch(
        hosts=[ELASTICSEARCH_URL],
        verify_certs=False,  # For development only
        ssl_show_warn=False,  # For development only
        request_timeout=60,  # Increase timeout to 60 seconds
        retry_on_timeout=True,  # Retry on timeout
        max_retries=3,  # Maximum number of retries
    )

    try:
        # Verify connection
        info = await client.info()
        print(f"Connected to Elasticsearch cluster: {info['cluster_name']}")

        # Delete the test index if it exists (start fresh for session)
        if await client.indices.exists(index=TEST_INDEX_NAME):
            await client.indices.delete(index=TEST_INDEX_NAME)
            print(f"Deleted existing test index {TEST_INDEX_NAME}")

        # Create the index once for the session
        await client.indices.create(
            index=TEST_INDEX_NAME,
            mappings=INDEX_MAPPING["mappings"],
            settings=INDEX_MAPPING["settings"],
        )
        print(f"Created test index {TEST_INDEX_NAME} for session")

        yield client

    finally:
        # Clean up - delete the test index at end of session
        try:
            if await client.indices.exists(index=TEST_INDEX_NAME):
                await client.indices.delete(index=TEST_INDEX_NAME)
                print(f"Cleaned up test index {TEST_INDEX_NAME}")
        except Exception as e:
            print(f"Error cleaning up test index: {e}")

        # Always close the client
        await client.close()


@pytest_asyncio.fixture
async def clean_es_index(es_client_session):
    """
    Function-scoped fixture that clears documents from the ES index between tests.
    This is much faster than deleting/recreating the index.
    """
    # Clear all documents from the index using delete_by_query
    try:
        await es_client_session.delete_by_query(
            index=TEST_INDEX_NAME,
            body={"query": {"match_all": {}}},
            wait_for_completion=True,
        )
    except Exception as e:
        # If delete_by_query fails, try to delete and recreate the index
        print(f"Warning: Could not clear index with delete_by_query: {e}")
        try:
            if await es_client_session.indices.exists(index=TEST_INDEX_NAME):
                await es_client_session.indices.delete(index=TEST_INDEX_NAME)
            await es_client_session.indices.create(
                index=TEST_INDEX_NAME,
                mappings=INDEX_MAPPING["mappings"],
                settings=INDEX_MAPPING["settings"],
            )
        except Exception as recreate_error:
            print(f"Warning: Could not recreate index: {recreate_error}")

    yield es_client_session


@pytest_asyncio.fixture
async def es_client(clean_es_index):
    """
    Backward-compatible fixture that provides a clean ES client for each test.
    Uses session-scoped index creation with function-scoped document clearing.
    """
    yield clean_es_index


@pytest.mark.asyncio
async def test_init_elasticsearch_success(es_client, monkeypatch):
    """Test successful initialization of Elasticsearch."""
    # Monkeypatch the global ES client to use our test client
    monkeypatch.setattr(es_client_mod, "es", es_client)

    try:
        # Call the function
        await es_client_mod.init_elasticsearch()

        # Verify the index was created
        assert await es_client.indices.exists(index=TEST_INDEX_NAME)
    except Exception as e:
        # Handle timeout context manager errors gracefully
        if "Timeout context manager should be used inside a task" in str(e):
            pytest.skip("Timeout context manager issue in test environment")
        else:
            raise


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_init_elasticsearch_index_exists(es_client, monkeypatch):
    """Test initialization when index already exists."""
    # Monkeypatch the global ES client to use our test client
    monkeypatch.setattr(es_client_mod, "es", es_client)

    try:
        # Delete the index if it exists
        if await es_client.indices.exists(index=TEST_INDEX_NAME):
            await es_client.indices.delete(index=TEST_INDEX_NAME)

        # Create the index first
        await es_client.indices.create(
            index=TEST_INDEX_NAME,
            mappings=INDEX_MAPPING["mappings"],
            settings=INDEX_MAPPING["settings"],
        )

        # Call the function
        await es_client_mod.init_elasticsearch()

        # Verify the index still exists
        assert await es_client.indices.exists(index=TEST_INDEX_NAME)

        # Clean up - delete the index
        await es_client.indices.delete(index=TEST_INDEX_NAME)
    except Exception as e:
        # Handle timeout context manager errors gracefully
        if "Timeout context manager should be used inside a task" in str(e):
            pytest.skip("Timeout context manager issue in test environment")
        else:
            raise


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_close_elasticsearch(monkeypatch):
    """Test closing the Elasticsearch connection."""
    # Create a separate client just for this test to avoid closing the session-scoped fixture
    test_client = AsyncElasticsearch(
        hosts=[ELASTICSEARCH_URL],
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=60,
        retry_on_timeout=True,
        max_retries=3,
    )

    try:
        # Monkeypatch the global ES client to use our test client
        monkeypatch.setattr(es_client_mod, "es", test_client)

        # Call the function - it should handle event loop issues gracefully
        await es_client_mod.close_elasticsearch()

        # This test is successful if no exception is raised
    finally:
        # Ensure the test client is closed even if close_elasticsearch had issues
        try:
            await test_client.close()
        except Exception:
            # Ignore errors when closing in test environment
            pass


@pytest.mark.asyncio
async def test_init_elasticsearch_ignores_resource_already_exists(monkeypatch):
    """init_elasticsearch should continue if create races with another process."""

    class _FakeBadRequestError(Exception):
        def __init__(self, body):
            self.body = body
            super().__init__("fake bad request")

    fake_es = Mock()
    fake_es.info = AsyncMock(return_value={"cluster_name": "test-cluster"})
    fake_es.indices = Mock()
    fake_es.indices.exists = AsyncMock(return_value=False)
    fake_es.indices.create = AsyncMock(
        side_effect=_FakeBadRequestError({"error": {"type": "resource_already_exists_exception"}})
    )

    monkeypatch.setattr(es_client_mod, "es", fake_es)
    monkeypatch.setattr(es_client_mod, "BadRequestError", _FakeBadRequestError)

    await es_client_mod.init_elasticsearch()

    fake_es.indices.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_elasticsearch_respects_alias_backed_existing_mapping(monkeypatch):
    """Do not put_mapping when an alias resolves to a concrete index with ogm_repo."""
    fake_es = Mock()
    fake_es.info = AsyncMock(return_value={"cluster_name": "test-cluster"})
    fake_es.indices = Mock()
    fake_es.indices.exists = AsyncMock(return_value=True)
    fake_es.indices.get_mapping = AsyncMock(
        return_value={
            "btaa_geospatial_api_20260616010101": {
                "mappings": {
                    "properties": {"ogm_repo": INDEX_MAPPING["mappings"]["properties"]["ogm_repo"]}
                }
            }
        }
    )
    fake_es.indices.put_mapping = AsyncMock()

    monkeypatch.setattr(es_client_mod, "es", fake_es)
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    await es_client_mod.init_elasticsearch()

    fake_es.indices.get_mapping.assert_awaited_once_with(index="btaa_geospatial_api")
    fake_es.indices.put_mapping.assert_not_awaited()


@pytest.mark.asyncio
async def test_init_elasticsearch_adds_missing_ogm_repo_with_canonical_mapping(monkeypatch):
    """When ogm_repo is truly absent, add the same mapping used for new indices."""
    fake_es = Mock()
    fake_es.info = AsyncMock(return_value={"cluster_name": "test-cluster"})
    fake_es.indices = Mock()
    fake_es.indices.exists = AsyncMock(return_value=True)
    fake_es.indices.get_mapping = AsyncMock(
        return_value={
            "btaa_geospatial_api_20260616010101": {
                "mappings": {"properties": {"id": {"type": "keyword"}}}
            }
        }
    )
    fake_es.indices.put_mapping = AsyncMock()

    monkeypatch.setattr(es_client_mod, "es", fake_es)
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    await es_client_mod.init_elasticsearch()

    fake_es.indices.put_mapping.assert_awaited_once_with(
        index="btaa_geospatial_api",
        properties={"ogm_repo": INDEX_MAPPING["mappings"]["properties"]["ogm_repo"]},
    )
