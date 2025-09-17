import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from db.database import database
from sqlalchemy import text

logger = logging.getLogger(__name__)


class SpatialFacetService:
    """Service for determining spatial hierarchical facets from bounding boxes."""

    def __init__(self, resource_dict: Dict[str, Any]):
        self.resource_dict = resource_dict

    async def get_spatial_facets(self, session=None) -> Dict[str, Any]:
        """
        Get spatial hierarchical facets (country, state, county) from dcat_bbox.
        
        Args:
            session: Optional database session to use for queries
        
        Returns:
            Dictionary with geo.country, geo.state, geo.county keys
        """
        facets = {}
        
        try:
            bbox = self.resource_dict.get("dcat_bbox")
            if not bbox:
                logger.debug(f"No dcat_bbox found for resource {self.resource_dict.get('id', 'unknown')}")
                return facets
            
            # Parse the bounding box
            bbox_geom = self._parse_bbox_to_geometry(bbox)
            if not bbox_geom:
                logger.debug(f"Could not parse bbox {bbox} for resource {self.resource_dict.get('id', 'unknown')}")
                return facets
            
            # Get spatial facets using PostGIS and Who's on First data
            country = await self._get_country_from_bbox(bbox_geom, session)
            if country:
                facets["geo.country"] = country
            
            regions = await self._get_regions_from_bbox(bbox_geom, session)
            if regions:
                facets["geo.region"] = regions
            
            counties = await self._get_counties_from_bbox(bbox_geom, session=session)
            if counties:
                facets["geo.county"] = counties
                
        except Exception as e:
            logger.error(f"Error getting spatial facets for resource {self.resource_dict.get('id', 'unknown')}: {e}", exc_info=True)
        
        return facets

    def _get_fallback_spatial_facets(self, bbox_coords: Tuple[float, float, float, float]) -> Dict[str, Any]:
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
            envelope_match = re.match(r'ENVELOPE\(([^,]+),([^,]+),([^,]+),([^)]+)\)', bbox.strip())
            if envelope_match:
                xmin, xmax, ymax, ymin = map(float, envelope_match.groups())
                return (xmin, ymin, xmax, ymax)
            
            # Handle other bbox formats if needed
            logger.warning(f"Unrecognized bbox format: {bbox}")
            return None
            
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing bbox {bbox}: {e}")
            return None

    async def _get_country_from_bbox(self, bbox_coords: Tuple[float, float, float, float], session=None) -> Optional[str]:
        """
        Get country using centroid rule.
        
        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple
            
        Returns:
            Country name or None
        """
        try:
            xmin, ymin, xmax, ymax = bbox_coords
            
            # Optimized query using pre-computed geometry and spatial index
            query = """
            WITH bbox AS (
                SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
            ),
            centroid AS (
                SELECT ST_PointOnSurface(bbox.geom) AS point
                FROM bbox
            )
            SELECT wof.name
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
                result = await session.execute(text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax})
                row = result.fetchone()
                return row[0] if row else None
            else:
                result = await database.fetch_one(query, (xmin, ymin, xmax, ymax))
                return result["name"] if result else None
            
        except Exception as e:
            logger.error(f"Error getting country from bbox {bbox_coords}: {e}", exc_info=True)
            return None

    async def _get_regions_from_bbox(self, bbox_coords: Tuple[float, float, float, float], session=None) -> Optional[List[str]]:
        """
        Get all regions/states that overlap with the bounding box.
        
        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple
            
        Returns:
            List of region names or None
        """
        try:
            xmin, ymin, xmax, ymax = bbox_coords
            
            # Optimized query using spatial index and pre-computed geometry
            query = """
            WITH bbox AS (
                SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
            )
            SELECT wof.name
            FROM gazetteer_wof_spr wof
            JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
            CROSS JOIN bbox
            WHERE wof.placetype = 'region'
              AND wof.country = 'US'
              AND geojson.source = 'quattroshapes'
              AND geojson.alt_label IS NULL
              AND geojson.geometry IS NOT NULL
              AND ST_Intersects(geojson.geometry, bbox.geom)
            ORDER BY ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) DESC;
            """
            
            if session:
                result = await session.execute(text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax})
                rows = result.fetchall()
                return [row[0] for row in rows] if rows else None
            else:
                results = await database.fetch_all(query, (xmin, ymin, xmax, ymax))
                return [row["name"] for row in results] if results else None
            
        except Exception as e:
            logger.error(f"Error getting regions from bbox {bbox_coords}: {e}", exc_info=True)
            return None

    async def _get_counties_from_bbox(self, bbox_coords: Tuple[float, float, float, float], 
                                    threshold: float = 0.001, session=None) -> Optional[List[str]]:
        """
        Get counties using multi-value rule with overlap threshold.
        
        Args:
            bbox_coords: (xmin, ymin, xmax, ymax) tuple
            threshold: Minimum overlap percentage (default 0.001 = 0.1%)
            
        Returns:
            List of county names or None
        """
        try:
            xmin, ymin, xmax, ymax = bbox_coords
            
            # Highly optimized query using materialized view and spatial indexes
            query = """
            WITH bbox AS (
                SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
            ),
            bbox_area AS (
                SELECT ST_Area(bbox.geom::geography) AS total_area
                FROM bbox
            )
            SELECT csr.state_abbrev || '|' || csr.county_name as county_with_state
            FROM county_state_relationships csr
            JOIN gazetteer_wof_geojson geojson ON csr.county_wok_id = geojson.wok_id
            CROSS JOIN bbox, bbox_area
            WHERE geojson.source = 'quattroshapes'
              AND geojson.alt_label IS NULL
              AND geojson.geometry IS NOT NULL
              AND ST_Intersects(geojson.geometry, bbox.geom)
              AND ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) / bbox_area.total_area >= :threshold
            ORDER BY ST_Area(ST_Intersection(geojson.geometry, bbox.geom)::geography) DESC
            LIMIT 100;
            """
            
            if session:
                result = await session.execute(text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax, "threshold": threshold})
                rows = result.fetchall()
                return [row[0] for row in rows] if rows else None
            else:
                results = await database.fetch_all(query, (xmin, ymin, xmax, ymax, threshold))
                return [row["name"] for row in results] if results else None
            
        except Exception as e:
            logger.error(f"Error getting counties from bbox {bbox_coords}: {e}", exc_info=True)
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
                {"resource_id": resource_id}
            )
            
            if not resource:
                logger.warning(f"Resource {resource_id} not found")
                return {}
            
            # Create service instance and get facets
            service = SpatialFacetService(dict(resource))
            return await service.get_spatial_facets()
            
        except Exception as e:
            logger.error(f"Error getting spatial facets for resource {resource_id}: {e}", exc_info=True)
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
            
            # Fetch all resources
            placeholders = ",".join([f":id_{i}" for i in range(len(resource_ids))])
            params = {f"id_{i}": resource_id for i, resource_id in enumerate(resource_ids)}
            
            resources = await database.fetch_all(
                f"SELECT id, dcat_bbox FROM resources WHERE id IN ({placeholders})",
                params
            )
            
            # Process each resource
            results = {}
            for resource in resources:
                service = SpatialFacetService(dict(resource))
                facets = await service.get_spatial_facets()
                results[resource["id"]] = facets
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting batch spatial facets for {len(resource_ids)} resources: {e}", exc_info=True)
            return {}
