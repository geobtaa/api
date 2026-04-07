import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from db.database import database

logger = logging.getLogger(__name__)


class SpatialFacetService:
    """Service for determining spatial hierarchical facets from bounding boxes."""

    def __init__(self, resource_dict: Dict[str, Any]):
        self.resource_dict = resource_dict

    async def get_spatial_facets(self, session=None, debug=False) -> Dict[str, Any]:
        """
        Get spatial hierarchical facets (country, state, county) from dcat_bbox.

        Args:
            session: Optional database session to use for queries
            debug: If True, include overlap ratios in results

        Returns:
            Dictionary with geo.global, geo.country, geo.region, geo.county keys
        """
        facets = {}

        try:
            bbox = self.resource_dict.get("dcat_bbox")
            if not bbox:
                logger.debug(
                    f"No dcat_bbox found for resource {self.resource_dict.get('id', 'unknown')}"
                )
                return facets

            # Parse the bounding box
            bbox_geom = self._parse_bbox_to_geometry(bbox)
            if not bbox_geom:
                logger.debug(
                    f"Could not parse bbox {bbox} for resource "
                    f"{self.resource_dict.get('id', 'unknown')}"
                )
                return facets

            # Check if this is a global dataset (entire world)
            if self._is_global_bbox(bbox_geom):
                facets["geo.global"] = True
                resource_id = self.resource_dict.get("id", "unknown")
                logger.debug(f"Global dataset detected for resource {resource_id}")
                return facets

            # Get spatial facets using PostGIS and Who's on First data
            country = await self._get_country_from_bbox(bbox_geom, session)
            if country:
                # Store as dict to preserve WOF IDs for indexing
                facets["geo.country"] = country

            regions = await self._get_regions_from_bbox(bbox_geom, session, debug=debug)
            if regions:
                # Store full dict array to preserve WOF IDs for indexing
                # (debug mode adds overlap_percent to each dict)
                facets["geo.region"] = regions

            counties = await self._get_counties_from_bbox(bbox_geom, session=session, debug=debug)
            if counties:
                # Store full dict array to preserve WOF IDs for indexing
                # (debug mode adds overlap_percent to each dict)
                facets["geo.county"] = counties

        except Exception as e:
            logger.error(
                f"Error getting spatial facets for resource "
                f"{self.resource_dict.get('id', 'unknown')}: {e}",
                exc_info=True,
            )

        return facets

    async def get_spatial_facets_with_wof_ids(self, session=None, debug=False) -> Dict[str, Any]:
        """
        Get spatial hierarchical facets with Who's on First identifiers for map visualization.

        Args:
            session: Optional database session to use for queries
            debug: If True, include overlap ratios in results

        Returns:
            Dictionary with geo.country, geo.region, geo.county keys containing WOF identifiers
        """
        facets = {}

        try:
            bbox = self.resource_dict.get("dcat_bbox")
            if not bbox:
                logger.debug(
                    f"No dcat_bbox found for resource {self.resource_dict.get('id', 'unknown')}"
                )
                return facets

            # Parse the bounding box
            bbox_geom = self._parse_bbox_to_geometry(bbox)
            if not bbox_geom:
                logger.debug(
                    f"Could not parse bbox {bbox} for resource "
                    f"{self.resource_dict.get('id', 'unknown')}"
                )
                return facets

            # Check if this is a global bbox - if so, return geo.global = True immediately
            # This should happen before PostGIS queries to avoid antipodal errors
            if self._is_global_bbox(bbox_geom):
                logger.debug(
                    f"Global bbox detected for resource "
                    f"{self.resource_dict.get('id', 'unknown')}: {bbox_geom}"
                )
                return {"geo.global": True}

            # Get spatial facets using PostGIS and Who's on First data
            # Use try/except around each query to handle transaction failures
            try:
                country = await self._get_country_from_bbox(bbox_geom, session)
                if country:
                    facets["geo.country"] = country
            except Exception as e:
                logger.warning(
                    f"Error getting country for resource "
                    f"{self.resource_dict.get('id', 'unknown')}: {e}"
                )
                if session:
                    try:
                        await session.rollback()
                    except Exception:
                        pass

            try:
                regions = await self._get_regions_from_bbox(bbox_geom, session, debug=debug)
                if regions:
                    facets["geo.region"] = regions
            except Exception as e:
                logger.warning(
                    f"Error getting regions for resource "
                    f"{self.resource_dict.get('id', 'unknown')}: {e}"
                )
                if session:
                    try:
                        await session.rollback()
                    except Exception:
                        pass

            try:
                counties = await self._get_counties_from_bbox(
                    bbox_geom, session=session, debug=debug
                )
                if counties:
                    facets["geo.county"] = counties
            except Exception as e:
                logger.warning(
                    f"Error getting counties for resource "
                    f"{self.resource_dict.get('id', 'unknown')}: {e}"
                )
                if session:
                    try:
                        await session.rollback()
                    except Exception:
                        pass

        except Exception as e:
            logger.error(
                f"Error getting spatial facets for resource "
                f"{self.resource_dict.get('id', 'unknown')}: {e}",
                exc_info=True,
            )
            # Rollback transaction if it's in a failed state
            if session:
                try:
                    await session.rollback()
                except Exception:
                    pass

        return facets

    def _get_fallback_spatial_facets(
        self, bbox_coords: Tuple[float, float, float, float]
    ) -> Dict[str, Any]:
        """
        Fallback method to determine spatial facets using simple coordinate-based logic.

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple

        Returns:
            Dictionary with basic spatial facet data
        """
        facets = {}
        xmin, ymin, xmax, ymax = bbox_coords

        # Calculate centroid
        centroid_lon = (xmin + xmax) / 2
        centroid_lat = (ymin + ymax) / 2

        # Simple coordinate-based country detection for US
        if -180 <= centroid_lon <= -50 and 18 <= centroid_lat <= 72:
            facets["geo.country"] = "United States"

            # Simple state detection based on latitude/longitude ranges
            if 25 <= centroid_lat <= 49 and -125 <= centroid_lon <= -66:
                # This is a very basic approximation - in reality you'd need proper state boundaries
                if 40 <= centroid_lat <= 49 and -125 <= centroid_lon <= -95:
                    facets["geo.state"] = "Western United States"
                elif 25 <= centroid_lat <= 40 and -125 <= centroid_lon <= -95:
                    facets["geo.state"] = "Southwestern United States"
                elif 25 <= centroid_lat <= 49 and -95 <= centroid_lon <= -66:
                    facets["geo.state"] = "Eastern United States"

        return facets

    def _is_global_bbox(self, bbox_coords: Tuple[float, float, float, float]) -> bool:
        """
        Check if a bounding box represents a global dataset (entire world).

        Allows some tolerance for catalogers who might use near-global extents
        to work around validation constraints. Also considers bboxes with very large
        longitude spans (>= 180 degrees) as global, even if latitude span is limited.

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple

        Returns:
            True if the bbox covers the entire world (or very close to it), False otherwise
        """
        xmin, ymin, xmax, ymax = bbox_coords

        # Allow 1 degree of tolerance on each edge for near-global datasets
        # This catches catalogers who fudge the bbox slightly to validate against Solr
        tolerance = 1.0

        lon_span = xmax - xmin
        lat_span = ymax - ymin

        # Handle dateline crossing: if xmin is negative and xmax is positive,
        # calculate the actual wrapped span
        if xmin < 0 and xmax > 0:
            # Dateline crossing - the actual span wraps around
            actual_lon_span = 360 - (abs(xmin) + abs(xmax))
        else:
            actual_lon_span = lon_span

        # Check if longitude span is close to 360 degrees (within tolerance)
        # and latitude span is close to 180 degrees (within tolerance)
        # and the bounds are close to world extent
        is_fully_global = (
            actual_lon_span >= (360 - tolerance * 2)  # At least 358 degrees wide
            and lat_span >= (180 - tolerance * 2)  # At least 178 degrees tall
            and xmin >= (-180 - tolerance)
            and xmin <= (-180 + tolerance)  # Western edge near -180
            and xmax <= (180 + tolerance)
            and xmax >= (180 - tolerance)  # Eastern edge near 180
            and ymin >= (-90 - tolerance)
            and ymin <= (-90 + tolerance)  # Southern edge near -90
            and ymax <= (90 + tolerance)
            and ymax >= (90 - tolerance)  # Northern edge near 90
        )

        # Also consider bboxes with very large longitude spans (>= 180 degrees) as global
        # even if latitude span is limited - these represent near-global datasets
        is_near_global_longitude = (
            actual_lon_span >= (360 - tolerance * 2)  # At least 358 degrees wide
            or (
                lon_span >= 180.0
                and xmin <= (-180 + tolerance * 2)
                and xmax >= (180 - tolerance * 2)
            )
        )

        return is_fully_global or is_near_global_longitude

    def _parse_bbox_to_geometry(self, bbox: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse ENVELOPE string to (xmin, ymin, xmax, ymax) tuple.

        Args:
            bbox: ENVELOPE string like "ENVELOPE(-123.08286, -121.912937, 45.918689, 45.255769)"

        Returns:
            Tuple of (xmin, ymin, xmax, ymax) or None if parsing fails
        """
        try:
            # Handle ENVELOPE format: ENVELOPE(xmin, xmax, ymax, ymin)
            envelope_match = re.match(r"ENVELOPE\(([^,]+),([^,]+),([^,]+),([^)]+)\)", bbox.strip())
            if envelope_match:
                xmin, xmax, ymax, ymin = map(float, envelope_match.groups())

                # Auto-fix: ensure xmin < xmax and ymin < ymax
                if xmin > xmax:
                    xmin, xmax = xmax, xmin
                    logger.debug(f"Swapped x coordinates in ENVELOPE bbox: {bbox}")

                if ymin > ymax:
                    ymin, ymax = ymax, ymin
                    logger.debug(f"Swapped y coordinates in ENVELOPE bbox: {bbox}")

                # Check if this is a point location (zero-area bbox)
                # If so, add a small buffer to make it processable
                buffer = 0.001  # ~100 meters at the equator

                if xmin == xmax and ymin == ymax:
                    # Point location - expand in all directions
                    logger.debug(f"Point location detected in {bbox}, adding buffer")
                    xmin -= buffer
                    xmax += buffer
                    ymin -= buffer
                    ymax += buffer
                elif xmin == xmax:
                    # Vertical line - expand horizontally
                    logger.debug(f"Vertical line detected in {bbox}, adding horizontal buffer")
                    xmin -= buffer
                    xmax += buffer
                elif ymin == ymax:
                    # Horizontal line - expand vertically
                    logger.debug(f"Horizontal line detected in {bbox}, adding vertical buffer")
                    ymin -= buffer
                    ymax += buffer

                # Handle very small bounding boxes (expand if too small)
                if (xmax - xmin) < 0.001:
                    logger.debug(f"Very small x range in {bbox}, expanding")
                    center_x = (xmin + xmax) / 2
                    xmin = center_x - buffer
                    xmax = center_x + buffer

                if (ymax - ymin) < 0.001:
                    logger.debug(f"Very small y range in {bbox}, expanding")
                    center_y = (ymin + ymax) / 2
                    ymin = center_y - buffer
                    ymax = center_y + buffer

                # Check if this is a global bbox BEFORE validation
                # Global bboxes should be returned even if they fail validation
                if self._is_global_bbox((xmin, ymin, xmax, ymax)):
                    logger.debug(
                        f"Global bbox detected (may fail validation): {bbox} -> "
                        f"({xmin},{ymin},{xmax},{ymax})"
                    )
                    return (xmin, ymin, xmax, ymax)

                # Validate bounding box
                if not self._is_valid_bbox(xmin, ymin, xmax, ymax):
                    logger.warning(
                        f"Invalid bounding box after fixes: {bbox} -> "
                        f"({xmin},{ymin},{xmax},{ymax}) - skipping"
                    )
                    return None

                return (xmin, ymin, xmax, ymax)

            # Handle simple comma-separated format: xmin,ymin,xmax,ymax
            parts = [p.strip() for p in bbox.split(",")]
            if len(parts) == 4:
                try:
                    xmin, ymin, xmax, ymax = map(float, parts)

                    # Auto-fix common issues: swapped coordinates
                    if xmin > xmax:
                        # x coordinates might be swapped
                        xmin, xmax = xmax, xmin
                        logger.debug(f"Swapped x coordinates in bbox: {bbox}")

                    if ymin > ymax:
                        # y coordinates might be swapped
                        ymin, ymax = ymax, ymin
                        logger.debug(f"Swapped y coordinates in bbox: {bbox}")

                    # Check if this is a point location (zero-area bbox)
                    buffer = 0.001  # ~100 meters at the equator

                    if xmin == xmax and ymin == ymax:
                        # Point location - expand in all directions
                        logger.debug(f"Point location detected in {bbox}, adding buffer")
                        xmin -= buffer
                        xmax += buffer
                        ymin -= buffer
                        ymax += buffer
                    elif xmin == xmax:
                        # Vertical line - expand horizontally
                        logger.debug(f"Vertical line detected in {bbox}, adding horizontal buffer")
                        xmin -= buffer
                        xmax += buffer
                    elif ymin == ymax:
                        # Horizontal line - expand vertically
                        logger.debug(f"Horizontal line detected in {bbox}, adding vertical buffer")
                        ymin -= buffer
                        ymax += buffer

                    # Handle very small bounding boxes (expand if too small)
                    if (xmax - xmin) < 0.001:
                        logger.debug(f"Very small x range in {bbox}, expanding")
                        center_x = (xmin + xmax) / 2
                        xmin = center_x - buffer
                        xmax = center_x + buffer

                    if (ymax - ymin) < 0.001:
                        logger.debug(f"Very small y range in {bbox}, expanding")
                        center_y = (ymin + ymax) / 2
                        ymin = center_y - buffer
                        ymax = center_y + buffer

                    # Check if this is a global bbox BEFORE validation
                    # Global bboxes should be returned even if they fail validation
                    if self._is_global_bbox((xmin, ymin, xmax, ymax)):
                        logger.debug(
                            f"Global bbox detected (may fail validation): {bbox} -> "
                            f"({xmin},{ymin},{xmax},{ymax})"
                        )
                        return (xmin, ymin, xmax, ymax)

                    # Validate bounding box
                    if not self._is_valid_bbox(xmin, ymin, xmax, ymax):
                        logger.warning(
                            f"Invalid bounding box after fixes: {bbox} -> "
                            f"({xmin},{ymin},{xmax},{ymax}) - skipping"
                        )
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
        Validate that a bounding box is reasonable for spatial processing.

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

        # Allow global/near-global extent for global datasets
        # Use the same detection logic as _is_global_bbox
        if self._is_global_bbox((xmin, ymin, xmax, ymax)):
            return True

        # Check for antipodal edges (spans 180 degrees longitude)
        # But allow dateline crossing for high-latitude regions (e.g., Arctic)
        lon_span = abs(xmax - xmin)
        if lon_span >= 180:
            # If this crosses the dateline (xmin negative, xmax positive) and is at high latitude,
            # it might be a legitimate bbox (e.g., Arctic regions)
            if xmin < 0 and xmax > 0 and abs((ymin + ymax) / 2) > 60:
                # High latitude dateline crossing - allow it
                pass
            else:
                return False

        # Check for extremely large bounding boxes (likely data errors)
        # For latitude, allow up to 180 degrees (covers entire globe N-S)
        # This allows legitimate large datasets like continental coverage
        if (ymax - ymin) > 180:
            return False

        # For longitude, use latitude-dependent threshold
        # At high latitudes (near poles), wider longitude spans are legitimate
        # because lines of longitude converge
        avg_lat = abs((ymin + ymax) / 2)
        lon_span = abs(xmax - xmin)

        # Handle dateline crossing: if xmin is negative and xmax is positive,
        # the actual span might wrap around (360 - lon_span)
        if xmin < 0 and xmax > 0:
            # Dateline crossing - calculate the shorter path
            # The actual span is either lon_span or (360 - lon_span), whichever is smaller
            actual_span = min(lon_span, 360 - lon_span)
        else:
            actual_span = lon_span

        # At the equator (lat=0), allow up to 180 degrees (half the globe)
        # At the poles (lat=90), allow up to 360 degrees (full circle)
        # Linear interpolation between these extremes
        # This allows legitimate large datasets like continental coverage
        max_lon_span = 180 + (avg_lat / 90) * 180  # ranges from 180 to 360

        if actual_span > max_lon_span:
            return False

        # Check for zero-area bounding boxes
        if (xmax - xmin) < 0.001 or (ymax - ymin) < 0.001:
            return False

        return True

    async def _get_country_from_bbox(
        self, bbox_coords: Tuple[float, float, float, float], session=None
    ) -> Optional[Dict[str, Any]]:
        """
        Get country using centroid rule.

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple

        Returns:
            Dictionary with country info (name, wok_id, parent_id) or None
        """
        try:
            xmin, ymin, xmax, ymax = bbox_coords

            # Skip global bboxes - they can't be processed by PostGIS
            if self._is_global_bbox(bbox_coords):
                logger.debug(f"Skipping global bbox for country lookup: {bbox_coords}")
                return None

            # Skip bboxes with exactly 180-degree longitude span (PostGIS antipodal error)
            if abs(xmax - xmin) >= 180.0:
                logger.debug(f"Skipping antipodal bbox for country lookup: {bbox_coords}")
                return None

            # Optimized query using pre-computed geometry and spatial index
            query = """
            WITH bbox AS (
                SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
            ),
            centroid AS (
                SELECT ST_PointOnSurface(bbox.geom) AS point
                FROM bbox
            )
            SELECT wof.name, wof.wok_id, wof.parent_id
            FROM gazetteer_wof_spr wof
            JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
            CROSS JOIN centroid
            WHERE wof.placetype = 'country'
              AND geojson.source = 'quattroshapes'
              AND geojson.alt_label = 'quattroshapes'
              AND geojson.geometry IS NOT NULL
              AND ST_Contains(geojson.geometry, centroid.point)
            ORDER BY ST_Area(geojson.geometry) DESC
            LIMIT 1;
            """

            if session:
                result = await session.execute(
                    text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
                )
                row = result.fetchone()
                if row:
                    return {"name": row[0], "wok_id": row[1], "parent_id": row[2]}
                return None
            else:
                result = await database.fetch_one(
                    query, {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
                )
                if result:
                    return {
                        "name": result["name"],
                        "wok_id": result["wok_id"],
                        "parent_id": result["parent_id"],
                    }
                return None

        except Exception as e:
            logger.error(f"Error getting country from bbox {bbox_coords}: {e}", exc_info=True)
            # Rollback transaction if it's in a failed state
            if session:
                try:
                    await session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
            return None

    async def _get_regions_from_bbox(
        self, bbox_coords: Tuple[float, float, float, float], session=None, debug=False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get all regions/states that overlap with the bounding box.

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple
            debug: If True, include overlap ratios in results

        Returns:
            List of region info dictionaries (name, wok_id, parent_id,
            overlap_percent if debug) or None
        """
        try:
            xmin, ymin, xmax, ymax = bbox_coords

            # Skip global bboxes - they can't be processed by PostGIS
            if self._is_global_bbox(bbox_coords):
                logger.debug(f"Skipping global bbox for regions lookup: {bbox_coords}")
                return None

            # Skip bboxes with exactly 180-degree longitude span (PostGIS antipodal error)
            if abs(xmax - xmin) >= 180.0:
                logger.debug(f"Skipping antipodal bbox for regions lookup: {bbox_coords}")
                return None

            # Optimized query using spatial index and pre-computed geometry
            if debug:
                query = """
                WITH bbox AS (
                    SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
                ),
                bbox_area AS (
                    SELECT ST_Area(bbox.geom::geography) AS total_area
                    FROM bbox
                ),
                intersections AS (
                    SELECT 
                        wof.name, 
                        wof.wok_id, 
                        wof.parent_id,
                        ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) 
                        AS intersect_area
                    FROM gazetteer_wof_spr wof
                    JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
                    CROSS JOIN bbox
                    WHERE wof.placetype = 'region'
                      AND wof.country = 'US'
                      AND geojson.source = 'quattroshapes'
                      AND geojson.alt_label IS NULL
                      AND geojson.geometry IS NOT NULL
                      AND ST_Intersects(geojson.geometry, bbox.geom)
                )
                SELECT 
                    name, wok_id, parent_id,
                    ROUND((intersect_area / bbox_area.total_area) * 100) AS overlap_percent
                FROM intersections, bbox_area
                ORDER BY intersect_area DESC;
                """
            else:
                query = """
                WITH bbox AS (
                    SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
                ),
                intersections AS (
                    SELECT 
                        wof.name, 
                        wof.wok_id, 
                        wof.parent_id,
                        ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) 
                        AS intersect_area
                    FROM gazetteer_wof_spr wof
                    JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
                    CROSS JOIN bbox
                    WHERE wof.placetype = 'region'
                      AND wof.country = 'US'
                      AND geojson.source = 'quattroshapes'
                      AND geojson.alt_label IS NULL
                      AND geojson.geometry IS NOT NULL
                      AND ST_Intersects(geojson.geometry, bbox.geom)
                )
                SELECT name, wok_id, parent_id
                FROM intersections
                ORDER BY intersect_area DESC;
                """

            if session:
                result = await session.execute(
                    text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
                )
                rows = result.fetchall()
                if rows:
                    if debug:
                        return [
                            {
                                "name": row[0],
                                "wok_id": row[1],
                                "parent_id": row[2],
                                "overlap_percent": int(row[3]),
                            }
                            for row in rows
                        ]
                    else:
                        return [
                            {"name": row[0], "wok_id": row[1], "parent_id": row[2]} for row in rows
                        ]
                return None
            else:
                results = await database.fetch_all(
                    query, {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
                )
                if results:
                    if debug:
                        return [
                            {
                                "name": row["name"],
                                "wok_id": row["wok_id"],
                                "parent_id": row["parent_id"],
                                "overlap_percent": int(row["overlap_percent"]),
                            }
                            for row in results
                        ]
                    else:
                        return [
                            {
                                "name": row["name"],
                                "wok_id": row["wok_id"],
                                "parent_id": row["parent_id"],
                            }
                            for row in results
                        ]
                return None

        except Exception as e:
            logger.error(f"Error getting regions from bbox {bbox_coords}: {e}", exc_info=True)
            # Rollback transaction if it's in a failed state
            if session:
                try:
                    await session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
            return None

    async def _get_counties_from_bbox(
        self,
        bbox_coords: Tuple[float, float, float, float],
        threshold: float = 0.001,
        session=None,
        debug=False,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get counties using multi-value rule with overlap threshold.

        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple
            threshold: Minimum overlap percentage (default 0.001 = 0.1%)
            debug: If True, include overlap ratios in results

        Returns:
            List of county info dictionaries (name, wok_id, parent_id,
            state_abbrev, overlap_percent if debug) or None
        """
        try:
            xmin, ymin, xmax, ymax = bbox_coords

            # Skip global bboxes - they can't be processed by PostGIS
            if self._is_global_bbox(bbox_coords):
                logger.debug(f"Skipping global bbox for counties lookup: {bbox_coords}")
                return None

            # Skip bboxes with exactly 180-degree longitude span (PostGIS antipodal error)
            if abs(xmax - xmin) >= 180.0:
                logger.debug(f"Skipping antipodal bbox for counties lookup: {bbox_coords}")
                return None

            # Highly optimized query using materialized view and spatial indexes
            if debug:
                query = """
                WITH bbox AS (
                    SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
                ),
                bbox_area AS (
                    SELECT ST_Area(bbox.geom::geography) AS total_area
                    FROM bbox
                ),
                intersections AS (
                    SELECT 
                        csr.county_name, 
                        csr.county_wok_id, 
                        csr.state_wok_id, 
                        csr.state_abbrev,
                        ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) 
                        AS intersect_area
                    FROM county_state_relationships csr
                    JOIN gazetteer_wof_geojson geojson ON csr.county_wok_id = geojson.wok_id
                    CROSS JOIN bbox
                    WHERE geojson.source = 'quattroshapes'
                      AND geojson.alt_label IS NULL
                      AND geojson.geometry IS NOT NULL
                      AND ST_Intersects(geojson.geometry, bbox.geom)
                ),
                filtered AS (
                    SELECT *, (intersect_area / bbox_area.total_area) AS overlap_ratio
                    FROM intersections, bbox_area
                    WHERE (intersect_area / bbox_area.total_area) >= :threshold
                )
                SELECT 
                    county_name, county_wok_id, state_wok_id, state_abbrev,
                    ROUND(overlap_ratio * 100) AS overlap_percent
                FROM filtered
                ORDER BY intersect_area DESC
                LIMIT 100;
                """
            else:
                query = """
                WITH bbox AS (
                    SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
                ),
                bbox_area AS (
                    SELECT ST_Area(bbox.geom::geography) AS total_area
                    FROM bbox
                ),
                intersections AS (
                    SELECT 
                        csr.county_name, 
                        csr.county_wok_id, 
                        csr.state_wok_id, 
                        csr.state_abbrev,
                        ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) 
                        AS intersect_area
                    FROM county_state_relationships csr
                    JOIN gazetteer_wof_geojson geojson ON csr.county_wok_id = geojson.wok_id
                    CROSS JOIN bbox
                    WHERE geojson.source = 'quattroshapes'
                      AND geojson.alt_label IS NULL
                      AND geojson.geometry IS NOT NULL
                      AND ST_Intersects(geojson.geometry, bbox.geom)
                ),
                filtered AS (
                    SELECT *, (intersect_area / bbox_area.total_area) AS overlap_ratio
                    FROM intersections, bbox_area
                    WHERE (intersect_area / bbox_area.total_area) >= :threshold
                )
                SELECT county_name, county_wok_id, state_wok_id, state_abbrev
                FROM filtered
                ORDER BY intersect_area DESC
                LIMIT 100;
                """

            if session:
                result = await session.execute(
                    text(query),
                    {
                        "xmin": xmin,
                        "ymin": ymin,
                        "xmax": xmax,
                        "ymax": ymax,
                        "threshold": threshold,
                    },
                )
                rows = result.fetchall()
                if rows:
                    if debug:
                        return [
                            {
                                "name": row[0],
                                "wok_id": row[1],
                                "parent_id": row[2],
                                "state_abbrev": row[3],
                                "overlap_percent": int(row[4]),
                            }
                            for row in rows
                        ]
                    else:
                        return [
                            {
                                "name": row[0],
                                "wok_id": row[1],
                                "parent_id": row[2],
                                "state_abbrev": row[3],
                            }
                            for row in rows
                        ]
                return None
            else:
                results = await database.fetch_all(
                    query,
                    {
                        "xmin": xmin,
                        "ymin": ymin,
                        "xmax": xmax,
                        "ymax": ymax,
                        "threshold": threshold,
                    },
                )
                if results:
                    if debug:
                        return [
                            {
                                "name": row["county_name"],
                                "wok_id": row["county_wok_id"],
                                "parent_id": row["state_wok_id"],
                                "state_abbrev": row["state_abbrev"],
                                "overlap_percent": int(row["overlap_percent"]),
                            }
                            for row in results
                        ]
                    else:
                        return [
                            {
                                "name": row["county_name"],
                                "wok_id": row["county_wok_id"],
                                "parent_id": row["state_wok_id"],
                                "state_abbrev": row["state_abbrev"],
                            }
                            for row in results
                        ]
                return None

        except Exception as e:
            logger.error(f"Error getting counties from bbox {bbox_coords}: {e}", exc_info=True)
            # Rollback transaction if it's in a failed state
            if session:
                try:
                    await session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
            return None

    @staticmethod
    async def get_resource_spatial_facets(resource_id: str) -> Dict[str, Any]:
        """
        Get spatial facets for a specific resource by ID.

        Args:
            resource_id: The resource ID to get facets for

        Returns:
            Dictionary with spatial facet data
        """
        try:
            # Fetch the resource
            resource = await database.fetch_one(
                "SELECT id, dcat_bbox FROM resources WHERE id = :resource_id",
                {"resource_id": resource_id},
            )

            if not resource:
                logger.warning(f"Resource {resource_id} not found")
                return {}

            # Create service instance and get facets
            service = SpatialFacetService(dict(resource))
            return await service.get_spatial_facets()

        except Exception as e:
            logger.error(
                f"Error getting spatial facets for resource {resource_id}: {e}", exc_info=True
            )
            return {}

    @staticmethod
    async def batch_get_spatial_facets(resource_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get spatial facets for multiple resources in batch.

        Args:
            resource_ids: List of resource IDs

        Returns:
            Dictionary mapping resource_id to spatial facets
        """
        try:
            if not resource_ids:
                return {}

            resources = await database.fetch_all(
                text("SELECT id, dcat_bbox FROM resources WHERE id = ANY(:resource_ids)"),
                {"resource_ids": resource_ids},
            )

            # Process each resource
            results = {}
            for resource in resources:
                service = SpatialFacetService(dict(resource))
                facets = await service.get_spatial_facets()
                results[resource["id"]] = facets

            return results

        except Exception as e:
            logger.error(
                f"Error getting batch spatial facets for {len(resource_ids)} resources: {e}",
                exc_info=True,
            )
            return {}
