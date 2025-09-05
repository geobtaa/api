import json
import re
from typing import Dict, List, Optional, TypedDict, Union


class Reference(TypedDict):
    protocol: str
    endpoint: str


class GeoJSON(TypedDict):
    type: str
    coordinates: Union[List[List[List[float]]], List[float]]


class ItemViewer:
    REFERENCE_URI_TO_NAME = {
        "urn:x-esri:serviceType:ArcGIS#DynamicMapLayer": "arcgis_dynamic_map_layer",
        "urn:x-esri:serviceType:ArcGIS#FeatureLayer": "arcgis_feature_layer",
        "urn:x-esri:serviceType:ArcGIS#ImageMapLayer": "arcgis_image_map_layer",
        "urn:x-esri:serviceType:ArcGIS#TiledMapLayer": "arcgis_tiled_map_layer",
        "https://github.com/cogeotiff/cog-spec": "cog",
        "http://lccn.loc.gov/sh85035852": "documentation_download",
        "http://schema.org/url": "documentation_external",
        "http://schema.org/downloadUrl": "download",
        "http://geojson.org/geojson-spec.html": "geo_json",
        "http://iiif.io/api/image": "iiif_image",
        "http://iiif.io/api/presentation#manifest": "iiif_manifest",
        "http://schema.org/image": "image",
        "http://www.opengis.net/cat/csw/csdgm": "metadata_fgdc",
        "http://www.w3.org/1999/xhtml": "metadata_html",
        "http://www.isotc211.org/schemas/2005/gmd/": "metadata_iso",
        "http://www.loc.gov/mods/v3": "metadata_mods",
        "https://oembed.com": "oembed",
        "https://openindexmaps.org": "open_index_map",
        "https://github.com/protomaps/PMTiles": "pmtiles",
        "http://schema.org/thumbnailUrl": "thumbnail",
        "https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification": "tile_map_service",
        "https://github.com/mapbox/tilejson-spec": "tile_json",
        "http://www.opengis.net/def/serviceType/ogc/wcs": "wcs",
        "http://www.opengis.net/def/serviceType/ogc/wfs": "wfs",
        "http://www.opengis.net/def/serviceType/ogc/wmts": "wmts",
        "http://www.opengis.net/def/serviceType/ogc/wms": "wms",
        "https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames": "xyz_tiles",
    }

    # LIGHTNING SPEED OPTIMIZATION: Class-level geometry cache
    # This avoids re-processing identical geometry strings across different resources
    _geometry_cache = {}
    _cache_hits = 0
    _cache_misses = 0

    def __init__(self, references: Dict[str, str]):
        self.references = references

    def viewer_protocol(self) -> Optional[str]:
        preference = self._viewer_preference()
        return self.REFERENCE_URI_TO_NAME.get(preference["protocol"]) if preference else "geo_json"

    def viewer_endpoint(self) -> str:
        preference = self._viewer_preference()
        return preference["endpoint"] if preference else ""

    def _viewer_preference(self) -> Optional[Reference]:
        preferences = [
            self._get_reference("https://github.com/cogeotiff/cog-spec"),
            self._get_reference("https://github.com/protomaps/PMTiles"),
            self._get_reference("https://oembed.com"),
            self._get_reference("https://openindexmaps.org"),
            self._get_reference("https://github.com/mapbox/tilejson-spec"),
            self._get_reference("https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames"),
            self._get_reference("http://www.opengis.net/def/serviceType/ogc/wmts"),
            self._get_reference("https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification"),
            self._get_reference("http://www.opengis.net/def/serviceType/ogc/wms"),
            self._get_reference("http://iiif.io/api/presentation#manifest"),
            self._get_reference("http://iiif.io/api/image"),
            self._get_reference("urn:x-esri:serviceType:ArcGIS#TiledMapLayer"),
            self._get_reference("urn:x-esri:serviceType:ArcGIS#DynamicMapLayer"),
            self._get_reference("urn:x-esri:serviceType:ArcGIS#ImageMapLayer"),
            self._get_reference("urn:x-esri:serviceType:ArcGIS#FeatureLayer"),
        ]
        return next((pref for pref in preferences if pref is not None), None)

    def _get_reference(self, protocol: str) -> Optional[Reference]:
        endpoint = self.references.get(protocol)
        return {"protocol": protocol, "endpoint": endpoint} if endpoint else None

    def viewer_geometry(self) -> Optional[GeoJSON]:
        """Convert locn_geometry to a GeoJSON object."""
        if not self.references.get("locn_geometry"):
            return None

        geometry = self.references["locn_geometry"]

        # LIGHTNING SPEED OPTIMIZATION: Check cache first
        # Many resources share identical geometry strings - avoid re-processing
        if geometry in self._geometry_cache:
            self._cache_hits += 1
            return self._geometry_cache[geometry]

        self._cache_misses += 1

        # If geometry is already a dictionary, return it if it's valid GeoJSON
        if isinstance(geometry, dict):
            if "type" in geometry and "coordinates" in geometry:
                # Ensure type is properly capitalized
                geometry["type"] = geometry["type"].capitalize()
                # LIGHTNING SPEED OPTIMIZATION: Cache the result
                self._geometry_cache[self.references["locn_geometry"]] = geometry
                return geometry
            return None

        # If geometry is a string, try to parse it
        if not isinstance(geometry, str):
            return None

        # LIGHTNING SPEED OPTIMIZATION: Pre-compile regex patterns for reuse
        # This eliminates the overhead of recompiling patterns on every call
        if not hasattr(self, "_envelope_pattern"):
            self._envelope_pattern = re.compile(
                r"ENVELOPE\(([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\)"
            )
            self._polygon_pattern = re.compile(r"POLYGON\(\(\s*([-\d.\s,]+)\s*\)\)")

        # Check if it's an ENVELOPE format using pre-compiled pattern
        envelope_match = self._envelope_pattern.match(geometry)
        if envelope_match:
            # Extract coordinates from ENVELOPE(minx,maxx,maxy,miny)
            minx, maxx, maxy, miny = map(float, envelope_match.groups())
            # Create a polygon from the envelope coordinates
            result = {
                "type": "Polygon",  # Ensure proper capitalization
                "coordinates": [
                    [
                        [minx, maxy],  # top left
                        [minx, miny],  # bottom left
                        [maxx, miny],  # bottom right
                        [maxx, maxy],  # top right
                        [minx, maxy],  # close the polygon
                    ]
                ],
            }
            # LIGHTNING SPEED OPTIMIZATION: Cache the result
            self._geometry_cache[geometry] = result
            return result

        # Check if it's a POLYGON format using pre-compiled pattern
        polygon_match = self._polygon_pattern.match(geometry)
        if polygon_match:
            # Extract coordinates from POLYGON((x1 y1, x2 y2, ..., xn yn))
            coordinates_str = polygon_match.group(1)
            # Split the coordinates and convert them to float pairs
            coordinates = [list(map(float, coord.split())) for coord in coordinates_str.split(",")]
            # Ensure the polygon is closed by repeating the first point at the end
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            result = {
                "type": "Polygon",
                "coordinates": [coordinates],
            }  # Ensure proper capitalization
            # LIGHTNING SPEED OPTIMIZATION: Cache the result
            self._geometry_cache[geometry] = result
            return result

        # Try parsing as JSON (handling escaped quotes)
        try:
            # Replace escaped quotes and parse
            clean_geometry = geometry.replace("&quot;", '"')
            geojson = json.loads(clean_geometry)
            if isinstance(geojson, dict) and "type" in geojson:
                geojson["type"] = geojson["type"].capitalize()

            # LIGHTNING SPEED OPTIMIZATION: Cache the result
            self._geometry_cache[geometry] = geojson
            return geojson
        except json.JSONDecodeError:
            # Cache None results too to avoid re-trying failed parses
            self._geometry_cache[geometry] = None
            return None

    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """Get cache statistics for monitoring performance."""
        return {
            "cache_size": len(cls._geometry_cache),
            "cache_hits": cls._cache_hits,
            "cache_misses": cls._cache_misses,
            "hit_rate": cls._cache_hits / (cls._cache_hits + cls._cache_misses)
            if (cls._cache_hits + cls._cache_misses) > 0
            else 0,
        }
