"""
Tests for CitationService - comprehensive coverage using real fixtures and data.
"""

import json

from app.services.citation_service import CitationService


class TestCitationService:
    """Test cases for CitationService initialization and basic functionality."""

    def test_init_with_document(self):
        """Test CitationService initialization with document data."""
        document = {
            "id": "test-document-123",
            "dct_title_s": "Test Document",
            "dct_creator_sm": ["Test Author"],
        }

        service = CitationService(document)
        assert service.document == document

    def test_init_with_empty_document(self):
        """Test CitationService initialization with empty document."""
        document = {}

        service = CitationService(document)
        assert service.document == document

    def test_init_with_various_document_structures(self):
        """Test initialization with different document structures."""
        test_cases = [
            {"id": "simple-document"},
            {"dct_title_s": "Document with title"},
            {"dct_creator_sm": ["Author 1", "Author 2"]},
            {"dct_references_s": '{"http://schema.org/url": "http://example.com"}'},
            {"gbl_resourcetype_sm": ["datasets"]},
            {"dct_publisher_sm": ["Publisher Name"]},
            {"dct_issued_s": "2023-01-01"},
            {"schema_provider_s": "Provider Name"},
        ]

        for document in test_cases:
            service = CitationService(document)
            assert service.document == document


class TestCitationServiceURLMethods:
    """Test cases for URL-related methods."""

    def test_get_url_with_schema_url(self):
        """Test getting URL from schema.org/url reference."""
        document = {
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/document"})
        }

        service = CitationService(document)
        url = service._get_url()

        assert url == "http://example.com/document"

    def test_get_url_with_download_url(self):
        """Test getting URL from schema.org/downloadUrl reference."""
        document = {
            "dct_references_s": json.dumps(
                {"http://schema.org/downloadUrl": "http://example.com/download"}
            )
        }

        service = CitationService(document)
        url = service._get_url()

        assert url == "http://example.com/download"

    def test_get_url_with_both_urls(self):
        """Test getting URL when both schema.org/url and downloadUrl exist."""
        document = {
            "dct_references_s": json.dumps(
                {
                    "http://schema.org/url": "http://example.com/document",
                    "http://schema.org/downloadUrl": "http://example.com/download",
                }
            )
        }

        service = CitationService(document)
        url = service._get_url()

        # Should prefer schema.org/url
        assert url == "http://example.com/document"

    def test_get_url_with_dict_references(self):
        """Test getting URL when references is already a dictionary."""
        document = {"dct_references_s": {"http://schema.org/url": "http://example.com/document"}}

        service = CitationService(document)
        url = service._get_url()

        # Application now supports dict references as well
        assert url == "http://example.com/document"

    def test_get_url_with_invalid_json(self):
        """Test getting URL with invalid JSON in references."""
        document = {"dct_references_s": "invalid json string"}

        service = CitationService(document)
        url = service._get_url()

        assert url is None

    def test_get_url_with_no_urls(self):
        """Test getting URL when no URLs exist in references."""
        document = {
            "dct_references_s": json.dumps(
                {"http://iiif.io/api/image": "http://example.com/iiif/image"}
            )
        }

        service = CitationService(document)
        url = service._get_url()

        assert url is None

    def test_get_url_with_empty_references(self):
        """Test getting URL with empty references."""
        document = {"dct_references_s": json.dumps({})}

        service = CitationService(document)
        url = service._get_url()

        assert url is None

    def test_get_url_with_missing_references(self):
        """Test getting URL when references field is missing."""
        document = {"dct_title_s": "Test Document"}

        service = CitationService(document)
        url = service._get_url()

        assert url is None

    def test_get_url_with_none_references(self):
        """Test getting URL when references is None."""
        document = {"dct_references_s": None}

        service = CitationService(document)
        url = service._get_url()

        assert url is None


class TestCitationServiceResourceTypeMethods:
    """Test cases for resource type methods."""

    def test_get_resource_type_with_list(self):
        """Test getting resource type from list."""
        document = {"gbl_resourcetype_sm": ["datasets", "web services"]}

        service = CitationService(document)
        resource_type = service._get_resource_type()

        assert resource_type == "datasets"

    def test_get_resource_type_with_single_item_list(self):
        """Test getting resource type from single-item list."""
        document = {"gbl_resourcetype_sm": ["maps"]}

        service = CitationService(document)
        resource_type = service._get_resource_type()

        assert resource_type == "maps"

    def test_get_resource_type_with_empty_list(self):
        """Test getting resource type from empty list."""
        document = {"gbl_resourcetype_sm": []}

        service = CitationService(document)
        resource_type = service._get_resource_type()

        assert resource_type == ""

    def test_get_resource_type_with_non_list(self):
        """Test getting resource type when field is not a list."""
        document = {"gbl_resourcetype_sm": "datasets"}

        service = CitationService(document)
        resource_type = service._get_resource_type()

        assert resource_type == ""

    def test_get_resource_type_with_missing_field(self):
        """Test getting resource type when field is missing."""
        document = {"dct_title_s": "Test Document"}

        service = CitationService(document)
        resource_type = service._get_resource_type()

        assert resource_type == ""

    def test_get_resource_type_with_none_value(self):
        """Test getting resource type when field is None."""
        document = {"gbl_resourcetype_sm": None}

        service = CitationService(document)
        resource_type = service._get_resource_type()

        assert resource_type == ""


class TestCitationServiceCreatorMethods:
    """Test cases for creator-related methods."""

    def test_get_creators_with_list(self):
        """Test getting creators from list."""
        document = {"dct_creator_sm": ["Author 1", "Author 2", "Author 3"]}

        service = CitationService(document)
        creators = service._get_creators()

        assert creators == ["Author 1", "Author 2", "Author 3"]

    def test_get_creators_with_single_creator(self):
        """Test getting single creator from list."""
        document = {"dct_creator_sm": ["Single Author"]}

        service = CitationService(document)
        creators = service._get_creators()

        assert creators == ["Single Author"]

    def test_get_creators_with_empty_list(self):
        """Test getting creators from empty list."""
        document = {"dct_creator_sm": []}

        service = CitationService(document)
        creators = service._get_creators()

        assert creators == []

    def test_get_creators_with_non_list(self):
        """Test getting creators when field is not a list."""
        document = {"dct_creator_sm": "Single Author"}

        service = CitationService(document)
        creators = service._get_creators()

        assert creators == []

    def test_get_creators_with_missing_field(self):
        """Test getting creators when field is missing."""
        document = {"dct_title_s": "Test Document"}

        service = CitationService(document)
        creators = service._get_creators()

        assert creators == []

    def test_get_creators_with_none_value(self):
        """Test getting creators when field is None."""
        document = {"dct_creator_sm": None}

        service = CitationService(document)
        creators = service._get_creators()

        assert creators == []


class TestCitationServicePublisherMethods:
    """Test cases for publisher-related methods."""

    def test_get_publishers_with_list(self):
        """Test getting publishers from list."""
        document = {"dct_publisher_sm": ["Publisher 1", "Publisher 2"]}

        service = CitationService(document)
        publishers = service._get_publishers()

        assert publishers == ["Publisher 1", "Publisher 2"]

    def test_get_publishers_with_single_publisher(self):
        """Test getting single publisher from list."""
        document = {"dct_publisher_sm": ["Single Publisher"]}

        service = CitationService(document)
        publishers = service._get_publishers()

        assert publishers == ["Single Publisher"]

    def test_get_publishers_with_empty_list(self):
        """Test getting publishers from empty list."""
        document = {"dct_publisher_sm": []}

        service = CitationService(document)
        publishers = service._get_publishers()

        assert publishers == []

    def test_get_publishers_with_non_list(self):
        """Test getting publishers when field is not a list."""
        document = {"dct_publisher_sm": "Single Publisher"}

        service = CitationService(document)
        publishers = service._get_publishers()

        assert publishers == []

    def test_get_publishers_with_missing_field(self):
        """Test getting publishers when field is missing."""
        document = {"dct_title_s": "Test Document"}

        service = CitationService(document)
        publishers = service._get_publishers()

        assert publishers == []

    def test_get_publishers_with_none_value(self):
        """Test getting publishers when field is None."""
        document = {"dct_publisher_sm": None}

        service = CitationService(document)
        publishers = service._get_publishers()

        assert publishers == []


class TestCitationServiceGetCitation:
    """Test cases for the main get_citation method."""

    def test_get_citation_complete_document(self):
        """Test generating citation with complete document data."""
        document = {
            "dct_creator_sm": ["John Doe", "Jane Smith"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Document Title",
            "dct_publisher_sm": ["Test Publisher"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/document"}
            ),
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "John Doe, Jane Smith." in citation
        assert "(2023-01-01)." in citation
        assert "Test Document Title." in citation
        assert "Test Publisher." in citation
        assert "http://example.com/document" in citation
        assert "(map)" in citation

    def test_get_citation_with_datasets_resource_type(self):
        """Test generating citation with datasets resource type."""
        document = {
            "dct_creator_sm": ["Data Creator"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Dataset",
            "schema_provider_s": "Data Provider",
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/dataset"}),
            "gbl_resourcetype_sm": ["datasets"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Data Creator." in citation
        assert "(2023-01-01)." in citation
        assert "Test Dataset." in citation
        assert "Data Provider." in citation
        assert "http://example.com/dataset" in citation
        assert "(dataset)" in citation

    def test_get_citation_with_web_services_resource_type(self):
        """Test generating citation with web services resource type."""
        document = {
            "dct_creator_sm": ["Service Creator"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Web Service",
            "schema_provider_s": "Service Provider",
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/service"}),
            "gbl_resourcetype_sm": ["web services"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Service Creator." in citation
        assert "(2023-01-01)." in citation
        assert "Test Web Service." in citation
        assert "Service Provider." in citation
        assert "http://example.com/service" in citation
        assert "(web service)" in citation

    def test_get_citation_without_creators(self):
        """Test generating citation without creators."""
        document = {
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Document",
            "dct_publisher_sm": ["Test Publisher"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/document"}
            ),
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "[Creator not found]," in citation
        assert "(2023-01-01)." in citation
        assert "Test Document." in citation

    def test_get_citation_without_date(self):
        """Test generating citation without date."""
        document = {
            "dct_creator_sm": ["Test Author"],
            "dct_title_s": "Test Document",
            "dct_publisher_sm": ["Test Publisher"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/document"}
            ),
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Test Author." in citation
        assert "(n.d.)." in citation
        assert "Test Document." in citation

    def test_get_citation_without_title(self):
        """Test generating citation without title."""
        document = {
            "dct_creator_sm": ["Test Author"],
            "dct_issued_s": "2023-01-01",
            "dct_publisher_sm": ["Test Publisher"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/document"}
            ),
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Test Author." in citation
        assert "(2023-01-01)." in citation
        # Title should not be in citation
        assert "Test Document" not in citation

    def test_get_citation_without_publisher_or_provider(self):
        """Test generating citation without publisher or provider."""
        document = {
            "dct_creator_sm": ["Test Author"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Document",
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/document"}
            ),
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Test Author." in citation
        assert "(2023-01-01)." in citation
        assert "Test Document." in citation
        # No publisher should be in citation

    def test_get_citation_without_url(self):
        """Test generating citation without URL."""
        document = {
            "dct_creator_sm": ["Test Author"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Document",
            "dct_publisher_sm": ["Test Publisher"],
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Test Author." in citation
        assert "(2023-01-01)." in citation
        assert "Test Document." in citation
        assert "Test Publisher." in citation
        # No URL should be in citation

    def test_get_citation_without_resource_type(self):
        """Test generating citation without resource type."""
        document = {
            "dct_creator_sm": ["Test Author"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Document",
            "dct_publisher_sm": ["Test Publisher"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/document"}
            ),
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Test Author." in citation
        assert "(2023-01-01)." in citation
        assert "Test Document." in citation
        assert "Test Publisher." in citation
        # No resource type should be in citation

    def test_get_citation_minimal_document(self):
        """Test generating citation with minimal document data."""
        document = {"dct_title_s": "Minimal Document"}

        service = CitationService(document)
        citation = service.get_citation()

        assert "[Creator not found]," in citation
        assert "(n.d.)." in citation
        assert "Minimal Document." in citation

    def test_get_citation_empty_document(self):
        """Test generating citation with empty document."""
        document = {}

        service = CitationService(document)
        citation = service.get_citation()

        assert "[Creator not found]," in citation
        assert "(n.d.)." in citation

    def test_get_citation_resource_type_singularization(self):
        """Test that resource types are properly singularized."""
        test_cases = [
            ("datasets", "dataset"),
            ("maps", "map"),
            ("web services", "web service"),
            ("images", "image"),
            ("documents", "document"),
            ("reports", "report"),
        ]

        for plural_type, expected_singular in test_cases:
            document = {
                "dct_creator_sm": ["Test Author"],
                "dct_issued_s": "2023-01-01",
                "dct_title_s": "Test Document",
                "gbl_resourcetype_sm": [plural_type],
            }

            service = CitationService(document)
            citation = service.get_citation()

            assert f"({expected_singular})" in citation

    def test_get_citation_error_handling(self):
        """Test citation generation error handling."""
        # Create a document that might cause issues
        document = {
            "dct_creator_sm": ["Test Author"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Test Document",
            "dct_references_s": "invalid json",
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        # Should still generate a citation despite JSON error
        assert "Test Author." in citation
        assert "(2023-01-01)." in citation
        assert "Test Document." in citation


class TestCitationServiceEdgeCases:
    """Test cases for edge cases and error conditions."""

    def test_citation_with_unicode_content(self):
        """Test citation generation with Unicode content."""
        document = {
            "dct_creator_sm": ["José García", "François Müller"],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Documento con Acentos y Ñ",
            "dct_publisher_sm": ["Éditeur Français"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/unicode-document"}
            ),
            "gbl_resourcetype_sm": ["maps"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "José García, François Müller." in citation
        assert "Documento con Acentos y Ñ." in citation
        assert "Éditeur Français." in citation

    def test_citation_with_special_characters(self):
        """Test citation generation with special characters."""
        document = {
            "dct_creator_sm": ["Author & Co.", "Smith, Jr."],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": "Document with Special Characters: A Study",
            "dct_publisher_sm": ["Publisher & Associates"],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/special-chars"}
            ),
            "gbl_resourcetype_sm": ["reports"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "Author & Co., Smith, Jr." in citation
        assert "Document with Special Characters: A Study." in citation
        assert "Publisher & Associates." in citation

    def test_citation_with_very_long_fields(self):
        """Test citation generation with very long field values."""
        long_title = "A" * 500
        long_creator = "B" * 200
        long_publisher = "C" * 200

        document = {
            "dct_creator_sm": [long_creator],
            "dct_issued_s": "2023-01-01",
            "dct_title_s": long_title,
            "dct_publisher_sm": [long_publisher],
            "dct_references_s": json.dumps(
                {"http://schema.org/url": "http://example.com/long-document"}
            ),
            "gbl_resourcetype_sm": ["documents"],
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert long_creator in citation
        assert long_title in citation
        assert long_publisher in citation

    def test_citation_with_none_values(self):
        """Test citation generation with None values."""
        document = {
            "dct_creator_sm": None,
            "dct_issued_s": None,
            "dct_title_s": None,
            "dct_publisher_sm": None,
            "dct_references_s": None,
            "gbl_resourcetype_sm": None,
        }

        service = CitationService(document)
        citation = service.get_citation()

        assert "[Creator not found]," in citation
        assert "(n.d.)." in citation

    def test_citation_with_mixed_data_types(self):
        """Test citation generation with mixed data types."""
        document = {
            "dct_creator_sm": "Single Creator String",  # Should be list
            "dct_issued_s": 2023,  # Should be string
            "dct_title_s": ["Title as List"],  # Should be string
            "dct_publisher_sm": "Single Publisher String",  # Should be list
            "gbl_resourcetype_sm": "Single Resource Type",  # Should be list
            "schema_provider_s": ["Provider as List"],  # Should be string
        }

        service = CitationService(document)
        citation = service.get_citation()

        # Should handle mixed types gracefully
        assert "[Creator not found]," in citation
        # The date 2023 is treated as truthy, so it gets included as "(2023)."
        assert "(2023)." in citation
