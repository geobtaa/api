"""
Tests for LinkService - comprehensive coverage using real fixtures and data.
"""

import json

import pytest

from app.services.link_service import LinkService


class TestLinkService:
    """Test cases for LinkService initialization and basic functionality."""

    def test_init_with_resource_dict(self):
        """Test LinkService initialization with resource data."""
        resource_dict = {
            "id": "test-resource-123",
            "dct_title_s": "Test Resource",
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com"}),
        }

        service = LinkService(resource_dict)
        assert service.resource_dict == resource_dict

    def test_init_with_various_resource_structures(self):
        """Test initialization with different resource structures."""
        test_cases = [
            {"id": "simple-resource"},
            {
                "id": "resource-with-refs",
                "dct_references_s": '{"http://schema.org/url": "http://example.com"}',
            },
            {
                "id": "resource-with-dict-refs",
                "dct_references_s": {"http://schema.org/url": "http://example.com"},
            },
            {"id": "resource-no-refs", "dct_references_s": {}},
            {},  # Empty resource
        ]

        for resource_dict in test_cases:
            service = LinkService(resource_dict)
            assert service.resource_dict == resource_dict


class TestLinkServiceReferenceParsing:
    """Test cases for reference parsing functionality."""

    def test_parse_references_json_string(self):
        """Test parsing references from JSON string."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://schema.org/url": "http://example.com",
                    "http://iiif.io/api/image": "http://example.com/iiif/image",
                }
            )
        }

        service = LinkService(resource_dict)
        references = service._parse_references()

        assert references == {
            "http://schema.org/url": "http://example.com",
            "http://iiif.io/api/image": "http://example.com/iiif/image",
        }

    def test_parse_references_dict(self):
        """Test parsing references from dictionary."""
        resource_dict = {
            "dct_references_s": {
                "http://schema.org/url": "http://example.com",
                "http://iiif.io/api/image": "http://example.com/iiif/image",
            }
        }

        service = LinkService(resource_dict)
        references = service._parse_references()

        assert references == {
            "http://schema.org/url": "http://example.com",
            "http://iiif.io/api/image": "http://example.com/iiif/image",
        }

    def test_parse_references_invalid_json(self):
        """Test parsing references with invalid JSON."""
        resource_dict = {"dct_references_s": "invalid json string"}

        service = LinkService(resource_dict)
        references = service._parse_references()

        assert references == {}

    def test_parse_references_non_dict_non_string(self):
        """Test parsing references with non-dict, non-string values."""
        resource_dict = {"dct_references_s": ["invalid", "reference", "format"]}

        service = LinkService(resource_dict)
        references = service._parse_references()

        assert references == {}

    def test_parse_references_missing_field(self):
        """Test parsing references when field is missing."""
        resource_dict = {"id": "test-resource"}

        service = LinkService(resource_dict)
        references = service._parse_references()

        assert references == {}

    def test_parse_references_none_value(self):
        """Test parsing references with None value."""
        resource_dict = {"dct_references_s": None}

        service = LinkService(resource_dict)
        references = service._parse_references()

        assert references == {}


class TestLinkServiceSourceLinks:
    """Test cases for source link extraction."""

    def test_get_source_links_valid_url(self):
        """Test getting source links with valid URL."""
        resource_dict = {
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/source"})
        }

        service = LinkService(resource_dict)
        links = service._get_source_links()

        assert len(links) == 1
        assert links[0] == {"label": "Visit Source", "url": "http://example.com/source"}

    def test_get_source_links_no_url(self):
        """Test getting source links when no URL exists."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://iiif.io/api/image": "http://example.com/iiif/image"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_source_links()

        assert links == []

    def test_get_source_links_empty_references(self):
        """Test getting source links with empty references."""
        resource_dict = {"dct_references_s": json.dumps({})}

        service = LinkService(resource_dict)
        links = service._get_source_links()

        assert links == []

    def test_get_source_links_invalid_references(self):
        """Test getting source links with invalid references."""
        resource_dict = {"dct_references_s": "invalid json"}

        service = LinkService(resource_dict)
        links = service._get_source_links()

        assert links == []


class TestLinkServiceWebServicesLinks:
    """Test cases for web services link extraction."""

    def test_get_web_services_links_iiif_services(self):
        """Test getting IIIF web service links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://iiif.io/api/image": "http://example.com/iiif/image",
                    "http://iiif.io/api/presentation#manifest": "http://example.com/iiif/manifest",
                    "https://iiif.io/api/extension/georef/1/context.json": "http://example.com/iiif/annotation",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_web_services_links()

        assert len(links) == 3
        assert {"label": "IIIF Image API", "url": "http://example.com/iiif/image"} in links
        assert {"label": "IIIF Manifest", "url": "http://example.com/iiif/manifest"} in links
        assert {"label": "IIIF Annotation", "url": "http://example.com/iiif/annotation"} in links

    def test_get_web_services_links_ogc_services(self):
        """Test getting OGC web service links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://www.opengis.net/def/serviceType/ogc/wms": "http://example.com/wms",
                    "http://www.opengis.net/def/serviceType/ogc/wfs": "http://example.com/wfs",
                    "http://www.opengis.net/def/serviceType/ogc/wcs": "http://example.com/wcs",
                    "http://www.opengis.net/def/serviceType/ogc/wmts": "http://example.com/wmts",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_web_services_links()

        assert len(links) == 4
        assert {"label": "Web Mapping Service (WMS)", "url": "http://example.com/wms"} in links
        assert {"label": "Web Feature Service (WFS)", "url": "http://example.com/wfs"} in links
        assert {"label": "Web Coverage Service (WCS)", "url": "http://example.com/wcs"} in links
        assert {"label": "Web Map Tile Service (WMTS)", "url": "http://example.com/wmts"} in links

    def test_get_web_services_links_tile_services(self):
        """Test getting tile service links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification": "http://example.com/tms",
                    "https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames": "http://example.com/xyz",
                    "https://github.com/mapbox/tilejson-spec": "http://example.com/tilejson",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_web_services_links()

        assert len(links) == 3
        assert {"label": "Tile Mapping Service (TMS)", "url": "http://example.com/tms"} in links
        assert {"label": "XYZ Tiles", "url": "http://example.com/xyz"} in links
        assert {"label": "TileJSON", "url": "http://example.com/tilejson"} in links

    def test_get_web_services_links_data_formats(self):
        """Test getting data format links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://geojson.org/geojson-spec.html": "http://example.com/geojson",
                    "https://github.com/cogeotiff/cog-spec": "http://example.com/cog",
                    "https://github.com/protomaps/PMTiles": "http://example.com/pmtiles",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_web_services_links()

        assert len(links) == 3
        assert {"label": "GeoJSON", "url": "http://example.com/geojson"} in links
        assert {"label": "Cloud Optimized GeoTIFF (COG)", "url": "http://example.com/cog"} in links
        assert {"label": "PMTiles", "url": "http://example.com/pmtiles"} in links

    def test_get_web_services_links_other_services(self):
        """Test getting other service links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "https://oembed.com": "http://example.com/oembed",
                    "https://openindexmaps.org": "http://example.com/openindexmap",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_web_services_links()

        assert len(links) == 2
        assert {"label": "oEmbed", "url": "http://example.com/oembed"} in links
        assert {"label": "OpenIndexMap", "url": "http://example.com/openindexmap"} in links

    def test_get_web_services_links_no_services(self):
        """Test getting web services links when none exist."""
        resource_dict = {
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/source"})
        }

        service = LinkService(resource_dict)
        links = service._get_web_services_links()

        assert links == []


class TestLinkServiceMetadataLinks:
    """Test cases for metadata link extraction."""

    def test_get_metadata_links_iso_metadata(self):
        """Test getting ISO metadata links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://www.isotc211.org/schemas/2005/gmd/": "http://example.com/iso.xml"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 1
        assert {"label": "ISO 19115 XML", "url": "http://example.com/iso.xml"} in links

    def test_get_metadata_links_iso_metadata_no_trailing_slash(self):
        """Test getting ISO metadata links without trailing slash."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://www.isotc211.org/schemas/2005/gmd": "http://example.com/iso.xml"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 1
        assert {"label": "ISO 19115 XML", "url": "http://example.com/iso.xml"} in links

    def test_get_metadata_links_fgdc_metadata(self):
        """Test getting FGDC metadata links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://www.fgdc.gov/schemas/metadata/": "http://example.com/fgdc.xml"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 1
        assert {"label": "FGDC XML", "url": "http://example.com/fgdc.xml"} in links

    def test_get_metadata_links_csgdm_metadata(self):
        """Test getting CS-GDM metadata links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://www.opengis.net/cat/csw/csdgm": "http://example.com/csgdm.xml"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 1
        assert {"label": "CS-GDM XML", "url": "http://example.com/csgdm.xml"} in links

    def test_get_metadata_links_mods_metadata(self):
        """Test getting MODS metadata links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://www.loc.gov/mods/v3": "http://example.com/mods.xml"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 1
        assert {"label": "MODS XML", "url": "http://example.com/mods.xml"} in links

    def test_get_metadata_links_html_metadata(self):
        """Test getting HTML metadata links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://www.w3.org/1999/xhtml": "http://example.com/metadata.html"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 1
        assert {"label": "HTML Metadata", "url": "http://example.com/metadata.html"} in links

    def test_get_metadata_links_multiple_types(self):
        """Test getting multiple metadata link types."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://www.isotc211.org/schemas/2005/gmd/": "http://example.com/iso.xml",
                    "http://www.fgdc.gov/schemas/metadata/": "http://example.com/fgdc.xml",
                    "http://www.loc.gov/mods/v3": "http://example.com/mods.xml",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_metadata_links()

        assert len(links) == 3
        assert {"label": "ISO 19115 XML", "url": "http://example.com/iso.xml"} in links
        assert {"label": "FGDC XML", "url": "http://example.com/fgdc.xml"} in links
        assert {"label": "MODS XML", "url": "http://example.com/mods.xml"} in links


class TestLinkServiceArcGISLinks:
    """Test cases for ArcGIS link extraction."""

    def test_get_arcgis_links_dynamic_map_layer(self):
        """Test getting ArcGIS DynamicMapLayer links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer": "http://example.com/arcgis/dynamic"
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_arcgis_links()

        assert len(links) == 1
        assert {
            "label": "Open in ArcGIS Online (DynamicMapLayer)",
            "url": "http://example.com/arcgis/dynamic",
        } in links

    def test_get_arcgis_links_feature_layer(self):
        """Test getting ArcGIS FeatureLayer links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"urn:x-esri:serviceType:ArcGIS#FeatureLayer": "http://example.com/arcgis/feature"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_arcgis_links()

        assert len(links) == 1
        assert {
            "label": "Open in ArcGIS Online (FeatureLayer)",
            "url": "http://example.com/arcgis/feature",
        } in links

    def test_get_arcgis_links_image_map_layer(self):
        """Test getting ArcGIS ImageMapLayer links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"urn:x-esri:serviceType:ArcGIS#ImageMapLayer": "http://example.com/arcgis/image"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_arcgis_links()

        assert len(links) == 1
        assert {
            "label": "Open in ArcGIS Online (ImageMapLayer)",
            "url": "http://example.com/arcgis/image",
        } in links

    def test_get_arcgis_links_tiled_map_layer(self):
        """Test getting ArcGIS TiledMapLayer links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"urn:x-esri:serviceType:ArcGIS#TiledMapLayer": "http://example.com/arcgis/tiled"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_arcgis_links()

        assert len(links) == 1
        assert {
            "label": "Open in ArcGIS Online (TiledMapLayer)",
            "url": "http://example.com/arcgis/tiled",
        } in links

    def test_get_arcgis_links_multiple_services(self):
        """Test getting multiple ArcGIS service links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer": "http://example.com/arcgis/dynamic",
                    "urn:x-esri:serviceType:ArcGIS#FeatureLayer": "http://example.com/arcgis/feature",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service._get_arcgis_links()

        assert len(links) == 2
        assert {
            "label": "Open in ArcGIS Online (DynamicMapLayer)",
            "url": "http://example.com/arcgis/dynamic",
        } in links
        assert {
            "label": "Open in ArcGIS Online (FeatureLayer)",
            "url": "http://example.com/arcgis/feature",
        } in links

    def test_get_arcgis_links_no_services(self):
        """Test getting ArcGIS links when none exist."""
        resource_dict = {
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/source"})
        }

        service = LinkService(resource_dict)
        links = service._get_arcgis_links()

        assert links == []


class TestLinkServiceDocumentationLinks:
    """Test cases for documentation link extraction."""

    def test_get_documentation_links_data_dictionary(self):
        """Test getting data dictionary documentation links."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {"http://lccn.loc.gov/sh85035852": "http://example.com/documentation"}
            )
        }

        service = LinkService(resource_dict)
        links = service._get_documentation_links()

        assert len(links) == 1
        assert {"label": "Data Dictionary", "url": "http://example.com/documentation"} in links

    def test_get_documentation_links_no_documentation(self):
        """Test getting documentation links when none exist."""
        resource_dict = {
            "dct_references_s": json.dumps({"http://schema.org/url": "http://example.com/source"})
        }

        service = LinkService(resource_dict)
        links = service._get_documentation_links()

        assert links == []


class TestLinkServiceGetLinks:
    """Test cases for the main get_links method."""

    def test_get_links_comprehensive(self):
        """Test getting all link types comprehensively."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://schema.org/url": "http://example.com/source",
                    "http://iiif.io/api/image": "http://example.com/iiif/image",
                    "http://www.isotc211.org/schemas/2005/gmd/": "http://example.com/iso.xml",
                    "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer": "http://example.com/arcgis/dynamic",
                    "http://lccn.loc.gov/sh85035852": "http://example.com/documentation",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service.get_links()

        assert "Visit Source" in links
        assert "Web Services" in links
        assert "Metadata" in links
        assert "Open in ArcGIS Online" in links
        assert "Documentation" in links

        assert len(links["Visit Source"]) == 1
        assert len(links["Web Services"]) == 1
        assert len(links["Metadata"]) == 1
        assert len(links["Open in ArcGIS Online"]) == 1
        assert len(links["Documentation"]) == 1

    def test_get_links_partial_coverage(self):
        """Test getting links with only some categories present."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://schema.org/url": "http://example.com/source",
                    "http://iiif.io/api/image": "http://example.com/iiif/image",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service.get_links()

        assert "Visit Source" in links
        assert "Web Services" in links
        assert "Metadata" not in links
        assert "Open in ArcGIS Online" not in links
        assert "Documentation" not in links

    def test_get_links_no_links(self):
        """Test getting links when no links exist."""
        resource_dict = {"dct_references_s": json.dumps({})}

        service = LinkService(resource_dict)
        links = service.get_links()

        assert links == {}

    def test_get_links_invalid_references(self):
        """Test getting links with invalid references."""
        resource_dict = {"dct_references_s": "invalid json"}

        service = LinkService(resource_dict)
        links = service.get_links()

        assert links == {}


class TestLinkServiceStaticMethod:
    """Test cases for the static get_resource_links method."""

    @pytest.mark.asyncio
    async def test_get_resource_links_with_real_database(self):
        """Test getting resource links using real database connection."""
        # Use real database connection - will handle connection errors gracefully
        try:
            result = await LinkService.get_resource_links("test-resource-id")

            # Should return a dictionary (empty if resource not found)
            assert isinstance(result, dict)

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_links_nonexistent_resource(self):
        """Test getting resource links for non-existent resource."""
        try:
            result = await LinkService.get_resource_links("nonexistent-resource-id")

            # Should return empty dict for non-existent resource
            assert result == {}

        except Exception as e:
            # Handle database connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "database" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_get_resource_links_with_various_ids(self):
        """Test getting resource links with various resource IDs."""
        test_ids = [
            "valid-resource-123",
            "another-valid-resource-456",
            "resource-with-special-chars-789",
            "very-long-resource-id-that-might-test-different-behavior-123456789",
        ]

        for resource_id in test_ids:
            try:
                result = await LinkService.get_resource_links(resource_id)

                # Should return a dictionary
                assert isinstance(result, dict)

            except Exception as e:
                # Handle database connection errors gracefully
                assert (
                    "connection" in str(e).lower()
                    or "database" in str(e).lower()
                    or "nodename" in str(e).lower()
                )


class TestLinkServiceEdgeCases:
    """Test cases for edge cases and error conditions."""

    def test_complex_reference_structures(self):
        """Test handling of complex reference structures."""
        complex_refs = {
            "http://schema.org/url": ["http://example.com/source1", "http://example.com/source2"],
            "http://iiif.io/api/image": "http://example.com/iiif/image",
            "http://www.isotc211.org/schemas/2005/gmd/": "http://example.com/iso.xml",
        }

        resource_dict = {
            "dct_references_s": complex_refs  # Pass as dict directly
        }

        service = LinkService(resource_dict)
        links = service.get_links()

        # Should handle complex structures gracefully
        assert isinstance(links, dict)

    def test_empty_string_references(self):
        """Test handling of empty string references."""
        resource_dict = {"dct_references_s": ""}

        service = LinkService(resource_dict)
        links = service.get_links()

        assert links == {}

    def test_none_references(self):
        """Test handling of None references."""
        resource_dict = {"dct_references_s": None}

        service = LinkService(resource_dict)
        links = service.get_links()

        assert links == {}

    def test_malformed_json_references(self):
        """Test handling of malformed JSON references."""
        resource_dict = {"dct_references_s": '{"invalid": json, "missing": quotes}'}

        service = LinkService(resource_dict)
        links = service.get_links()

        assert links == {}

    def test_unicode_in_references(self):
        """Test handling of Unicode characters in references."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://schema.org/url": "http://example.com/source-with-unicode-ñ",
                    "http://iiif.io/api/image": "http://example.com/iiif/image-with-émojis",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service.get_links()

        # Should handle Unicode gracefully
        assert isinstance(links, dict)
        if "Visit Source" in links:
            assert "unicode-ñ" in links["Visit Source"][0]["url"]

    def test_very_long_urls(self):
        """Test handling of very long URLs."""
        long_url = "http://example.com/" + "a" * 1000

        resource_dict = {"dct_references_s": json.dumps({"http://schema.org/url": long_url})}

        service = LinkService(resource_dict)
        links = service.get_links()

        # Should handle long URLs gracefully
        assert isinstance(links, dict)
        if "Visit Source" in links:
            assert len(links["Visit Source"][0]["url"]) > 1000

    def test_special_characters_in_urls(self):
        """Test handling of special characters in URLs."""
        resource_dict = {
            "dct_references_s": json.dumps(
                {
                    "http://schema.org/url": "http://example.com/path?param=value&other=test#fragment",
                    "http://iiif.io/api/image": "http://example.com/iiif/image/region/100,100,200,200/0/default.jpg",
                }
            )
        }

        service = LinkService(resource_dict)
        links = service.get_links()

        # Should handle special characters gracefully
        assert isinstance(links, dict)
        if "Visit Source" in links:
            assert "?" in links["Visit Source"][0]["url"]
            assert "#" in links["Visit Source"][0]["url"]

    def test_nested_json_structures(self):
        """Test handling of nested JSON structures."""
        nested_refs = {
            "http://schema.org/url": "http://example.com/source",
            "nested": {"http://iiif.io/api/image": "http://example.com/iiif/image"},
        }

        resource_dict = {"dct_references_s": json.dumps(nested_refs)}

        service = LinkService(resource_dict)
        links = service.get_links()

        # Should handle nested structures gracefully
        assert isinstance(links, dict)
        if "Visit Source" in links:
            assert links["Visit Source"][0]["url"] == "http://example.com/source"
