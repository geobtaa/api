"""
Tests for the MCP endpoint module.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.mcp import router
from app.main import app

client = TestClient(app)


class TestMCPEndpoints:
    """Test cases for MCP endpoints."""

    def test_mcp_endpoint_structure(self):
        """Test that the MCP endpoint is properly configured."""
        # Test that the app has the expected routes
        routes = [route.path for route in app.routes]

        # Check that MCP routes exist
        assert "/api/v1/mcp" in routes
        assert "/api/v1/mcp/ws" in routes

    def test_mcp_info_endpoint(self):
        """Test the MCP info endpoint returns correct information."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        # Check basic service information
        assert data["name"] == "geo-btaa-api"
        assert data["version"] == "0.1.0"
        assert data["description"] == "GeoBTAA API MCP Service"
        assert data["protocol"] == "mcp"
        assert "stdio" in data["transports"]
        assert "websocket" in data["transports"]

        # Check capabilities
        assert "tools" in data["capabilities"]
        expected_tools = [
            "search_resources",
            "get_resource",
            "get_resource_ogm",
            "list_resources",
            "get_suggestions",
            "get_resource_viewer",
            "validate_aardvark_record",
        ]
        for tool in expected_tools:
            assert tool in data["capabilities"]["tools"]

        # Check connections
        assert "stdio" in data["connections"]
        assert "websocket" in data["connections"]
        assert data["connections"]["stdio"]["type"] == "stdio"
        assert data["connections"]["websocket"]["type"] == "websocket"
        assert data["connections"]["websocket"]["url"] == "/api/v1/mcp/ws"

        # Check documentation
        assert "documentation" in data
        assert "tools" in data["documentation"]
        for tool in expected_tools:
            assert tool in data["documentation"]["tools"]
            assert isinstance(data["documentation"]["tools"][tool], str)
            assert len(data["documentation"]["tools"][tool]) > 0

    def test_mcp_info_endpoint_response_structure(self):
        """Test that the MCP endpoint response has the correct JSON structure."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        # Verify all required top-level keys exist
        required_keys = [
            "name",
            "version",
            "description",
            "protocol",
            "transports",
            "capabilities",
            "connections",
            "documentation",
        ]
        for key in required_keys:
            assert key in data

        # Verify capabilities structure
        assert isinstance(data["capabilities"], dict)
        assert "tools" in data["capabilities"]
        assert isinstance(data["capabilities"]["tools"], list)

        # Verify connections structure
        assert isinstance(data["connections"], dict)
        assert "stdio" in data["connections"]
        assert "websocket" in data["connections"]

        # Verify documentation structure
        assert isinstance(data["documentation"], dict)
        assert "tools" in data["documentation"]
        assert isinstance(data["documentation"]["tools"], dict)

    def test_mcp_websocket_endpoint_exists(self):
        """Test that the WebSocket endpoint is properly configured."""
        # Check that the WebSocket route exists
        routes = [route.path for route in app.routes]
        assert "/api/v1/mcp/ws" in routes

        # Note: WebSocket testing requires a different approach
        # This test just verifies the route is registered

    def test_mcp_endpoint_content_type(self):
        """Test that the MCP endpoint returns proper JSON content type."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_mcp_endpoint_tool_descriptions(self):
        """Test that all tools have meaningful descriptions."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        tool_descriptions = data["documentation"]["tools"]

        # Check that each tool has a description
        for _tool_name, description in tool_descriptions.items():
            assert isinstance(description, str)
            assert len(description) > 10  # Description should be meaningful
            # Check that description contains meaningful content about the tool
            # (Don't require exact tool name match since descriptions are human-readable)

    def test_mcp_endpoint_connection_details(self):
        """Test that connection details are properly formatted."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        # Check stdio connection
        stdio_conn = data["connections"]["stdio"]
        assert stdio_conn["type"] == "stdio"
        assert "command" in stdio_conn
        assert "args" in stdio_conn
        assert stdio_conn["command"] == "python"
        assert stdio_conn["args"] == ["-m", "app.services.mcp_service"]

        # Check websocket connection
        ws_conn = data["connections"]["websocket"]
        assert ws_conn["type"] == "websocket"
        assert "url" in ws_conn
        assert ws_conn["url"] == "/api/v1/mcp/ws"

    def test_mcp_endpoint_version_consistency(self):
        """Test that version information is consistent across the response."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        # Version should be a valid semantic version format
        version = data["version"]
        assert isinstance(version, str)
        assert "." in version
        version_parts = version.split(".")
        assert len(version_parts) >= 2
        assert all(part.isdigit() for part in version_parts[:2])

    def test_mcp_endpoint_transport_list(self):
        """Test that transport list is properly formatted."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        transports = data["transports"]
        assert isinstance(transports, list)
        assert len(transports) == 2
        assert "stdio" in transports
        assert "websocket" in transports

        # Transports should be unique
        assert len(set(transports)) == len(transports)

    def test_mcp_endpoint_tool_list_consistency(self):
        """Test that tool lists are consistent across different sections."""
        response = client.get("/api/v1/mcp")

        assert response.status_code == 200
        data = response.json()

        # Tools should be the same in capabilities and documentation
        capabilities_tools = set(data["capabilities"]["tools"])
        documentation_tools = set(data["documentation"]["tools"].keys())

        assert capabilities_tools == documentation_tools

        # All tools should have descriptions
        for tool in capabilities_tools:
            assert tool in data["documentation"]["tools"]
            assert data["documentation"]["tools"][tool] is not None
            assert data["documentation"]["tools"][tool] != ""


class TestMCPWebSocketEndpoint:
    """Test cases for MCP WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_mcp_websocket_endpoint_accepts_connection(self):
        """Test that WebSocket endpoint accepts connections."""
        from unittest.mock import Mock

        from fastapi import WebSocket

        # Create a mock WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()

        # Mock the MCP service
        with patch("app.services.mcp_service.run_mcp_websocket_server") as mock_run_server:
            mock_run_server.return_value = AsyncMock()

            # Import and call the endpoint function
            from app.api.v1.endpoint_modules.mcp import mcp_websocket_endpoint

            await mcp_websocket_endpoint(mock_websocket)

            # Verify WebSocket was accepted
            mock_websocket.accept.assert_called_once()
            # Verify MCP service was called
            mock_run_server.assert_called_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_mcp_websocket_endpoint_handles_disconnect(self):
        """Test that WebSocket endpoint handles client disconnection gracefully."""
        from unittest.mock import Mock

        from fastapi import WebSocket, WebSocketDisconnect

        # Create a mock WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()

        # Mock the MCP service to raise WebSocketDisconnect
        with patch("app.services.mcp_service.run_mcp_websocket_server") as mock_run_server:
            mock_run_server.side_effect = WebSocketDisconnect(1000, "Client disconnected")

            # Import and call the endpoint function
            from app.api.v1.endpoint_modules.mcp import mcp_websocket_endpoint

            # Should not raise an exception
            await mcp_websocket_endpoint(mock_websocket)

            # Verify WebSocket was accepted
            mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_websocket_endpoint_handles_general_exception(self):
        """Test that WebSocket endpoint handles general exceptions."""
        from unittest.mock import Mock

        from fastapi import WebSocket

        # Create a mock WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        # Mock the MCP service to raise a general exception
        with patch("app.services.mcp_service.run_mcp_websocket_server") as mock_run_server:
            mock_run_server.side_effect = Exception("Test error")

            # Import and call the endpoint function
            from app.api.v1.endpoint_modules.mcp import mcp_websocket_endpoint

            # Should not raise an exception
            await mcp_websocket_endpoint(mock_websocket)

            # Verify WebSocket was accepted
            mock_websocket.accept.assert_called_once()
            # Verify WebSocket was closed due to error
            mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_websocket_endpoint_handles_close_exception(self):
        """Test that WebSocket endpoint handles exceptions when closing connection."""
        from unittest.mock import Mock

        from fastapi import WebSocket

        # Create a mock WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock(side_effect=Exception("Close failed"))

        # Mock the MCP service to raise a general exception
        with patch("app.services.mcp_service.run_mcp_websocket_server") as mock_run_server:
            mock_run_server.side_effect = Exception("Test error")

            # Import and call the endpoint function
            from app.api.v1.endpoint_modules.mcp import mcp_websocket_endpoint

            # Should not raise an exception even if close fails
            await mcp_websocket_endpoint(mock_websocket)

            # Verify WebSocket was accepted
            mock_websocket.accept.assert_called_once()
            # Verify close was attempted
            mock_websocket.close.assert_called_once()

    def test_mcp_websocket_endpoint_function_signature(self):
        """Test that WebSocket endpoint has correct function signature."""
        import inspect

        from app.api.v1.endpoint_modules.mcp import mcp_websocket_endpoint

        # Check function signature
        sig = inspect.signature(mcp_websocket_endpoint)
        params = list(sig.parameters.keys())

        # Should have websocket parameter
        assert len(params) == 1
        assert params[0] == "websocket"

    def test_mcp_websocket_endpoint_is_async(self):
        """Test that WebSocket endpoint is async."""
        import inspect

        from app.api.v1.endpoint_modules.mcp import mcp_websocket_endpoint

        # Check that function is async
        assert inspect.iscoroutinefunction(mcp_websocket_endpoint)

    def test_mcp_websocket_route_configuration(self):
        """Test that WebSocket route is properly configured."""
        # Check that the WebSocket route exists in the router
        routes = [route for route in router.routes]
        websocket_routes = [
            route for route in routes if hasattr(route, "path") and route.path == "/mcp/ws"
        ]

        assert len(websocket_routes) == 1
        websocket_route = websocket_routes[0]

        # Check route methods
        assert hasattr(websocket_route, "methods") or hasattr(websocket_route, "endpoint")
        # WebSocket routes typically don't have methods, they have endpoint
        assert hasattr(websocket_route, "endpoint")
