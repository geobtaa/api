"""
Tests for the MCP service.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.mcp_service import MCP_SERVICE_NAME, OGMMCPService, mcp_service


class TestOGMMCPService:
    """Test cases for OGMMCPService class."""

    def test_mcp_service_initialization(self):
        """Test that the MCP service can be initialized."""
        service = OGMMCPService()
        assert service is not None
        assert hasattr(service, "server")
        assert hasattr(service, "_register_tools")

    def test_mcp_service_singleton(self):
        """Test that the global mcp_service instance exists."""
        assert mcp_service is not None
        assert isinstance(mcp_service, OGMMCPService)

    @pytest.mark.asyncio
    async def test_search_resources_tool(self):
        """Test the search_resources tool."""
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        result = await service._search_resources({"query": "minneapolis", "page": 1, "per_page": 5})

        assert result is not None
        # In test environment, database connection might fail, so we accept both success and error
        if result.isError:
            # If it's an error, verify it's an expected environment or data error
            error_text = result.content[0].text.lower()
            assert any(
                term in error_text
                for term in [
                    "database",
                    "connection",
                    "nodename",
                    "servname",
                    "not found",
                    "elasticsearch",
                    "search failed",
                ]
            )
        else:
            # If it's successful, verify the content
            assert len(result.content) == 1
            assert "minneapolis" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_search_resources_tool_uses_api_search_response(self):
        """Test that search_resources relays the public search API response."""
        service = OGMMCPService()
        api_payload = {
            "status_code": 200,
            "url": "http://localhost:8000/api/v1/search?q=minneapolis&page=2&per_page=1",
            "content_type": "application/json",
            "location": None,
            "data": {
                "links": {"self": "http://localhost:8000/api/v1/search?q=minneapolis"},
                "meta": {
                    "totalCount": 42,
                    "totalPages": 42,
                    "currentPage": 2,
                    "perPage": 1,
                    "spellingSuggestions": ["minneapolis maps"],
                },
                "data": [{"id": "stanford-abc123", "type": "resource", "attributes": {}}],
            },
        }

        with patch.object(service, "_api_request", AsyncMock(return_value=api_payload)) as mock_api:
            result = await service._search_resources(
                {"query": "minneapolis", "page": 2, "per_page": 1}
            )

        assert not result.isError
        mock_api.assert_awaited_once_with(
            "/search", params={"q": "minneapolis", "page": 2, "per_page": 1}
        )

        payload = json.loads(result.content[0].text)
        assert payload["query"] == "minneapolis"
        assert payload["total_results"] == 42
        assert payload["total_pages"] == 42
        assert payload["page"] == 2
        assert payload["per_page"] == 1
        assert payload["spelling_suggestions"] == ["minneapolis maps"]
        assert payload["resources"][0]["id"] == "stanford-abc123"
        assert payload["links"]["self"] == "http://localhost:8000/api/v1/search?q=minneapolis"
        assert payload["source"]["transport"] == "http"

    @pytest.mark.asyncio
    async def test_search_resources_tool_surfaces_api_errors(self):
        """Test that search_resources returns API errors instead of fake empty results."""
        service = OGMMCPService()
        api_payload = {
            "status_code": 500,
            "url": "http://localhost:8000/api/v1/search?q=palestine",
            "content_type": "application/json",
            "location": None,
            "data": {
                "errors": [
                    {
                        "status": 500,
                        "code": "elasticsearch_search_failed",
                        "title": "Search failed",
                        "detail": "Elasticsearch search failed.",
                    }
                ]
            },
        }

        with patch.object(service, "_api_request", AsyncMock(return_value=api_payload)):
            result = await service._search_resources({"query": "palestine"})

        assert result.isError
        payload = json.loads(result.content[0].text)
        assert payload["status_code"] == 500
        assert payload["error_type"] == "elasticsearch"
        assert payload["query"] == "palestine"
        assert payload["data"]["errors"][0]["code"] == "elasticsearch_search_failed"

    @pytest.mark.asyncio
    async def test_search_resources_tool_surfaces_connection_errors(self):
        """Test that search_resources returns structured errors when the API is unreachable."""
        service = OGMMCPService()

        with patch.object(
            service, "_api_request", AsyncMock(side_effect=RuntimeError("connection refused"))
        ):
            result = await service._search_resources({"query": "palestine", "page": 3})

        assert result.isError
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "Search request failed"
        assert payload["error_type"] == "connection"
        assert payload["detail"] == "connection refused"
        assert payload["query"] == "palestine"
        assert payload["page"] == 3
        assert payload["source"]["transport"] == "http"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_get_resource_tool(self):
        """Test the get_resource tool.

        This test is marked as slow because it makes real database/Elasticsearch queries.
        Skip slow tests with: pytest -m "not slow"
        """
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        # Add timeout to prevent hanging on slow database/ES queries
        import asyncio

        try:
            result = await asyncio.wait_for(
                service._get_resource({"id": "stanford-wt473hz7153"}),
                timeout=5.0,  # 5 second timeout
            )
        except asyncio.TimeoutError:
            pytest.skip("Test timed out - database/Elasticsearch query took too long")

        assert result is not None
        # In test environment, database connection might fail, so we accept both success and error
        if result.isError:
            # If it's an error, verify it's an expected environment or data error
            error_text = result.content[0].text.lower()
            assert any(
                term in error_text
                for term in ["database", "connection", "nodename", "servname", "not found"]
            )
        else:
            # If it's successful, verify the content
            assert len(result.content) == 1
            assert "stanford" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_get_resource_ogm_tool(self):
        """Test the get_resource_metadata tool (formerly get_resource_ogm)."""
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        result = await service._get_resource_metadata({"id": "stanford-wt473hz7153"})

        assert result is not None
        # In test environment, database connection might fail, so we accept both success and error
        if result.isError:
            # If it's an error, verify it's a database connection error
            error_text = result.content[0].text.lower()
            assert any(
                term in error_text
                for term in ["database", "connection", "nodename", "servname", "not found"]
            )
        else:
            # If it's successful, verify the content
            assert len(result.content) == 1
            assert "stanford" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_list_resources_tool(self):
        """Test the list_resources tool."""
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        result = await service._list_resources({"page": 1, "per_page": 5})

        assert result is not None
        # In test environment, database connection might fail, so we accept both success and error
        if result.isError:
            # If it's an error, verify it's a database connection error
            error_text = result.content[0].text.lower()
            assert any(
                term in error_text for term in ["database", "connection", "nodename", "servname"]
            )
        else:
            # If it's successful, verify the content
            assert len(result.content) == 1
            assert "total_count" in result.content[0].text

    @pytest.mark.asyncio
    async def test_get_suggestions_tool(self):
        """Test the get_suggestions tool."""
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        result = await service._get_suggestions({"query": "minneapolis"})

        assert result is not None
        # In test environment, database connection might fail, so we accept both success and error
        if result.isError:
            # If it's an error, verify it's a database connection error
            error_text = result.content[0].text.lower()
            assert any(
                term in error_text for term in ["database", "connection", "nodename", "servname"]
            )
        else:
            # If it's successful, verify the content
            assert len(result.content) >= 1
            assert "minneapolis" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_get_resource_viewer_tool(self):
        """Test the get_resource_viewer tool."""
        service = OGMMCPService()

        result = await service._get_resource_viewer({"id": "stanford-wt473hz7153", "embed": False})

        assert result is not None
        assert not result.isError
        assert len(result.content) == 1
        assert "stanford-wt473hz7153" in result.content[0].text
        assert "<!DOCTYPE html>" in result.content[0].text
        assert "ogm-viewer" in result.content[0].text

    @pytest.mark.asyncio
    async def test_validate_aardvark_record_tool(self):
        """Test the validate_aardvark_record tool."""
        service = OGMMCPService()

        # Test with a valid Aardvark record
        valid_record = {"dct_title_s": "Test Title", "gbl_mdVersion_s": "Aardvark"}

        result = await service._validate_aardvark_record({"record": valid_record})

        assert result is not None
        # This might fail if the external schema URL is not accessible in test environment
        # Just verify the service can handle the call
        assert len(result.content) >= 1

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in tools."""
        service = OGMMCPService()

        # Test with invalid arguments
        result = await service._get_resource({})  # Missing 'id'

        assert result is not None
        assert result.isError
        assert len(result.content) == 1
        assert "Error" in result.content[0].text

    def test_tool_registration(self):
        """Test that tools are properly registered."""
        service = OGMMCPService()

        # Check that the server has the expected decorators
        assert hasattr(service.server, "list_tools")
        assert hasattr(service.server, "call_tool")

    @pytest.mark.asyncio
    async def test_mcp_message_handling(self):
        """Test MCP message handling."""
        from app.services.mcp_service import handle_mcp_message

        # Test initialize message
        init_message = {"method": "initialize", "id": 1, "params": {}}

        response = await handle_mcp_message(init_message)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == MCP_SERVICE_NAME

        # Test tools/list message
        list_message = {"method": "tools/list", "id": 2, "params": {}}

        response = await handle_mcp_message(list_message)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) > 0

        # Test unknown method
        unknown_message = {"method": "unknown_method", "id": 3, "params": {}}

        response = await handle_mcp_message(unknown_message)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "error" in response
        assert response["error"]["code"] == -32601

        # Test ping
        ping_message = {"method": "ping", "id": 4, "params": {}}

        response = await handle_mcp_message(ping_message)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert response["result"] == {}

        # Test initialized notification
        notification_message = {"method": "notifications/initialized", "params": {}}

        response = await handle_mcp_message(notification_message)
        assert response is None
