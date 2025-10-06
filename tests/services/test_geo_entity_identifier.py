"""
Tests for the GeoEntityIdentifier.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm.geo_entity_identifier import GeoEntityIdentifier


class TestGeoEntityIdentifier:
    """Test cases for GeoEntityIdentifier class."""

    def test_geo_entity_identifier_initialization(self):
        """Test GeoEntityIdentifier initialization."""
        gazetteer_service = MagicMock()
        identifier = GeoEntityIdentifier(
            api_key="test-key",
            model="gpt-3.5-turbo",
            api_url="https://api.openai.com/v1/chat/completions",
            gazetteer_service=gazetteer_service,
        )

        assert identifier.api_key == "test-key"
        assert identifier.model == "gpt-3.5-turbo"
        assert identifier.api_url == "https://api.openai.com/v1/chat/completions"
        assert identifier.gazetteer_service == gazetteer_service

    def test_geo_entity_identifier_initialization_no_gazetteer(self):
        """Test GeoEntityIdentifier initialization without gazetteer service."""
        identifier = GeoEntityIdentifier(
            api_key="test-key",
            model="gpt-3.5-turbo",
            api_url="https://api.openai.com/v1/chat/completions",
        )

        assert identifier.api_key == "test-key"
        assert identifier.model == "gpt-3.5-turbo"
        assert identifier.api_url == "https://api.openai.com/v1/chat/completions"
        assert identifier.gazetteer_service is None

    def test_construct_geo_entity_prompt_basic(self):
        """Test constructing geo entity prompt without context."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "The Mississippi River flows through Minnesota and Wisconsin."
        prompt, output_parser = identifier._construct_geo_entity_prompt(text)

        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Mississippi River flows through Minnesota and Wisconsin" in prompt
        assert "Identify all geographic named entities" in prompt
        assert "OCLC Fast Gazetteer Names" in prompt
        assert "JSON array of objects" in prompt
        assert output_parser["type"] == "json"
        assert "geographic entities" in output_parser["description"]

    def test_construct_geo_entity_prompt_empty_text(self):
        """Test constructing geo entity prompt with empty text."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = ""
        prompt, output_parser = identifier._construct_geo_entity_prompt(text)

        assert isinstance(prompt, str)
        assert isinstance(output_parser, dict)
        assert "Text:\n" in prompt
        assert output_parser["type"] == "json"

    def test_construct_geo_entity_prompt_examples_included(self):
        """Test that prompt includes OCLC Fast Gazetteer examples."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "Test text"
        prompt, output_parser = identifier._construct_geo_entity_prompt(text)

        # Check that examples are included
        assert "California" in prompt
        assert "Minnesota" in prompt
        assert "Minnesota--Minneapolis" in prompt
        assert "California--San Francisco" in prompt
        assert "New York (State)--New York" in prompt
        assert "New York (State)--New York--Brooklyn" in prompt

    def test_construct_geo_entity_prompt_json_format(self):
        """Test that prompt includes JSON format specification."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "Test text"
        prompt, output_parser = identifier._construct_geo_entity_prompt(text)

        # Check JSON format is specified
        assert "JSON array of objects" in prompt
        assert '"name": "entity name"' in prompt
        assert '"type": "entity type"' in prompt
        assert '"context": "additional context"' in prompt
        assert '"fast_approximation": "fast gazetteer name"' in prompt
        assert '"fast_vectorized_name": ""' in prompt

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_no_service(self):
        """Test enriching entities without gazetteer service."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        entities = [
            {"name": "Minneapolis", "type": "city", "context": "Minnesota"},
            {"name": "Mississippi River", "type": "river", "context": "flows through Midwest"},
        ]

        result = await identifier._enrich_with_gazetteer(entities)

        # Should return entities unchanged
        assert result == entities
        assert len(result) == 2
        assert result[0]["name"] == "Minneapolis"
        assert result[1]["name"] == "Mississippi River"

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_empty_entities(self):
        """Test enriching empty entities list."""
        gazetteer_service = MagicMock()
        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = []

        result = await identifier._enrich_with_gazetteer(entities)

        assert result == []
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_successful_lookup(self):
        """Test enriching entities with successful gazetteer lookup."""
        gazetteer_service = AsyncMock()
        gazetteer_service.lookup_place.return_value = {
            "id": "geo_123",
            "name": "Minneapolis",
            "type": "city",
            "country": "United States",
            "latitude": 44.9778,
            "longitude": -93.2650,
            "confidence": 0.95,
        }

        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = [{"name": "Minneapolis", "type": "city", "context": "Minnesota"}]

        result = await identifier._enrich_with_gazetteer(entities)

        assert len(result) == 1
        assert result[0]["name"] == "Minneapolis"
        assert result[0]["gazetteer_id"] == "geo_123"
        assert result[0]["gazetteer_name"] == "Minneapolis"
        assert result[0]["gazetteer_type"] == "city"
        assert result[0]["gazetteer_country"] == "United States"
        assert result[0]["gazetteer_lat"] == 44.9778
        assert result[0]["gazetteer_lng"] == -93.2650
        assert result[0]["gazetteer_confidence"] == 0.95

        gazetteer_service.lookup_place.assert_called_once_with(
            name="Minneapolis", entity_type="city", context="Minnesota"
        )

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_no_match(self):
        """Test enriching entities with no gazetteer match."""
        gazetteer_service = AsyncMock()
        gazetteer_service.lookup_place.return_value = None

        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = [{"name": "Unknown City", "type": "city", "context": "Unknown"}]

        result = await identifier._enrich_with_gazetteer(entities)

        assert len(result) == 1
        assert result[0]["name"] == "Unknown City"
        # Should not have gazetteer fields
        assert "gazetteer_id" not in result[0]
        assert "gazetteer_name" not in result[0]

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_partial_match(self):
        """Test enriching entities with partial gazetteer data."""
        gazetteer_service = AsyncMock()
        gazetteer_service.lookup_place.return_value = {
            "id": "geo_456",
            "name": "Minnesota",
            "type": "state",
            "country": "United States",
            "latitude": 46.7296,
            "longitude": -94.6859,
            "confidence": 0.88,
        }

        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = [{"name": "Minnesota", "type": "state", "context": "Midwestern state"}]

        result = await identifier._enrich_with_gazetteer(entities)

        assert len(result) == 1
        assert result[0]["name"] == "Minnesota"
        assert result[0]["gazetteer_id"] == "geo_456"
        assert result[0]["gazetteer_confidence"] == 0.88

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_error_handling(self):
        """Test enriching entities with gazetteer service error."""
        gazetteer_service = AsyncMock()
        gazetteer_service.lookup_place.side_effect = Exception("Gazetteer service error")

        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = [{"name": "Test City", "type": "city", "context": "Test"}]

        result = await identifier._enrich_with_gazetteer(entities)

        # Should still return the entity, just without gazetteer data
        assert len(result) == 1
        assert result[0]["name"] == "Test City"
        assert "gazetteer_id" not in result[0]

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_multiple_entities(self):
        """Test enriching multiple entities with mixed results."""
        gazetteer_service = AsyncMock()

        def mock_lookup(name, entity_type, context):
            if name == "Minneapolis":
                return {
                    "id": "geo_123",
                    "name": "Minneapolis",
                    "type": "city",
                    "country": "United States",
                    "latitude": 44.9778,
                    "longitude": -93.2650,
                    "confidence": 0.95,
                }
            elif name == "Unknown City":
                return None
            else:
                raise Exception("Service error")

        gazetteer_service.lookup_place.side_effect = mock_lookup

        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = [
            {"name": "Minneapolis", "type": "city", "context": "Minnesota"},
            {"name": "Unknown City", "type": "city", "context": "Unknown"},
            {"name": "Error City", "type": "city", "context": "Error"},
        ]

        result = await identifier._enrich_with_gazetteer(entities)

        assert len(result) == 3

        # First entity should be enriched
        assert result[0]["name"] == "Minneapolis"
        assert result[0]["gazetteer_id"] == "geo_123"

        # Second entity should not be enriched
        assert result[1]["name"] == "Unknown City"
        assert "gazetteer_id" not in result[1]

        # Third entity should not be enriched due to error
        assert result[2]["name"] == "Error City"
        assert "gazetteer_id" not in result[2]

    @pytest.mark.asyncio
    async def test_enrich_with_gazetteer_missing_context(self):
        """Test enriching entities with missing context field."""
        gazetteer_service = AsyncMock()
        gazetteer_service.lookup_place.return_value = {
            "id": "geo_789",
            "name": "Test City",
            "type": "city",
            "country": "United States",
            "latitude": 40.0,
            "longitude": -90.0,
            "confidence": 0.75,
        }

        identifier = GeoEntityIdentifier(
            "test-key",
            "gpt-3.5-turbo",
            "https://api.openai.com/v1/chat/completions",
            gazetteer_service,
        )

        entities = [
            {"name": "Test City", "type": "city"}  # No context field
        ]

        result = await identifier._enrich_with_gazetteer(entities)

        assert len(result) == 1
        assert result[0]["name"] == "Test City"
        assert result[0]["gazetteer_id"] == "geo_789"

        # Should be called with empty string for context
        gazetteer_service.lookup_place.assert_called_once_with(
            name="Test City", entity_type="city", context=""
        )

    @pytest.mark.asyncio
    async def test_identify_geo_entities_success(self):
        """Test successful geo entity identification."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "The Mississippi River flows through Minneapolis, Minnesota."

        # Mock the API response
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "name": "Mississippi River",
                                    "type": "river",
                                    "context": "major river",
                                    "fast_approximation": "Mississippi River",
                                    "fast_vectorized_name": "",
                                },
                                {
                                    "name": "Minneapolis",
                                    "type": "city",
                                    "context": "in Minnesota",
                                    "fast_approximation": "Minnesota--Minneapolis",
                                    "fast_vectorized_name": "",
                                },
                                {
                                    "name": "Minnesota",
                                    "type": "state",
                                    "context": "Midwestern state",
                                    "fast_approximation": "Minnesota",
                                    "fast_vectorized_name": "",
                                },
                            ]
                        )
                    }
                }
            ]
        }

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await identifier.identify_geo_entities(text)

            entities, prompt, output_parser = result

            assert len(entities) == 3
            assert entities[0]["name"] == "Mississippi River"
            assert entities[1]["name"] == "Minneapolis"
            assert entities[2]["name"] == "Minnesota"
            assert isinstance(prompt, str)
            assert isinstance(output_parser, dict)

    @pytest.mark.asyncio
    async def test_identify_geo_entities_api_error(self):
        """Test geo entity identification with API error."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "Test text"

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(Exception, match="OpenAI API request failed"):
                await identifier.identify_geo_entities(text)

    @pytest.mark.asyncio
    async def test_identify_geo_entities_timeout(self):
        """Test geo entity identification with timeout."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "Test text"

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()

            with pytest.raises(asyncio.TimeoutError):
                await identifier.identify_geo_entities(text)

    @pytest.mark.asyncio
    async def test_identify_geo_entities_invalid_json(self):
        """Test geo entity identification with invalid JSON response."""
        identifier = GeoEntityIdentifier(
            "test-key", "gpt-3.5-turbo", "https://api.openai.com/v1/chat/completions"
        )

        text = "Test text"

        mock_response_data = {"choices": [{"message": {"content": "Invalid JSON response"}}]}

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ValueError):
                await identifier.identify_geo_entities(text)
