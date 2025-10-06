"""
Tests for the jsonp module.
"""

import json
from datetime import datetime

import pytest

from app.api.v1.jsonp import BaseJSONResponse, JSONPResponse, datetime_handler


class TestDatetimeHandler:
    """Test cases for datetime_handler function."""

    def test_datetime_handler_with_datetime(self):
        """Test datetime_handler with datetime object."""
        dt = datetime(2023, 12, 25, 14, 30, 45, 123456)
        result = datetime_handler(dt)
        assert result == "2023-12-25T14:30:45.123456"

    def test_datetime_handler_with_datetime_no_microseconds(self):
        """Test datetime_handler with datetime object without microseconds."""
        dt = datetime(2023, 12, 25, 14, 30, 45)
        result = datetime_handler(dt)
        assert result == "2023-12-25T14:30:45"

    def test_datetime_handler_with_datetime_utc(self):
        """Test datetime_handler with UTC datetime."""
        dt = datetime(2023, 1, 1, 0, 0, 0)
        result = datetime_handler(dt)
        assert result == "2023-01-01T00:00:00"

    def test_datetime_handler_with_non_datetime(self):
        """Test datetime_handler with non-datetime object."""
        with pytest.raises(TypeError, match="Object of type <class 'int'> is not JSON serializable"):
            datetime_handler(123)

    def test_datetime_handler_with_string(self):
        """Test datetime_handler with string object."""
        with pytest.raises(TypeError, match="Object of type <class 'str'> is not JSON serializable"):
            datetime_handler("test")

    def test_datetime_handler_with_list(self):
        """Test datetime_handler with list object."""
        with pytest.raises(TypeError, match="Object of type <class 'list'> is not JSON serializable"):
            datetime_handler([1, 2, 3])

    def test_datetime_handler_with_dict(self):
        """Test datetime_handler with dict object."""
        with pytest.raises(TypeError, match="Object of type <class 'dict'> is not JSON serializable"):
            datetime_handler({"key": "value"})


class TestBaseJSONResponse:
    """Test cases for BaseJSONResponse class."""

    def test_base_json_response_render_simple_content(self):
        """Test BaseJSONResponse render with simple content."""
        response = BaseJSONResponse({"message": "test"})
        result = response.render({"message": "test"})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == '{"message":"test"}'

    def test_base_json_response_render_with_datetime(self):
        """Test BaseJSONResponse render with datetime content."""
        dt = datetime(2023, 12, 25, 14, 30, 45)
        response = BaseJSONResponse({"date": dt})
        result = response.render({"date": dt})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert '"date":"2023-12-25T14:30:45"' in decoded

    def test_base_json_response_render_complex_content(self):
        """Test BaseJSONResponse render with complex content."""
        content = {
            "id": "test-123",
            "title": "Test Document",
            "created_at": datetime(2023, 12, 25, 14, 30, 45),
            "tags": ["tag1", "tag2"],
            "metadata": {
                "author": "John Doe",
                "version": 1.0
            }
        }
        
        response = BaseJSONResponse(content)
        result = response.render(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert '"id":"test-123"' in decoded
        assert '"title":"Test Document"' in decoded
        assert '"created_at":"2023-12-25T14:30:45"' in decoded
        assert '"tags":["tag1","tag2"]' in decoded
        assert '"author":"John Doe"' in decoded

    def test_base_json_response_render_unicode_content(self):
        """Test BaseJSONResponse render with unicode content."""
        content = {
            "title": "Título con acentos: ñáéíóú",
            "description": "Descripción con emojis: 🗺️ 📍"
        }
        
        response = BaseJSONResponse(content)
        result = response.render(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert "Título con acentos" in decoded
        assert "ñáéíóú" in decoded
        assert "🗺️" in decoded

    def test_base_json_response_render_empty_content(self):
        """Test BaseJSONResponse render with empty content."""
        response = BaseJSONResponse({})
        result = response.render({})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == "{}"

    def test_base_json_response_render_none_content(self):
        """Test BaseJSONResponse render with None content."""
        response = BaseJSONResponse(None)
        result = response.render(None)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == "null"

    def test_base_json_response_render_list_content(self):
        """Test BaseJSONResponse render with list content."""
        content = [1, 2, 3, "test", {"nested": "value"}]
        response = BaseJSONResponse(content)
        result = response.render(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert '[1,2,3,"test",{"nested":"value"}]' == decoded


class TestJSONPResponse:
    """Test cases for JSONPResponse class."""

    def test_jsonp_response_initialization_default_callback(self):
        """Test JSONPResponse initialization with default callback."""
        response = JSONPResponse({"message": "test"})
        assert response.callback == "callback"
        assert response.media_type == "application/javascript"

    def test_jsonp_response_initialization_custom_callback(self):
        """Test JSONPResponse initialization with custom callback."""
        response = JSONPResponse({"message": "test"}, callback="myCallback")
        assert response.callback == "myCallback"
        assert response.media_type == "application/javascript"

    def test_jsonp_response_render_simple_content(self):
        """Test JSONPResponse render with simple content."""
        response = JSONPResponse({"message": "test"})
        result = response.render({"message": "test"})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == 'callback({"message":"test"})'

    def test_jsonp_response_render_custom_callback(self):
        """Test JSONPResponse render with custom callback."""
        response = JSONPResponse({"message": "test"}, callback="myCallback")
        result = response.render({"message": "test"})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == 'myCallback({"message":"test"})'

    def test_jsonp_response_render_with_datetime(self):
        """Test JSONPResponse render with datetime content."""
        dt = datetime(2023, 12, 25, 14, 30, 45)
        response = JSONPResponse({"date": dt})
        result = response.render({"date": dt})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == 'callback({"date":"2023-12-25T14:30:45"})'

    def test_jsonp_response_render_complex_content(self):
        """Test JSONPResponse render with complex content."""
        content = {
            "id": "test-123",
            "title": "Test Document",
            "created_at": datetime(2023, 12, 25, 14, 30, 45),
            "tags": ["tag1", "tag2"],
            "metadata": {
                "author": "John Doe",
                "version": 1.0
            }
        }
        
        response = JSONPResponse(content, callback="handleData")
        result = response.render(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded.startswith("handleData({")
        assert decoded.endswith("})")
        assert '"id":"test-123"' in decoded
        assert '"title":"Test Document"' in decoded
        assert '"created_at":"2023-12-25T14:30:45"' in decoded

    def test_jsonp_response_render_empty_content(self):
        """Test JSONPResponse render with empty content."""
        response = JSONPResponse({})
        result = response.render({})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == "callback({})"

    def test_jsonp_response_render_none_content(self):
        """Test JSONPResponse render with None content."""
        response = JSONPResponse(None)
        result = response.render(None)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == "callback(null)"

    def test_jsonp_response_render_list_content(self):
        """Test JSONPResponse render with list content."""
        content = [1, 2, 3, "test"]
        response = JSONPResponse(content, callback="processArray")
        result = response.render(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == 'processArray([1,2,3,"test"])'

    def test_jsonp_response_render_unicode_content(self):
        """Test JSONPResponse render with unicode content."""
        content = {
            "title": "Título con acentos: ñáéíóú",
            "description": "Descripción con emojis: 🗺️ 📍"
        }
        
        response = JSONPResponse(content, callback="unicodeCallback")
        result = response.render(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded.startswith("unicodeCallback({")
        assert decoded.endswith("})")
        assert "Título con acentos" in decoded
        assert "ñáéíóú" in decoded

    def test_jsonp_response_callback_with_special_characters(self):
        """Test JSONPResponse with callback containing special characters."""
        response = JSONPResponse({"message": "test"}, callback="my_callback_123")
        result = response.render({"message": "test"})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == 'my_callback_123({"message":"test"})'

    def test_jsonp_response_callback_with_dots(self):
        """Test JSONPResponse with callback containing dots."""
        response = JSONPResponse({"message": "test"}, callback="namespace.callback")
        result = response.render({"message": "test"})
        
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        assert decoded == 'namespace.callback({"message":"test"})'

    def test_jsonp_response_inheritance(self):
        """Test that JSONPResponse properly inherits from BaseJSONResponse."""
        response = JSONPResponse({"message": "test"})
        
        # Should have media_type from JSONPResponse
        assert response.media_type == "application/javascript"
        
        # Should have callback attribute
        assert hasattr(response, 'callback')
        assert response.callback == "callback"
        
        # Should be able to render
        result = response.render({"message": "test"})
        assert isinstance(result, bytes)

    def test_jsonp_response_with_kwargs(self):
        """Test JSONPResponse initialization with additional kwargs."""
        response = JSONPResponse(
            {"message": "test"}, 
            callback="myCallback",
            status_code=200,
            headers={"Custom-Header": "value"}
        )
        
        assert response.callback == "myCallback"
        # Should pass kwargs to parent class
        assert response.status_code == 200

    def test_jsonp_response_render_consistency(self):
        """Test that JSONPResponse render produces consistent output."""
        content = {"message": "test", "number": 42}
        response = JSONPResponse(content, callback="testCallback")
        
        result1 = response.render(content)
        result2 = response.render(content)
        
        assert result1 == result2
        decoded = result1.decode("utf-8")
        assert decoded == 'testCallback({"message":"test","number":42})'
