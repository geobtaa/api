"""
Transform geospatial metadata XML (ISO 19139, FGDC) to HTML using GeoCombine XSLT.
"""

import logging
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)

_XSLT_DIR = Path(__file__).resolve().parent.parent / "metadata" / "xslt"


class MetadataTransformError(Exception):
    """Raised when metadata transformation fails."""

    pass


def _load_xslt(filename: str) -> etree.XSLT:
    """Load and compile an XSLT stylesheet."""
    path = _XSLT_DIR / filename
    if not path.exists():
        raise MetadataTransformError(f"XSLT file not found: {path}")
    with open(path, "rb") as f:
        xslt_doc = etree.parse(f)
    return etree.XSLT(xslt_doc)


def transform_iso_to_html(xml_content: str | bytes) -> str:
    """
    Transform ISO 19139 XML to HTML using GeoCombine iso2html.xsl.

    Args:
        xml_content: Raw ISO 19139 XML as string or bytes.

    Returns:
        HTML string.

    Raises:
        MetadataTransformError: On parse or transform failure.
    """
    if not xml_content or (isinstance(xml_content, str) and not xml_content.strip()):
        raise MetadataTransformError("Empty metadata content")

    try:
        if isinstance(xml_content, str):
            xml_content = xml_content.encode("utf-8")
        doc = etree.fromstring(xml_content)
    except etree.XMLSyntaxError as e:
        raise MetadataTransformError(f"Invalid ISO XML: {e}") from e

    try:
        xslt = _load_xslt("iso2html.xsl")
        result = xslt(doc)
        return str(result)
    except Exception as e:
        raise MetadataTransformError(f"ISO transform failed: {e}") from e


def transform_fgdc_to_html(xml_content: str | bytes) -> str:
    """
    Transform FGDC/CSDGM XML to HTML using GeoCombine fgdc2html.xsl.

    Args:
        xml_content: Raw FGDC XML as string or bytes.

    Returns:
        HTML string.

    Raises:
        MetadataTransformError: On parse or transform failure.
    """
    if not xml_content or (isinstance(xml_content, str) and not xml_content.strip()):
        raise MetadataTransformError("Empty metadata content")

    try:
        if isinstance(xml_content, str):
            xml_content = xml_content.encode("utf-8")
        doc = etree.fromstring(xml_content)
    except etree.XMLSyntaxError as e:
        raise MetadataTransformError(f"Invalid FGDC XML: {e}") from e

    try:
        xslt = _load_xslt("fgdc2html.xsl")
        result = xslt(doc)
        return str(result)
    except Exception as e:
        raise MetadataTransformError(f"FGDC transform failed: {e}") from e
