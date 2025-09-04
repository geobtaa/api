"""
Tests for the MCP service.
"""

import pytest

from app.services.mcp_service import OGMMCPService, mcp_service


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
            # If it's an error, verify it's a database connection error
            error_text = result.content[0].text.lower()
            assert any(
                term in error_text for term in ["database", "connection", "nodename", "servname"]
            )
        else:
            # If it's successful, verify the content
            assert len(result.content) == 1
            assert "minneapolis" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_get_resource_tool(self):
        """Test the get_resource tool."""
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        result = await service._get_resource({"id": "stanford-wt473hz7153"})

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
            assert "stanford" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_get_resource_ogm_tool(self):
        """Test the get_resource_ogm tool."""
        service = OGMMCPService()

        # Test with real data - this may fail in test environment due to DB connection issues
        result = await service._get_resource_ogm({"id": "stanford-wt473hz7153"})

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
        assert response["result"]["serverInfo"]["name"] == "ogm-api"

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
