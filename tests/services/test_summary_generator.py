"""
Tests for the SummaryGenerator.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm.summary_generator import SummaryGenerator


class TestSummaryGenerator:
    """Test cases for SummaryGenerator class."""

    def test_summary_generator_initialization(self):
        """Test SummaryGenerator initialization."""
        generator = SummaryGenerator(
            api_key="test-key",
            model="gpt-3.5-turbo",
            api_url="https://api.openai.com/v1/chat/completions"
        )
        
        assert generator.api_key == "test-key"
        assert generator.model == "gpt-3.5-turbo"
        assert generator.api_url == "https://api.openai.com/v1/chat/completions"

    def test_construct_summary_prompt_basic(self):
        """Test constructing summary prompt without asset content."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {
            "title": "Historical Map of Minnesota",
            "creator": "John Smith",
            "date": "1880",
            "description": "A detailed map of Minnesota counties"
        }
        
        prompt, output_parser = generator._construct_summary_prompt(metadata)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Generate a concise summary" in prompt
        assert "Historical Map of Minnesota" in prompt
        assert "John Smith" in prompt
        assert "1880" in prompt
        assert "A detailed map of Minnesota counties" in prompt
        assert "Main features and content" in prompt
        assert "Historical context" in prompt
        assert "Geographic coverage" in prompt
        assert "Notable characteristics" in prompt
        assert output_parser["type"] == "text"
        assert "concise summary" in output_parser["description"]

    def test_construct_summary_prompt_with_asset_content(self):
        """Test constructing summary prompt with asset content."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {
            "title": "Minnesota Counties Map",
            "creator": "Jane Doe",
            "date": "1890"
        }
        
        asset_content = "This map shows all 87 counties in Minnesota with their boundaries and county seats."
        
        prompt, output_parser = generator._construct_summary_prompt(metadata, asset_content)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Minnesota Counties Map" in prompt
        assert "Jane Doe" in prompt
        assert "1890" in prompt
        assert "Content:" in prompt
        assert "This map shows all 87 counties" in prompt
        assert "counties in Minnesota" in prompt
        assert "county seats" in prompt
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_empty_metadata(self):
        """Test constructing summary prompt with empty metadata."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {}
        
        prompt, output_parser = generator._construct_summary_prompt(metadata)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Generate a concise summary" in prompt
        assert "{}" in prompt  # Empty metadata JSON
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_complex_metadata(self):
        """Test constructing summary prompt with complex metadata."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {
            "title": "Complex Map",
            "creator": ["Author 1", "Author 2"],
            "date": "1900-1910",
            "description": "Multi-layered map with detailed annotations",
            "spatial": {
                "bbox": [-97.5, 43.0, -89.0, 49.5],
                "center": [-93.25, 46.25]
            },
            "subjects": ["Geography", "History", "Transportation"],
            "rights": "Public Domain"
        }
        
        prompt, output_parser = generator._construct_summary_prompt(metadata)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Complex Map" in prompt
        assert "Author 1" in prompt
        assert "Author 2" in prompt
        assert "1900-1910" in prompt
        assert "Multi-layered map" in prompt
        assert "bbox" in prompt
        assert "Geography" in prompt
        assert "Public Domain" in prompt
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_long_asset_content(self):
        """Test constructing summary prompt with long asset content."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        asset_content = "This is a very long description of a historical map that contains detailed information about various geographic features, historical events, and contextual information that would be relevant for understanding the map's significance and content."
        
        prompt, output_parser = generator._construct_summary_prompt(metadata, asset_content)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Test Map" in prompt
        assert "Content:" in prompt
        assert "very long description" in prompt
        assert "geographic features" in prompt
        assert "historical events" in prompt
        assert "contextual information" in prompt
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_special_characters(self):
        """Test constructing summary prompt with special characters."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {
            "title": "Map with Special Characters: éñü",
            "description": "Contains unicode: αβγδε and symbols: @#$%"
        }
        
        asset_content = "Special content: ñáéíóú and symbols: !@#$%^&*()"
        
        prompt, output_parser = generator._construct_summary_prompt(metadata, asset_content)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        # Special characters are JSON encoded, so check for the encoded versions
        assert "\\u00e9\\u00f1\\u00fc" in prompt or "éñü" in prompt
        assert "\\u03b1\\u03b2\\u03b3\\u03b4\\u03b5" in prompt or "αβγδε" in prompt
        assert "@#$%" in prompt
        assert "ñáéíóú" in prompt
        assert "!@#$%^&*()" in prompt
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_none_asset_content(self):
        """Test constructing summary prompt with None asset content."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        prompt, output_parser = generator._construct_summary_prompt(metadata, None)
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Test Map" in prompt
        assert "Content:" not in prompt  # Should not include Content section
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_empty_asset_content(self):
        """Test constructing summary prompt with empty asset content."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        prompt, output_parser = generator._construct_summary_prompt(metadata, "")
        
        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Test Map" in prompt
        assert "Content:" not in prompt  # Should not include Content section for empty string
        assert output_parser["type"] == "text"

    def test_construct_summary_prompt_prompt_structure(self):
        """Test that the constructed prompt has the correct structure."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Structure Test"}
        
        prompt, output_parser = generator._construct_summary_prompt(metadata)
        
        # Check that prompt contains all required sections
        assert "Generate a concise summary" in prompt
        assert "Metadata:" in prompt
        assert "Main features and content" in prompt
        assert "Historical context" in prompt
        assert "Geographic coverage" in prompt
        assert "Notable characteristics" in prompt
        assert "Keep the summary focused and brief" in prompt
        
        # Check that it doesn't contain numbered list instruction
        assert "do not make a numbered list" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_success(self):
        """Test successful summary generation."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {
            "title": "Minnesota Historical Map",
            "creator": "John Doe",
            "date": "1880"
        }
        
        # Mock the API response
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "This historical map of Minnesota from 1880 by John Doe shows the state's counties and major geographic features. The map provides valuable insight into the state's development during the late 19th century."
                    }
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await generator.generate_summary(metadata)
            
            summary, prompt, output_parser = result
            
            assert isinstance(summary, str)
            assert "Minnesota" in summary
            assert "1880" in summary
            assert "John Doe" in summary
            assert isinstance(prompt, str)
            assert isinstance(output_parser, dict)
            assert output_parser["type"] == "text"

    @pytest.mark.asyncio
    async def test_generate_summary_with_asset_content(self):
        """Test summary generation with asset content."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        asset_content = "This map shows detailed county boundaries and transportation routes."
        
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "A detailed map showing county boundaries and transportation routes, providing comprehensive geographic information."
                    }
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await generator.generate_summary(metadata, asset_content)
            
            summary, prompt, output_parser = result
            
            assert isinstance(summary, str)
            assert "county boundaries" in summary
            assert "transportation routes" in summary
            assert isinstance(prompt, str)
            assert "Content:" in prompt
            assert asset_content in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_api_error(self):
        """Test summary generation with API error."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(Exception, match="OpenAI API request failed"):
                await generator.generate_summary(metadata)

    @pytest.mark.asyncio
    async def test_generate_summary_timeout(self):
        """Test summary generation with timeout."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(asyncio.TimeoutError):
                await generator.generate_summary(metadata)

    @pytest.mark.asyncio
    async def test_generate_summary_empty_response(self):
        """Test summary generation with empty response."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await generator.generate_summary(metadata)
            
            summary, prompt, output_parser = result
            
            assert summary == ""  # Empty summary after strip()
            assert isinstance(prompt, str)
            assert isinstance(output_parser, dict)

    @pytest.mark.asyncio
    async def test_generate_summary_whitespace_response(self):
        """Test summary generation with whitespace-only response."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "   \n  \t  "
                    }
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await generator.generate_summary(metadata)
            
            summary, prompt, output_parser = result
            
            assert summary == ""  # Empty summary after strip()
            assert isinstance(prompt, str)
            assert isinstance(output_parser, dict)

    @pytest.mark.asyncio
    async def test_generate_summary_long_response(self):
        """Test summary generation with long response."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        long_content = "This is a very long summary that contains detailed information about the historical map, including its creation date, creator, geographic coverage, notable features, historical context, and significance. The summary provides comprehensive information that would be useful for researchers and historians studying this particular time period and geographic region."
        
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": long_content
                    }
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await generator.generate_summary(metadata)
            
            summary, prompt, output_parser = result
            
            assert summary == long_content  # Should preserve the full content
            assert len(summary) > 100  # Verify it's a long summary
            assert isinstance(prompt, str)
            assert isinstance(output_parser, dict)

    @pytest.mark.asyncio
    async def test_generate_summary_network_error(self):
        """Test summary generation with network error."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            with pytest.raises(Exception, match="Network error"):
                await generator.generate_summary(metadata)

    @pytest.mark.asyncio
    async def test_generate_summary_invalid_json_response(self):
        """Test summary generation with invalid JSON response."""
        generator = SummaryGenerator("test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions")
        
        metadata = {"title": "Test Map"}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(Exception):
                await generator.generate_summary(metadata)
