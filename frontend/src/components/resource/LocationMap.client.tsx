import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { normalizeGeometry } from '../../utils/geometryUtils';
import { attachBasemapSwitcher } from '../../config/basemaps';

interface LocationMapProps {
  geometry:
    | string
    | GeoJSON.Polygon
    | GeoJSON.MultiPolygon
    | { wkt: string }
    | null; // Accept any format, we'll normalize it
}

export const LocationMap: React.FC<LocationMapProps> = ({ geometry }) => {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainer = useRef<HTMLDivElement>(null);
  const basemapCleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!mapContainer.current || !geometry) return;

    // Normalize the geometry to GeoJSON format
    const normalizedGeometry = normalizeGeometry(geometry);
    if (!normalizedGeometry) {
      console.warn('Could not normalize geometry:', geometry);
      return;
    }

    // Initialize map if it doesn't exist
    if (!mapRef.current) {
      mapRef.current = L.map(mapContainer.current).setView([0, 0], 2);
      basemapCleanupRef.current = attachBasemapSwitcher(mapRef.current, L);
    }

    // Clear existing layers
    mapRef.current.eachLayer((layer) => {
      if (layer instanceof L.GeoJSON) {
        mapRef.current?.removeLayer(layer);
      }
    });

    try {
      // Handle MultiPolygon by converting to individual Polygon features
      // Standard GeoJSON: coordinates = [[ring1, hole?], [ring2], ...] per polygon
      let features;
      if (normalizedGeometry.type === 'MultiPolygon') {
        features = normalizedGeometry.coordinates.map((polygonRings) => {
          return {
            type: 'Feature' as const,
            geometry: {
              type: 'Polygon' as const,
              coordinates: polygonRings, // [exteriorRing, hole1?, ...]
            },
            properties: {},
          };
        });
      } else {
        features = [
          {
            type: 'Feature' as const,
            geometry: normalizedGeometry,
            properties: {},
          },
        ];
      }

      // Add the GeoJSON layer
      const geoJsonLayer = L.geoJSON(features, {
        style: {
          color: '#2563eb',
          weight: 2,
          opacity: 0.6,
          fillOpacity: 0.1,
        },
      }).addTo(mapRef.current);

      // Add a dashed bounding box for MultiPolygon to show full extent
      if (normalizedGeometry.type === 'MultiPolygon') {
        // Calculate the bounding box of all polygons
        let minLat = Infinity,
          maxLat = -Infinity,
          minLon = Infinity,
          maxLon = -Infinity;

        normalizedGeometry.coordinates.forEach((polygonRings) => {
          polygonRings.forEach((ring) => {
            ring.forEach((coord) => {
              const [lon, lat] = coord;
              minLat = Math.min(minLat, lat);
              maxLat = Math.max(maxLat, lat);
              minLon = Math.min(minLon, lon);
              maxLon = Math.max(maxLon, lon);
            });
          });
        });

        // Create a bounding box rectangle
        const bounds = L.latLngBounds(
          L.latLng(minLat, minLon),
          L.latLng(maxLat, maxLon)
        );

        // Add dashed rectangle to show full extent
        L.rectangle(bounds, {
          color: '#2563eb',
          weight: 2,
          opacity: 0.8,
          fillOpacity: 0,
          dashArray: '10, 5',
          className: 'multipolygon-extent',
        }).addTo(mapRef.current);
      }

      // Fit bounds to show the feature
      mapRef.current.fitBounds(geoJsonLayer.getBounds(), {
        padding: [20, 20],
      });
    } catch (error) {
      console.error('Error rendering geometry:', error);
    }

    return () => {
      basemapCleanupRef.current?.();
      basemapCleanupRef.current = null;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [geometry]);

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden pa11y-ignore-map-contrast">
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-950">Location</h2>
      </div>
      <div ref={mapContainer} className="h-[300px] w-full" />
    </div>
  );
};

export default LocationMap;
