"""
Service for generating static maps from resource geometries.

This service uses py-staticmaps to generate static map images from locn_geometry values.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import staticmaps
from shapely import wkt as shapely_wkt
from shapely.geometry import shape

logger = logging.getLogger(__name__)

# Custom Carto tile provider (not available in py-staticmaps v0.4.0)
# Based on: https://github.com/flopp/py-staticmaps/blob/e0266dc40163e87ce42a0ea5d8836a9a4bd92208/staticmaps/tile_provider.py#L132
tile_provider_Carto = staticmaps.TileProvider(
    "carto",
    url_pattern="http://$s.basemaps.cartocdn.com/rastertiles/light_all/$z/$x/$y.png",
    shards=["a", "b", "c", "d"],
    attribution="Maps (C) CARTO (C) OpenStreetMap.org contributors",
    max_zoom=20,
)


class StaticMapService:
    """Service for generating static maps from bounding boxes."""

    def __init__(self, map_width: int = 800, map_height: int = 600):
        """
        Initialize the static map service.

        Args:
            map_width: Width of generated maps in pixels (default: 800)
            map_height: Height of generated maps in pixels (default: 600)
        """
        self.map_width = map_width
        self.map_height = map_height
        self.maps_dir = Path(os.getenv("STATIC_MAPS_DIR", "static/maps"))
        self.maps_dir.mkdir(parents=True, exist_ok=True)

    def _parse_bbox_to_geometry(self, bbox: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse bbox string to (xmin, ymin, xmax, ymax) tuple.
        Supports both ENVELOPE format and simple comma-separated format.

        Args:
            bbox: ENVELOPE string like "ENVELOPE(-123.08286, -121.912937, 45.918689, 45.255769)"
                  or simple format like "-123.08286,45.255769,-121.912937,45.918689"
                  (xmin,ymin,xmax,ymax)

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if parsing fails
        """
        try:
            bbox = bbox.strip()

            # Handle ENVELOPE format: ENVELOPE(xmin, xmax, ymax, ymin)
            envelope_match = re.match(
                r"ENVELOPE\(([^,]+),([^,]+),([^,]+),([^)]+)\)", bbox, re.IGNORECASE
            )
            if envelope_match:
                xmin, xmax, ymax, ymin = map(float, envelope_match.groups())

                # Validate bounding box
                if not self._is_valid_bbox(xmin, ymin, xmax, ymax):
                    logger.warning(f"Invalid bounding box: {bbox} - skipping")
                    return None

                return (xmin, ymin, xmax, ymax)

            # Handle simple comma-separated format: xmin,ymin,xmax,ymax
            parts = [p.strip() for p in bbox.split(",")]
            if len(parts) == 4:
                try:
                    xmin, ymin, xmax, ymax = map(float, parts)

                    # Validate bounding box
                    if not self._is_valid_bbox(xmin, ymin, xmax, ymax):
                        logger.warning(f"Invalid bounding box: {bbox} - skipping")
                        return None

                    return (xmin, ymin, xmax, ymax)
                except ValueError:
                    logger.warning(f"Could not parse bbox coordinates: {bbox}")
                    return None

            # Unrecognized format
            logger.warning(f"Unrecognized bbox format: {bbox}")
            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing bbox {bbox}: {e}")
            return None

    def _is_valid_bbox(self, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
        """
        Validate that a bounding box is reasonable for map generation.

        Args:
            xmin, ymin, xmax, ymax: Bounding box coordinates

        Returns:
            True if the bounding box is valid, False otherwise
        """
        # Check for valid coordinate ranges
        if not (-180 <= xmin <= 180) or not (-180 <= xmax <= 180):
            return False
        if not (-90 <= ymin <= 90) or not (-90 <= ymax <= 90):
            return False

        # Check for valid min/max relationships
        if xmin >= xmax or ymin >= ymax:
            return False

        # Check for zero-area bounding boxes
        if (xmax - xmin) < 0.001 or (ymax - ymin) < 0.001:
            return False

        return True

    def _is_global_bbox(self, bbox_coords: Tuple[float, float, float, float]) -> bool:
        """
        Check if a bounding box represents a global dataset (entire world).

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple

        Returns:
            True if the bbox covers the entire world, False otherwise
        """
        xmin, ymin, xmax, ymax = bbox_coords
        tolerance = 1.0

        lon_span = xmax - xmin
        lat_span = ymax - ymin

        is_near_global = (
            lon_span >= (360 - tolerance * 2)
            and lat_span >= (180 - tolerance * 2)
            and xmin >= (-180 - tolerance)
            and xmin <= (-180 + tolerance)
            and xmax <= (180 + tolerance)
            and xmax >= (180 - tolerance)
            and ymin >= (-90 - tolerance)
            and ymin <= (-90 + tolerance)
            and ymax <= (90 + tolerance)
            and ymax >= (90 - tolerance)
        )

        return is_near_global

    def _parse_geometry_to_bbox(self, geometry: Any) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse geometry (GeoJSON, WKT, ENVELOPE, or string) to bounding box coordinates.

        Args:
            geometry: Geometry in various formats (GeoJSON dict, WKT string, ENVELOPE string, etc.)

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if parsing fails
        """
        if not geometry:
            return None

        try:
            # If it's already a dict (GeoJSON), use it directly
            if isinstance(geometry, dict):
                return self._extract_bbox_from_geojson(geometry)

            # If it's a string, try to parse it
            if isinstance(geometry, str):
                geometry_str = geometry.strip()

                # Try parsing as JSON first (GeoJSON)
                try:
                    geometry_dict = json.loads(geometry_str)
                    if isinstance(geometry_dict, dict):
                        return self._extract_bbox_from_geojson(geometry_dict)
                except (json.JSONDecodeError, ValueError):
                    pass

                # Try parsing as WKT using Shapely
                try:
                    shapely_geom = shapely_wkt.loads(geometry_str)
                    bounds = shapely_geom.bounds  # Returns (minx, miny, maxx, maxy)
                    return (bounds[0], bounds[1], bounds[2], bounds[3])
                except Exception:
                    pass

                # Try parsing as ENVELOPE or simple bbox format
                bbox_coords = self._parse_bbox_to_geometry(geometry_str)
                if bbox_coords:
                    return bbox_coords

            return None

        except Exception as e:
            logger.error(f"Error parsing geometry: {e}")
            return None

    def _extract_bbox_from_geojson(
        self, geojson: Dict[str, Any]
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Extract bounding box from GeoJSON geometry.

        Args:
            geojson: GeoJSON geometry dict

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if extraction fails
        """
        try:
            # Use Shapely to get bounds from any geometry type
            geom = shape(geojson)
            bounds = geom.bounds  # Returns (minx, miny, maxx, maxy)
            return (bounds[0], bounds[1], bounds[2], bounds[3])
        except Exception as e:
            logger.error(f"Error extracting bbox from GeoJSON: {e}")
            return None

    def generate_map(self, resource_id: str, geometry: Any) -> Optional[Path]:
        """
        Generate a static map image from a geometry.

        Args:
            resource_id: The resource ID
            geometry: Geometry in various formats (GeoJSON dict, WKT string, ENVELOPE string, etc.)

        Returns:
            Path to the generated map file, or None if generation failed
        """
        try:
            # Parse the geometry to get bounding box coordinates
            bbox_coords = self._parse_geometry_to_bbox(geometry)
            if not bbox_coords:
                logger.warning(f"Could not parse geometry for resource {resource_id}")
                return None

            xmin, ymin, xmax, ymax = bbox_coords

            # Skip global datasets (they don't make good static maps)
            if self._is_global_bbox(bbox_coords):
                logger.debug(f"Skipping global dataset for resource {resource_id}")
                return None

            # Create a context for the map
            context = staticmaps.Context()
            # Carto Light tiles (standard provider with labels)
            context.set_tile_provider(tile_provider_Carto)

            # Create a rectangle from the bounding box
            # py-staticmaps uses (lat, lon) order for coordinates
            # To make straight edges in Web Mercator projection, we need many intermediate points
            # along the top and bottom edges (lines of latitude) to approximate straight lines
            # Calculate number of segments based on bbox width - more segments for wider boxes
            bbox_width_degrees = xmax - xmin
            # Use more segments: approximately one per degree of longitude, minimum 50
            num_segments = max(50, int(bbox_width_degrees * 2))

            points = []

            # West edge: from south to north (straight line, no intermediate points needed)
            points.append(staticmaps.create_latlng(ymin, xmin))  # Southwest
            points.append(staticmaps.create_latlng(ymax, xmin))  # Northwest

            # North edge: from west to east (needs many points to appear straight in projection)
            for i in range(1, num_segments):
                lon = xmin + (xmax - xmin) * (i / num_segments)
                points.append(staticmaps.create_latlng(ymax, lon))

            # East edge: from north to south (straight line)
            points.append(staticmaps.create_latlng(ymax, xmax))  # Northeast
            points.append(staticmaps.create_latlng(ymin, xmax))  # Southeast

            # South edge: from east to west (needs many points to appear straight in projection)
            for i in range(num_segments - 1, 0, -1):
                lon = xmin + (xmax - xmin) * (i / num_segments)
                points.append(staticmaps.create_latlng(ymin, lon))

            # Close the polygon
            points.append(points[0])

            rectangle = staticmaps.Area(
                points,
                fill_color=staticmaps.Color(
                    37, 99, 235, 26
                ),  # #2563eb with 10% opacity (fill-opacity="0.1")
                color=staticmaps.Color(
                    37, 99, 235, 153
                ),  # #2563eb with 60% opacity (stroke-opacity="0.6")
                width=2,
            )

            # Add the rectangle to the context
            context.add_object(rectangle)

            # Render the map (this will auto-center and zoom to fit the objects)
            # Use render_cairo instead of render_pillow to avoid Pillow 10+ compatibility issues
            try:
                cairo_surface = context.render_cairo(self.map_width, self.map_height)
                # Convert cairo ImageSurface to Pillow Image
                import io

                from PIL import Image

                buf = io.BytesIO()
                cairo_surface.write_to_png(buf)
                buf.seek(0)
                image = Image.open(buf)
            except Exception as e:
                logger.warning(f"Failed to render with cairo, trying pillow: {e}")
                # Fallback to pillow if cairo fails (may fail with Pillow 10+)
                try:
                    image = context.render_pillow(self.map_width, self.map_height)
                except Exception as pillow_error:
                    logger.error(f"Both cairo and pillow rendering failed: {pillow_error}")
                    raise

            # Save the map to file
            map_path = self.maps_dir / f"{resource_id}.png"
            image.save(map_path, "PNG")

            logger.info(f"Generated static map for resource {resource_id} at {map_path}")
            return map_path

        except Exception as e:
            logger.error(
                f"Error generating static map for resource {resource_id}: {e}", exc_info=True
            )
            return None

    def get_map_path(self, resource_id: str) -> Optional[Path]:
        """
        Get the path to a static map file if it exists.

        Args:
            resource_id: The resource ID

        Returns:
            Path to the map file if it exists, None otherwise
        """
        map_path = self.maps_dir / f"{resource_id}.png"
        if map_path.exists():
            return map_path
        return None

    def map_exists(self, resource_id: str) -> bool:
        """
        Check if a static map exists for a resource.

        Args:
            resource_id: The resource ID

        Returns:
            True if the map exists, False otherwise
        """
        return self.get_map_path(resource_id) is not None
