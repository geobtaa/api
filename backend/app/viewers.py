import json
import logging
from typing import Dict, List, Optional, TypedDict, Union

logger = logging.getLogger(__name__)


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

    def _parse_polygon_coords(
        self, coordinates_str: str, geometry: str
    ) -> Optional[Dict[str, Union[str, List]]]:
        """Parse WKT polygon coordinate string to GeoJSON Polygon."""
        coordinates = [list(map(float, coord.split())) for coord in coordinates_str.split(",")]
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        from app.elasticsearch.index import _is_valid_single_polygon

        if not _is_valid_single_polygon([coordinates]):
            logger.warning(f"Invalid polygon coordinates in viewer: {geometry} - skipping")
            return None
        return {"type": "Polygon", "coordinates": [coordinates]}

    @staticmethod
    def _unwrap_wkt(geometry: str, prefix: str, layers: int = 1) -> Optional[str]:
        stripped = geometry.strip()
        if not stripped[: len(prefix)].upper() == prefix.upper():
            return None

        remainder = stripped[len(prefix) :].strip()
        for _ in range(layers):
            if not remainder.startswith("(") or not remainder.endswith(")"):
                return None
            remainder = remainder[1:-1].strip()
        return remainder

    @staticmethod
    def _extract_double_parenthesized_segments(value: str) -> List[str]:
        segments: List[str] = []
        depth = 0
        segment_start: Optional[int] = None

        for index, char in enumerate(value):
            if char == "(":
                depth += 1
                if depth == 2:
                    segment_start = index + 1
            elif char == ")":
                if depth == 2 and segment_start is not None:
                    segments.append(value[segment_start:index].strip())
                    segment_start = None
                depth -= 1
                if depth < 0:
                    return []

        return segments if depth == 0 else []

    def _parse_multipolygon_wkt(self, geometry: str) -> Optional[Dict[str, Union[str, List]]]:
        """Parse MultiPolygon WKT to GeoJSON MultiPolygon, preserving all polygons."""
        inner = self._unwrap_wkt(geometry, "MULTIPOLYGON")
        if inner is None:
            return None

        ring_matches = self._extract_double_parenthesized_segments(inner)
        if not ring_matches:
            return None

        polygons = []
        from app.elasticsearch.index import _is_valid_single_polygon

        for coords_str in ring_matches:
            ring = [list(map(float, coord.split())) for coord in coords_str.split(",")]
            if len(ring) < 3:
                continue
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            if not _is_valid_single_polygon([ring]):
                logger.warning(f"Invalid ring in MultiPolygon: {geometry[:80]}... - skipping")
                continue
            polygons.append([ring])
        if not polygons:
            return None
        return {"type": "MultiPolygon", "coordinates": polygons}

    @staticmethod
    def _viewer_geometry_from_envelope(
        minx: float, maxx: float, maxy: float, miny: float
    ) -> Optional[GeoJSON]:
        """Normalize an envelope and return consistently ordered viewer GeoJSON."""
        from app.elasticsearch.index import _normalize_envelope

        normalized_geom, error_msg = _normalize_envelope(minx, maxx, maxy, miny)
        if normalized_geom is None:
            logger.error(
                "Invalid viewer envelope (%s, %s, %s, %s): %s - skipping",
                minx,
                maxx,
                maxy,
                miny,
                error_msg,
            )
            return None

        if normalized_geom["type"] != "polygon":
            return {"type": "Point", "coordinates": normalized_geom["coordinates"]}

        ring = normalized_geom["coordinates"][0]
        xs = [point[0] for point in ring]
        ys = [point[1] for point in ring]
        normalized_minx, normalized_maxx = min(xs), max(xs)
        normalized_miny, normalized_maxy = min(ys), max(ys)
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [normalized_minx, normalized_maxy],
                    [normalized_minx, normalized_miny],
                    [normalized_maxx, normalized_miny],
                    [normalized_maxx, normalized_maxy],
                    [normalized_minx, normalized_maxy],
                ]
            ],
        }

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

        envelope_inner = self._unwrap_wkt(geometry, "ENVELOPE")
        if envelope_inner is not None:
            parts = [part.strip() for part in envelope_inner.split(",")]
            if len(parts) != 4:
                return None

            # Extract coordinates from ENVELOPE(minx,maxx,maxy,miny)
            try:
                minx, maxx, maxy, miny = map(float, parts)
            except ValueError:
                return None

            result = self._viewer_geometry_from_envelope(minx, maxx, maxy, miny)
            if result is None:
                return None

            # Cache the result for performance
            self._geometry_cache[geometry] = result
            return result

        point_inner = self._unwrap_wkt(geometry, "POINT")
        if point_inner is not None:
            try:
                coordinates = [float(value) for value in point_inner.split()]
            except ValueError:
                return None

            from app.elasticsearch.index import _is_valid_point

            if len(coordinates) < 2 or not _is_valid_point(coordinates):
                logger.warning(f"Invalid point coordinates in viewer: {geometry} - skipping")
                return None

            result = {"type": "Point", "coordinates": coordinates[:2]}
            self._geometry_cache[geometry] = result
            return result

        # The bridge stores dcat_bbox as minx,miny,maxx,maxy. Bbox-only
        # records use this path after parse_references aliases it as geometry.
        bbox_parts = [part.strip() for part in geometry.split(",")]
        if len(bbox_parts) == 4:
            try:
                minx, miny, maxx, maxy = map(float, bbox_parts)
            except ValueError:
                pass
            else:
                result = self._viewer_geometry_from_envelope(minx, maxx, maxy, miny)
                if result is not None:
                    self._geometry_cache[geometry] = result
                return result

        polygon_inner = self._unwrap_wkt(geometry, "POLYGON", layers=2)
        if polygon_inner is not None:
            result = self._parse_polygon_coords(polygon_inner, geometry)
            if result:
                self._geometry_cache[geometry] = result
            return result

        # Check if it's a MultiPolygon format: MultiPolygon(((r1)), ((r2)), ...)
        if geometry.strip().upper().startswith("MULTIPOLYGON"):
            result = self._parse_multipolygon_wkt(geometry)
            if result:
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
