"""
Tests for the GazetteerService.

This module tests the GazetteerService which provides methods for looking up
geographic places and entities in the GeoNames database.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gazetteer_service import GazetteerService


class TestGazetteerService:
    """Test cases for GazetteerService."""

    def test_init_without_connection(self):
        """Test GazetteerService initialization without existing connection."""
        service = GazetteerService()

        assert service.db_connection is None
        assert service.db_pool is None

    def test_init_with_connection(self):
        """Test GazetteerService initialization with existing connection."""
        mock_connection = MagicMock()
        service = GazetteerService(db_connection=mock_connection)

        assert service.db_connection == mock_connection
        assert service.db_pool is None

    @pytest.mark.asyncio
    async def test_connect_with_existing_connection(self):
        """Test connect method when connection already exists."""
        mock_connection = MagicMock()
        service = GazetteerService(db_connection=mock_connection)

        # Should not create new connection
        await service.connect()
        assert service.db_connection == mock_connection
        assert service.db_pool is None

    @pytest.mark.asyncio
    async def test_connect_without_database_url(self):
        """Test connect method fails when DATABASE_URL is not set."""
        service = GazetteerService()

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DATABASE_URL environment variable is not set"):
                await service.connect()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful database connection."""
        service = GazetteerService()
        mock_pool = AsyncMock()

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch(
                "app.services.gazetteer_service.asyncpg.create_pool", new_callable=AsyncMock
            ) as mock_create_pool:
                mock_create_pool.return_value = mock_pool
                await service.connect()

                assert service.db_pool == mock_pool

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test database connection failure."""
        service = GazetteerService()

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch(
                "app.services.gazetteer_service.asyncpg.create_pool",
                side_effect=Exception("Connection failed"),
            ):
                with pytest.raises(Exception, match="Connection failed"):
                    await service.connect()

    @pytest.mark.asyncio
    async def test_disconnect_with_pool(self):
        """Test disconnect method with existing pool."""
        service = GazetteerService()
        mock_pool = AsyncMock()
        service.db_pool = mock_pool

        await service.disconnect()

        mock_pool.close.assert_called_once()
        assert service.db_pool is None

    @pytest.mark.asyncio
    async def test_disconnect_without_pool(self):
        """Test disconnect method without existing pool."""
        service = GazetteerService()

        # Should not raise an error
        await service.disconnect()

    def test_get_feature_class_valid_types(self):
        """Test _get_feature_class with valid entity types."""
        service = GazetteerService()

        test_cases = [
            ("country", "A"),
            ("state", "A"),
            ("city", "P"),
            ("town", "P"),
            ("village", "P"),
            ("river", "H"),
            ("lake", "H"),
            ("ocean", "H"),
            ("mountain", "T"),
            ("hill", "T"),
            ("forest", "V"),
            ("park", "L"),
            ("island", "L"),
        ]

        for entity_type, expected_class in test_cases:
            result = service._get_feature_class(entity_type)
            assert result == expected_class

    def test_get_feature_class_invalid_type(self):
        """Test _get_feature_class with invalid entity type."""
        service = GazetteerService()

        result = service._get_feature_class("invalid_type")
        assert result is None

    def test_get_feature_class_case_insensitive(self):
        """Test _get_feature_class is case insensitive."""
        service = GazetteerService()

        result = service._get_feature_class("CITY")
        assert result == "P"

    def test_get_entity_type_feature_classes(self):
        """Test _get_entity_type with different feature classes."""
        service = GazetteerService()

        test_cases = [
            ("A", None, "administrative"),
            ("H", None, "hydrographic"),
            ("L", None, "area"),
            ("P", None, "populated place"),
            ("R", None, "road"),
            ("S", None, "spot"),
            ("T", None, "hypsographic"),
            ("U", None, "undersea"),
            ("V", None, "vegetation"),
            ("X", None, "unknown"),  # Unknown feature class
        ]

        for feature_class, feature_code, expected in test_cases:
            result = service._get_entity_type(feature_class, feature_code)
            assert result == expected

    def test_get_entity_type_with_feature_codes(self):
        """Test _get_entity_type with feature codes for refinement."""
        service = GazetteerService()

        test_cases = [
            ("P", "PPL", "city"),
            ("P", "PPLA", "capital"),
            ("P", "PPLG", "seat of government"),
            ("H", "STM", "stream"),
            ("H", "RV", "river"),
            ("H", "LK", "lake"),
            ("H", "OCN", "ocean"),
            ("H", "SEA", "sea"),
        ]

        for feature_class, feature_code, expected in test_cases:
            result = service._get_entity_type(feature_class, feature_code)
            assert result == expected

    def test_get_entity_type_none_feature_class(self):
        """Test _get_entity_type with None feature class."""
        service = GazetteerService()

        result = service._get_entity_type(None, None)
        assert result == "unknown"

    def test_calculate_confidence_base(self):
        """Test _calculate_confidence base score."""
        service = GazetteerService()

        result = {
            "name": "Test City",
            "asciiname": "Test City",
            "feature_class": "P",
            "feature_code": "PPL",
            "population": 100000,
        }

        confidence = service._calculate_confidence(result, "Test", None)
        # Base confidence (0.5) + population factor (100000/10000000 * 0.1 = 0.001)
        assert confidence == 0.501

    def test_calculate_confidence_exact_name_match(self):
        """Test _calculate_confidence with exact name match."""
        service = GazetteerService()

        result = {
            "name": "Test City",
            "asciiname": "Test City",
            "feature_class": "P",
            "feature_code": "PPL",
            "population": 100000,
        }

        confidence = service._calculate_confidence(result, "Test City", None)
        # Base (0.5) + exact match (0.3) + population factor (0.001)
        assert confidence == 0.801

    def test_calculate_confidence_ascii_name_match(self):
        """Test _calculate_confidence with ascii name match."""
        service = GazetteerService()

        result = {
            "name": "Different Name",
            "asciiname": "Test City",
            "feature_class": "P",
            "feature_code": "PPL",
            "population": 100000,
        }

        confidence = service._calculate_confidence(result, "Test City", None)
        # Base (0.5) + ascii match (0.2) + population factor (0.001)
        assert confidence == 0.701

    def test_calculate_confidence_entity_type_match(self):
        """Test _calculate_confidence with entity type match."""
        service = GazetteerService()

        result = {
            "name": "Test City",
            "asciiname": "Test City",
            "feature_class": "P",
            "feature_code": "PPL",
            "population": 100000,
        }

        confidence = service._calculate_confidence(result, "Test", "city")
        # Base (0.5) + entity type match (0.2) + population factor (0.001)
        assert confidence == 0.701

    def test_calculate_confidence_population_factor(self):
        """Test _calculate_confidence with population factor."""
        service = GazetteerService()

        result = {
            "name": "Test City",
            "asciiname": "Test City",
            "feature_class": "P",
            "feature_code": "PPL",
            "population": 5000000,  # 5 million
        }

        confidence = service._calculate_confidence(result, "Test", None)
        expected = 0.5 + 0.05  # Base + population factor (5M/10M * 0.1)
        assert confidence == expected

    def test_calculate_confidence_max_cap(self):
        """Test _calculate_confidence is capped at 1.0."""
        service = GazetteerService()

        result = {
            "name": "Test City",
            "asciiname": "Test City",
            "feature_class": "P",
            "feature_code": "PPL",
            "population": 50000000,  # Very large population
        }

        confidence = service._calculate_confidence(result, "Test City", "city")
        assert confidence == 1.0  # Should be capped

    @pytest.mark.asyncio
    async def test_lookup_place_success(self):
        """Test successful place lookup."""
        service = GazetteerService()

        # Mock database response
        mock_row = {
            "id": 12345,
            "name": "Test City",
            "asciiname": "Test City",
            "alternatenames": "Test, Testville",
            "feature_class": "P",
            "feature_code": "PPL",
            "country_code": "US",
            "cc2": None,
            "admin1_code": "CA",
            "admin2_code": "001",
            "admin3_code": None,
            "admin4_code": None,
            "population": 100000,
            "elevation": None,
            "dem": 100,
            "timezone": "America/Los_Angeles",
            "modification_date": "2023-01-01",
            "latitude": 37.7749,
            "longitude": -122.4194,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        mock_pool = AsyncMock()
        mock_pool.acquire.return_value = mock_conn
        mock_pool.release = AsyncMock()

        service.db_pool = mock_pool

        # Mock country name lookup
        with patch.object(service, "_get_country_name", return_value="United States"):
            result = await service.lookup_place("Test City")

            assert result is not None
            assert result["id"] == 12345
            assert result["name"] == "Test City"
            assert result["confidence"] > 0
            assert result["country"] == "United States"
            assert result["type"] == "city"

    @pytest.mark.asyncio
    async def test_lookup_place_not_found(self):
        """Test place lookup when no results found."""
        service = GazetteerService()

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        mock_pool = AsyncMock()
        mock_pool.acquire.return_value = mock_conn
        mock_pool.release = AsyncMock()

        service.db_pool = mock_pool

        result = await service.lookup_place("Nonexistent City")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_place_with_entity_type(self):
        """Test place lookup with entity type filter."""
        service = GazetteerService()

        mock_row = {
            "id": 12345,
            "name": "Test River",
            "asciiname": "Test River",
            "alternatenames": None,
            "feature_class": "H",
            "feature_code": "STM",
            "country_code": "US",
            "cc2": None,
            "admin1_code": None,
            "admin2_code": None,
            "admin3_code": None,
            "admin4_code": None,
            "population": None,
            "elevation": None,
            "dem": None,
            "timezone": "America/Los_Angeles",
            "modification_date": "2023-01-01",
            "latitude": 37.7749,
            "longitude": -122.4194,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        mock_pool = AsyncMock()
        mock_pool.acquire.return_value = mock_conn
        mock_pool.release = AsyncMock()

        service.db_pool = mock_pool

        result = await service.lookup_place("Test River", entity_type="river")

        assert result is not None
        assert result["name"] == "Test River"
        assert result["type"] == "stream"

    @pytest.mark.asyncio
    async def test_lookup_place_database_error(self):
        """Test place lookup with database error."""
        service = GazetteerService()

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("Database error")

        service.db_pool = mock_pool

        result = await service.lookup_place("Test City")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_country_name_success(self):
        """Test successful country name lookup."""
        service = GazetteerService()

        mock_row = {"name": "United States"}
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        mock_pool = AsyncMock()
        mock_pool.acquire.return_value = mock_conn
        mock_pool.release = AsyncMock()

        service.db_pool = mock_pool

        result = await service._get_country_name("US")

        assert result == "United States"

    @pytest.mark.asyncio
    async def test_get_country_name_not_found(self):
        """Test country name lookup when not found."""
        service = GazetteerService()

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        mock_pool = AsyncMock()
        mock_pool.acquire.return_value = mock_conn
        mock_pool.release = AsyncMock()

        service.db_pool = mock_pool

        result = await service._get_country_name("XX")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_country_name_error(self):
        """Test country name lookup with database error."""
        service = GazetteerService()

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("Database error")

        service.db_pool = mock_pool

        result = await service._get_country_name("US")

        assert result is None

    def test_entity_type_mapping_comprehensive(self):
        """Test comprehensive entity type mapping for common features."""
        service = GazetteerService()

        # Test specific feature codes that are handled specially
        special_cases = [
            ("P", "PPL", "city"),
            ("P", "PPLA", "capital"),
            ("P", "PPLG", "seat of government"),
            ("H", "STM", "stream"),
            ("H", "RV", "river"),
            ("H", "LK", "lake"),
            ("H", "OCN", "ocean"),
            ("H", "SEA", "sea"),
        ]

        for feature_class, feature_code, expected_type in special_cases:
            result = service._get_entity_type(feature_class, feature_code)
            assert result == expected_type

        # Test that other feature codes fall back to base class types
        base_class_cases = [
            ("A", "ADM1", "administrative"),
            ("H", "STMA", "hydrographic"),
            ("T", "MT", "hypsographic"),
            ("L", "PARK", "area"),
            ("R", "RD", "road"),
            ("S", "SPOT", "spot"),
            ("U", "UPLD", "undersea"),
            ("V", "FRST", "vegetation"),
        ]

        for feature_class, feature_code, expected_type in base_class_cases:
            result = service._get_entity_type(feature_class, feature_code)
            assert result == expected_type
