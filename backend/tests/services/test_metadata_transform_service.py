"""Tests for the metadata transform service (ISO 19139, FGDC XML to HTML)."""

import pytest

from app.services.metadata_transform_service import (
    MetadataTransformError,
    transform_fgdc_to_html,
    transform_iso_to_html,
)

# Minimal valid ISO 19139 XML
SAMPLE_ISO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd"
    xmlns:gco="http://www.isotc211.org/2005/gco">
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification>
      <gmd:citation>
        <gmd:CI_Citation>
          <gmd:title><gco:CharacterString>Test Dataset</gco:CharacterString></gmd:title>
        </gmd:CI_Citation>
      </gmd:citation>
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
</gmd:MD_Metadata>
"""

# Minimal valid FGDC/CSDGM XML
SAMPLE_FGDC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata>
  <idinfo>
    <citation>
      <citeinfo>
        <title>Test FGDC Dataset</title>
        <origin>Test Originator</origin>
      </citeinfo>
    </citation>
  </idinfo>
</metadata>
"""


class TestTransformIsoToHtml:
    """Test ISO 19139 to HTML transformation."""

    def test_transform_iso_to_html_returns_html(self):
        """Transform produces HTML output."""
        html = transform_iso_to_html(SAMPLE_ISO_XML)
        assert isinstance(html, str)
        assert "<html" in html.lower()
        assert "<body" in html.lower()
        assert "Test Dataset" in html

    def test_transform_iso_to_html_accepts_bytes(self):
        """Transform accepts bytes input."""
        html = transform_iso_to_html(SAMPLE_ISO_XML.encode("utf-8"))
        assert "<html" in html.lower()
        assert "Test Dataset" in html

    def test_transform_iso_to_html_empty_raises(self):
        """Empty content raises MetadataTransformError."""
        with pytest.raises(MetadataTransformError, match="Empty"):
            transform_iso_to_html("")

    def test_transform_iso_to_html_whitespace_only_raises(self):
        """Whitespace-only content raises MetadataTransformError."""
        with pytest.raises(MetadataTransformError, match="Empty"):
            transform_iso_to_html("   \n  ")

    def test_transform_iso_to_html_invalid_xml_raises(self):
        """Invalid XML raises MetadataTransformError."""
        with pytest.raises(MetadataTransformError, match="Invalid"):
            transform_iso_to_html("<not-valid-xml")


class TestTransformFgdcToHtml:
    """Test FGDC/CSDGM to HTML transformation."""

    def test_transform_fgdc_to_html_returns_html(self):
        """Transform produces HTML output."""
        html = transform_fgdc_to_html(SAMPLE_FGDC_XML)
        assert isinstance(html, str)
        assert "<html" in html.lower()
        assert "<body" in html.lower()
        assert "Test FGDC Dataset" in html or "Test Originator" in html

    def test_transform_fgdc_to_html_accepts_bytes(self):
        """Transform accepts bytes input."""
        html = transform_fgdc_to_html(SAMPLE_FGDC_XML.encode("utf-8"))
        assert "<html" in html.lower()

    def test_transform_fgdc_to_html_empty_raises(self):
        """Empty content raises MetadataTransformError."""
        with pytest.raises(MetadataTransformError, match="Empty"):
            transform_fgdc_to_html("")

    def test_transform_fgdc_to_html_invalid_xml_raises(self):
        """Invalid XML raises MetadataTransformError."""
        with pytest.raises(MetadataTransformError, match="Invalid"):
            transform_fgdc_to_html("<metadata><unclosed>")
