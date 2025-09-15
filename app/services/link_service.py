import json
import logging
from typing import Any, Dict, List, Optional

from db.database import database

logger = logging.getLogger(__name__)


class LinkService:
    """Service for handling resource links."""

    def __init__(self, resource_dict: Dict[str, Any]):
        """
        Initialize the link service with resource data.

        Args:
            resource_dict: The resource data from the database
        """
        self.resource_dict = resource_dict

    def get_links(self) -> Dict[str, List[Dict[str, str]]]:
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

        # Add "Open in ArcGIS Online" links
        arcgis_links = self._get_arcgis_links()
        if arcgis_links:
            links["Open in ArcGIS Online"] = arcgis_links

        # Add "Documentation" links
        documentation_links = self._get_documentation_links()
        if documentation_links:
            links["Documentation"] = documentation_links

        return links

    def _get_source_links(self) -> List[Dict[str, str]]:
        """
        Get the "Visit Source" links from dct_references_s.

        Returns:
            List of link dictionaries with 'label' and 'url' keys
        """
        links = []
        try:
            references = self._parse_references()
            source_url = references.get("http://schema.org/url")
            
            if source_url:
                links.append({
                    "label": "Visit Source",
                    "url": source_url
                })
        except Exception as e:
            logger.error(f"Error getting source links: {e}", exc_info=True)
        
        return links

    def _get_web_services_links(self) -> List[Dict[str, str]]:
        """
        Get the "Web Services" links from dct_references_s for various web services.

        Returns:
            List of link dictionaries with 'label' and 'url' keys
        """
        links = []
        try:
            references = self._parse_references()
            
            # IIIF Image API
            iiif_url = references.get("http://iiif.io/api/image")
            if iiif_url:
                links.append({
                    "label": "IIIF Image API",
                    "url": iiif_url
                })
            
            # IIIF Presentation API
            iiif_manifest_url = references.get("http://iiif.io/api/presentation#manifest")
            if iiif_manifest_url:
                links.append({
                    "label": "IIIF Manifest",
                    "url": iiif_manifest_url
                })
            
            # IIIF Annotation
            iiif_annotation_url = references.get("https://iiif.io/api/extension/georef/1/context.json")
            if iiif_annotation_url:
                links.append({
                    "label": "IIIF Annotation",
                    "url": iiif_annotation_url
                })
            
            
            # OGC Services
            wms_url = references.get("http://www.opengis.net/def/serviceType/ogc/wms")
            if wms_url:
                links.append({
                    "label": "Web Mapping Service (WMS)",
                    "url": wms_url
                })
            
            wfs_url = references.get("http://www.opengis.net/def/serviceType/ogc/wfs")
            if wfs_url:
                links.append({
                    "label": "Web Feature Service (WFS)",
                    "url": wfs_url
                })
            
            wcs_url = references.get("http://www.opengis.net/def/serviceType/ogc/wcs")
            if wcs_url:
                links.append({
                    "label": "Web Coverage Service (WCS)",
                    "url": wcs_url
                })
            
            wmts_url = references.get("http://www.opengis.net/def/serviceType/ogc/wmts")
            if wmts_url:
                links.append({
                    "label": "Web Map Tile Service (WMTS)",
                    "url": wmts_url
                })
            
            # Tile Services
            tms_url = references.get("https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification")
            if tms_url:
                links.append({
                    "label": "Tile Mapping Service (TMS)",
                    "url": tms_url
                })
            
            xyz_url = references.get("https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames")
            if xyz_url:
                links.append({
                    "label": "XYZ Tiles",
                    "url": xyz_url
                })
            
            tilejson_url = references.get("https://github.com/mapbox/tilejson-spec")
            if tilejson_url:
                links.append({
                    "label": "TileJSON",
                    "url": tilejson_url
                })
            
            # Data Formats
            geojson_url = references.get("http://geojson.org/geojson-spec.html")
            if geojson_url:
                links.append({
                    "label": "GeoJSON",
                    "url": geojson_url
                })
            
            cog_url = references.get("https://github.com/cogeotiff/cog-spec")
            if cog_url:
                links.append({
                    "label": "Cloud Optimized GeoTIFF (COG)",
                    "url": cog_url
                })
            
            pmtiles_url = references.get("https://github.com/protomaps/PMTiles")
            if pmtiles_url:
                links.append({
                    "label": "PMTiles",
                    "url": pmtiles_url
                })
            
            # Other Services
            oembed_url = references.get("https://oembed.com")
            if oembed_url:
                links.append({
                    "label": "oEmbed",
                    "url": oembed_url
                })
            
            openindexmap_url = references.get("https://openindexmaps.org")
            if openindexmap_url:
                links.append({
                    "label": "OpenIndexMap",
                    "url": openindexmap_url
                })
                
        except Exception as e:
            logger.error(f"Error getting web services links: {e}", exc_info=True)
        
        return links

    def _get_metadata_links(self) -> List[Dict[str, str]]:
        """
        Get the "Metadata" links from dct_references_s for FGDC and ISO XML.

        Returns:
            List of link dictionaries with 'label' and 'url' keys
        """
        links = []
        try:
            references = self._parse_references()
            
            # ISO 19115 metadata (try both with and without trailing slash)
            iso_url = references.get("http://www.isotc211.org/schemas/2005/gmd/") or references.get("http://www.isotc211.org/schemas/2005/gmd")
            if iso_url:
                links.append({
                    "label": "ISO 19115 XML",
                    "url": iso_url
                })
            
            # FGDC metadata (if it exists)
            fgdc_url = references.get("http://www.fgdc.gov/schemas/metadata/")
            if fgdc_url:
                links.append({
                    "label": "FGDC XML",
                    "url": fgdc_url
                })
 
            # CS-GDM metadata (if it exists)
            csgdm_url = references.get("http://www.opengis.net/cat/csw/csdgm")
            if csgdm_url:
                links.append({
                    "label": "CS-GDM XML",
                    "url": csgdm_url
                })
            
            # MODS metadata (if it exists)
            mods_url = references.get("http://www.loc.gov/mods/v3")
            if mods_url:
                links.append({
                    "label": "MODS XML",
                    "url": mods_url
                })
            
            # HTML metadata (if it exists)
            html_metadata_url = references.get("http://www.w3.org/1999/xhtml")
            if html_metadata_url:
                links.append({
                    "label": "HTML Metadata",
                    "url": html_metadata_url
                })
                
        except Exception as e:
            logger.error(f"Error getting metadata links: {e}", exc_info=True)
        
        return links

    def _get_arcgis_links(self) -> List[Dict[str, str]]:
        """
        Get the "Open in ArcGIS Online" links from dct_references_s.

        Returns:
            List of link dictionaries with 'label' and 'url' keys
        """
        links = []
        try:
            references = self._parse_references()
            
            # Look for ArcGIS service types
            arcgis_service_types = [
                "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer",
                "urn:x-esri:serviceType:ArcGIS#FeatureLayer", 
                "urn:x-esri:serviceType:ArcGIS#ImageMapLayer",
                "urn:x-esri:serviceType:ArcGIS#TiledMapLayer"
            ]
            
            for service_type in arcgis_service_types:
                arcgis_url = references.get(service_type)
                if arcgis_url:
                    # Extract the service type name for a cleaner label
                    service_name = service_type.split("#")[-1] if "#" in service_type else service_type
                    links.append({
                        "label": f"Open in ArcGIS Online ({service_name})",
                        "url": arcgis_url
                    })
                
        except Exception as e:
            logger.error(f"Error getting ArcGIS links: {e}", exc_info=True)
        
        return links


    def _get_documentation_links(self) -> List[Dict[str, str]]:
        """
        Get the "Documentation" links from dct_references_s.

        Returns:
            List of link dictionaries with 'label' and 'url' keys
        """
        links = []
        try:
            references = self._parse_references()
            
            # Data dictionary / supplemental documentation
            documentation_url = references.get("http://lccn.loc.gov/sh85035852")
            if documentation_url:
                links.append({
                    "label": "Data Dictionary",
                    "url": documentation_url
                })
                
        except Exception as e:
            logger.error(f"Error getting documentation links: {e}", exc_info=True)
        
        return links

    def _parse_references(self) -> Dict[str, Any]:
        """
        Parse the dct_references_s field from the resource.

        Returns:
            Dictionary of parsed references
        """
        try:
            refs = self.resource_dict.get("dct_references_s", {})

            # If refs is a string, try to parse it as JSON
            if isinstance(refs, str):
                try:
                    refs = json.loads(refs)
                except json.JSONDecodeError:
                    refs = {}
            elif not isinstance(refs, dict):
                refs = {}

            return refs
        except Exception as e:
            logger.error(f"Error parsing references: {e}", exc_info=True)
            return {}

    @staticmethod
    async def get_resource_links(resource_id: str) -> Dict[str, List[Dict[str, str]]]:
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
                SELECT id, dct_title_s, dct_references_s
                FROM resources
                WHERE id = :resource_id
            """
            resource = await database.fetch_one(resource_query, {"resource_id": resource_id})
            
            if not resource:
                logger.warning(f"Resource {resource_id} not found")
                return {}
            
            # Create LinkService instance and get links
            link_service = LinkService(dict(resource))
            return link_service.get_links()
            
        except Exception as e:
            logger.error(f"Error getting resource links for {resource_id}: {e}", exc_info=True)
            return {}
