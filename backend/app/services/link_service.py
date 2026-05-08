import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
    fetch_distribution_context,
)
from db.database import database

logger = logging.getLogger(__name__)
BBOX_ENVELOPE_RE = re.compile(
    r"ENVELOPE\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)",
    re.IGNORECASE,
)


class LinkService:
    """Service for handling resource links."""

    def __init__(
        self,
        resource_dict: Dict[str, Any],
        distribution_context: Optional[DistributionContext] = None,
    ):
        """
        Initialize the link service with resource data.

        Args:
            resource_dict: The resource data from the database
        """
        self.resource_dict = resource_dict
        if distribution_context is None:
            distribution_context = build_distribution_context(resource_dict.get("id", ""), [])
        self.distribution_context = distribution_context
        self.by_uri = distribution_context.by_uri
        self._legacy_refs_cache: Optional[Dict[str, Any]] = None

    def get_links(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all links for a resource organized by category.

        Returns:
            Dictionary with category names as keys and arrays of link objects as values
        """
        links = {}

        # Add "Visit Source" links
        source_links = self._get_source_links()
        if source_links:
            links["Visit Source"] = source_links

        # Add "Web Services" links
        web_services_links = self._get_web_services_links()
        if web_services_links:
            links["Web Services"] = web_services_links

        # Add "Metadata" links
        metadata_links = self._get_metadata_links()
        if metadata_links:
            links["Metadata"] = metadata_links

        # Add "Open in ArcGIS" links
        arcgis_links = self._get_arcgis_links()
        if arcgis_links:
            links["Open in ArcGIS"] = arcgis_links

        # Add "Documentation" links
        documentation_links = self._get_documentation_links()
        if documentation_links:
            links["Documentation"] = documentation_links

        return links

    def _get_source_links(self) -> List[Dict[str, str]]:
        """Get the “Visit Source” links derived from resource distributions."""
        links = []
        try:
            references = self._parse_references()
            source_url = references.get("http://schema.org/url")

            if source_url:
                links.append({"label": "Visit Source", "url": source_url})
        except Exception as e:
            logger.error(f"Error getting source links: {e}", exc_info=True)

        return links

    def _get_web_services_links(self) -> List[Dict[str, Any]]:
        """Get the “Web Services” links derived from resource distributions."""
        links = []
        try:
            if iiif_url := self._first_url("http://iiif.io/api/image"):
                links.append({"label": "IIIF Image API", "url": iiif_url})

            # IIIF Presentation API
            if iiif_manifest_url := self._first_url("http://iiif.io/api/presentation#manifest"):
                links.append({"label": "IIIF Manifest", "url": iiif_manifest_url})

            # IIIF Annotation
            if iiif_annotation_url := self._first_url(
                "https://iiif.io/api/extension/georef/1/context.json"
            ):
                links.append({"label": "IIIF Annotation", "url": iiif_annotation_url})

            # OGC Services
            service_map = {
                "http://www.opengis.net/def/serviceType/ogc/wms": (
                    "Web Mapping Service (WMS)",
                    "WMS",
                ),
                "http://www.opengis.net/def/serviceType/ogc/wfs": (
                    "Web Feature Service (WFS)",
                    "WFS",
                ),
                "http://www.opengis.net/def/serviceType/ogc/wcs": (
                    "Web Coverage Service (WCS)",
                    "WCS",
                ),
                "http://www.opengis.net/def/serviceType/ogc/wmts": (
                    "Web Map Tile Service (WMTS)",
                    "WMTS",
                ),
            }
            for uri, (label, service_type) in service_map.items():
                if url := self._first_url(uri):
                    links.append(
                        self._web_service_link(
                            label,
                            url,
                            service_type=service_type,
                            include_wxs_identifier=True,
                        )
                    )

            # Tile Services
            tile_map = {
                "https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification": (
                    "Tile Mapping Service (TMS)"
                ),
                "https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames": "XYZ Tiles",
                "https://github.com/mapbox/tilejson-spec": "TileJSON",
            }
            for uri, label in tile_map.items():
                if url := self._first_url(uri):
                    links.append({"label": label, "url": url})

            # Data Formats
            data_formats = {
                "http://geojson.org/geojson-spec.html": "GeoJSON",
                "https://github.com/cogeotiff/cog-spec": "Cloud Optimized GeoTIFF (COG)",
                "https://github.com/protomaps/PMTiles": "PMTiles",
            }
            for uri, label in data_formats.items():
                if url := self._first_url(uri):
                    links.append({"label": label, "url": url})

            # Other Services
            if oembed_url := self._first_url("https://oembed.com"):
                links.append({"label": "oEmbed", "url": oembed_url})

            if openindexmap_url := self._first_url("https://openindexmaps.org"):
                links.append({"label": "OpenIndexMap", "url": openindexmap_url})

        except Exception as e:
            logger.error(f"Error getting web services links: {e}", exc_info=True)

        return links

    def _get_metadata_links(self) -> List[Dict[str, Any]]:
        """Get the “Metadata” links derived from resource distributions.
        Each link includes 'label', 'url', and optionally 'format' (iso, fgdc, html)
        for transformable types.
        """
        links = []
        try:
            # (uri, label, format for display endpoint or None)
            metadata_map = [
                ("http://www.isotc211.org/schemas/2005/gmd/", "ISO 19115 XML", "iso"),
                ("http://www.isotc211.org/schemas/2005/gmd", "ISO 19115 XML", "iso"),
                ("http://www.fgdc.gov/schemas/metadata/", "FGDC XML", "fgdc"),
                ("http://www.opengis.net/cat/csw/csdgm", "CS-GDM XML", "fgdc"),
                ("http://www.loc.gov/mods/v3", "MODS XML", None),
                ("http://www.w3.org/1999/xhtml", "HTML Metadata", "html"),
            ]
            seen_labels = set()
            for uri, label, fmt in metadata_map:
                if label in seen_labels:
                    continue
                if url := self._first_url(uri):
                    link: Dict[str, Any] = {"label": label, "url": url}
                    if fmt is not None:
                        link["format"] = fmt
                    links.append(link)
                    seen_labels.add(label)

        except Exception as e:
            logger.error(f"Error getting metadata links: {e}", exc_info=True)

        return links

    def _get_arcgis_links(self) -> List[Dict[str, str]]:
        """Get the “Open in ArcGIS” links derived from resource distributions."""
        links = []
        try:
            arcgis_service_types = {
                "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer": "DynamicMapLayer",
                "urn:x-esri:serviceType:ArcGIS#FeatureLayer": "FeatureLayer",
                "urn:x-esri:serviceType:ArcGIS#ImageMapLayer": "ImageMapLayer",
                "urn:x-esri:serviceType:ArcGIS#TiledMapLayer": "TiledMapLayer",
            }

            available_services = []
            for service_type, service_name in arcgis_service_types.items():
                arcgis_url = self._first_url(service_type)
                if arcgis_url:
                    available_services.append((service_name, arcgis_url))

            multiple_services = len(available_services) > 1
            for service_name, arcgis_url in available_services:
                label_suffix = f" ({service_name})" if multiple_services else ""
                links.append(
                    {
                        "label": f"MapViewer{label_suffix}",
                        "url": self._build_arcgis_mapviewer_url(arcgis_url),
                    }
                )
                links.append({"label": f"REST Service Details{label_suffix}", "url": arcgis_url})

        except Exception as e:
            logger.error(f"Error getting ArcGIS links: {e}", exc_info=True)

        return links

    @staticmethod
    def _build_arcgis_mapviewer_url(arcgis_url: str) -> str:
        encoded_url = quote(arcgis_url, safe="")
        return f"https://www.arcgis.com/home/webmap/viewer.html?urls={encoded_url}"

    def _get_documentation_links(self) -> List[Dict[str, str]]:
        """Get the “Documentation” links derived from resource distributions."""
        links = []
        try:
            documentation_url = self._first_url("http://lccn.loc.gov/sh85035852")
            if documentation_url:
                links.append({"label": "Data Dictionary", "url": documentation_url})

        except Exception as e:
            logger.error(f"Error getting documentation links: {e}", exc_info=True)

        return links

    @staticmethod
    async def get_resource_links(resource_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all links for a resource by its ID organized by category.

        Args:
            resource_id: The ID of the resource

        Returns:
            Dictionary with category names as keys and arrays of link objects as values
        """
        try:
            # Fetch the resource from the database
            resource_query = """
                SELECT id, dct_title_s, dct_references_s, "gbl_wxsIdentifier_s", dcat_bbox
                FROM resources
                WHERE id = :resource_id
            """
            resource = await database.fetch_one(resource_query, {"resource_id": resource_id})

            if not resource:
                logger.warning(f"Resource {resource_id} not found")
                return {}

            # Create LinkService instance and get links
            distribution_context = await fetch_distribution_context(resource_id)
            link_service = LinkService(dict(resource), distribution_context=distribution_context)
            return link_service.get_links()

        except Exception as e:
            logger.error(f"Error getting resource links for {resource_id}: {e}", exc_info=True)
            return {}

    def _web_service_link(
        self,
        label: str,
        url: str,
        *,
        service_type: Optional[str] = None,
        include_wxs_identifier: bool = False,
    ) -> Dict[str, Any]:
        link: Dict[str, Any] = {"label": label, "url": url}
        wxs_identifier = None
        if include_wxs_identifier:
            wxs_identifier = self._wxs_identifier()
            if wxs_identifier:
                link["wxs_identifier"] = wxs_identifier
        if wxs_identifier and service_type:
            request = self._ogc_layer_request(
                url,
                service_type=service_type,
                wxs_identifier=wxs_identifier,
            )
            if request:
                link.update(request)
        return link

    def _ogc_layer_request(
        self,
        service_url: str,
        *,
        service_type: str,
        wxs_identifier: str,
    ) -> Optional[Dict[str, str]]:
        service_type = service_type.upper()
        if service_type == "WMS":
            bbox = self._wms_bbox()
            if not bbox:
                return None
            request_url = self._url_with_query(
                service_url,
                {
                    "SERVICE": "WMS",
                    "VERSION": "1.1.1",
                    "REQUEST": "GetMap",
                    "LAYERS": wxs_identifier,
                    "STYLES": "",
                    "BBOX": bbox,
                    "WIDTH": "1024",
                    "HEIGHT": "768",
                    "SRS": "EPSG:4326",
                    "FORMAT": "image/png",
                    "TRANSPARENT": "true",
                    "EXCEPTIONS": "application/vnd.ogc.se_inimage",
                },
            )
            return {"request_url": request_url, "request_label": "Open map preview"}
        if service_type == "WFS":
            request_url = self._url_with_query(
                service_url,
                {
                    "SERVICE": "WFS",
                    "VERSION": "1.1.0",
                    "REQUEST": "DescribeFeatureType",
                    "TYPENAME": wxs_identifier,
                },
            )
            return {"request_url": request_url, "request_label": "Open layer schema"}
        if service_type == "WCS":
            request_url = self._url_with_query(
                service_url,
                {
                    "SERVICE": "WCS",
                    "VERSION": "2.0.1",
                    "REQUEST": "DescribeCoverage",
                    "COVERAGEID": wxs_identifier,
                },
            )
            return {"request_url": request_url, "request_label": "Open coverage description"}
        return None

    @staticmethod
    def _url_with_query(url: str, params: Dict[str, str]) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update(params)
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

    def _wms_bbox(self) -> Optional[str]:
        bbox = self.resource_dict.get("dcat_bbox")
        if not isinstance(bbox, str):
            return None
        match = BBOX_ENVELOPE_RE.search(bbox)
        if match:
            try:
                min_x, max_x, max_y, min_y = (float(value.strip()) for value in match.groups())
            except ValueError:
                return None
            return f"{min_x:g},{min_y:g},{max_x:g},{max_y:g}"

        parts = [part.strip() for part in bbox.split(",")]
        if len(parts) != 4:
            return None
        try:
            min_x, min_y, max_x, max_y = (float(value) for value in parts)
        except ValueError:
            return None
        return f"{min_x:g},{min_y:g},{max_x:g},{max_y:g}"

    def _wxs_identifier(self) -> Optional[str]:
        for key in ("gbl_wxsIdentifier_s", "gbl_wxsidentifier_s"):
            value = self.resource_dict.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        return item.strip()
        return None

    def _first_url(self, uri: str) -> Optional[str]:
        # Prefer distribution context if available
        records = self.by_uri.get(uri, [])
        if records:
            return records[0].url
        # Fallback to legacy references on the resource_dict
        refs = self._parse_references()
        val = refs.get(uri)
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return val.get("url")
        return None

    def _parse_references(self) -> Dict[str, Any]:
        """
        Backwards compatibility helper for legacy logic not yet refactored.
        Uses distribution context when available, falling back to dct_references_s.
        """
        if self._legacy_refs_cache is not None:
            return self._legacy_refs_cache

        # Use distribution context first
        references: Dict[str, Any] = {}
        for uri, records in self.by_uri.items():
            if records:
                references[uri] = records[0].url

        # Fallback to the legacy field if we didn't find anything
        if not references:
            raw_refs = self.resource_dict.get("dct_references_s")
            if isinstance(raw_refs, str):
                try:
                    import json

                    raw_refs = json.loads(raw_refs)
                except Exception:
                    raw_refs = None
            if isinstance(raw_refs, dict):
                # Coerce mixed values to simple URLs where possible
                coerced: Dict[str, Any] = {}
                for uri, value in raw_refs.items():
                    if isinstance(value, str):
                        coerced[uri] = value
                    elif isinstance(value, dict):
                        url = value.get("url") or value.get("@id") or value.get("id")
                        if url:
                            coerced[uri] = url
                references = coerced

        self._legacy_refs_cache = references
        return references
