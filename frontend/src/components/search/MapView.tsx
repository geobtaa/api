import { useEffect, useRef, useCallback } from 'react';
import type * as Leaflet from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoDocument } from '../../types/api';
import { useMap } from '../../context/MapContext';
import { isValidGeoJsonForLeaflet } from '../../utils/geometryUtils';
import { useSearchParams } from 'react-router';
import { attachBasemapSwitcher } from '../../config/basemaps';
import { debugLog } from '../../utils/logger';

interface MapViewProps {
  results: GeoDocument[];
}

interface BBox {
  topLeft: { lat: number; lon: number };
  bottomRight: { lat: number; lon: number };
}

export function MapView({ results }: MapViewProps) {
  const mapRef = useRef<Leaflet.Map | null>(null);
  const mapContainer = useRef<HTMLDivElement>(null);
  const highlightLayerRef = useRef<Leaflet.GeoJSON | null>(null);
  const filterRectRef = useRef<Leaflet.Rectangle | null>(null);
  const resultLayerRef = useRef<Leaflet.GeoJSON | null>(null);
  const basemapCleanupRef = useRef<(() => void) | null>(null);
  const { hoveredGeometry } = useMap();
  const [searchParams] = useSearchParams();
  const isUpdatingFromParamsRef = useRef(false);

  // Leaflet requires `window`, so only load it in the browser.
  const loadLeaflet = useCallback(async () => {
    const mod = await import('leaflet');
    return mod.default;
  }, []);

  // Parse bbox from URL params
  const getBBoxFromParams = useCallback((): BBox | null => {
    const type = searchParams.get('include_filters[geo][type]');
    if (type !== 'bbox') return null;

    const topLeftLat = searchParams.get('include_filters[geo][top_left][lat]');
    const topLeftLon = searchParams.get('include_filters[geo][top_left][lon]');
    const bottomRightLat = searchParams.get(
      'include_filters[geo][bottom_right][lat]'
    );
    const bottomRightLon = searchParams.get(
      'include_filters[geo][bottom_right][lon]'
    );

    if (topLeftLat && topLeftLon && bottomRightLat && bottomRightLon) {
      return {
        topLeft: {
          lat: parseFloat(topLeftLat),
          lon: parseFloat(topLeftLon),
        },
        bottomRight: {
          lat: parseFloat(bottomRightLat),
          lon: parseFloat(bottomRightLon),
        },
      };
    }
    return null;
  }, [searchParams]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const startTime = performance.now();
    debugLog(
      '🗺️ MapView useEffect triggered with',
      results?.length || 0,
      'results'
    );

    if (!mapContainer.current) {
      debugLog('⏭️ No map container, skipping');
      return;
    }

    // Initialize map if it doesn't exist
    if (!mapRef.current) {
      debugLog('🏗️ Initializing new map...');
      void (async () => {
        const L = await loadLeaflet();
        if (!mapContainer.current) return;
        if (mapRef.current) return;
        mapRef.current = L.map(mapContainer.current).setView(
          [39.8283, -98.5795],
          3
        );
        basemapCleanupRef.current = attachBasemapSwitcher(mapRef.current, L);
        debugLog('✅ Map initialized');
      })();
    }

    // Clear existing result layer (but preserve filter rectangle)
    if (resultLayerRef.current && mapRef.current) {
      mapRef.current.removeLayer(resultLayerRef.current);
      resultLayerRef.current = null;
    }

    // Always render if we have results
    if (results && results.length > 0) {
      debugLog('🎯 Rendering map with', results.length, 'results');

      // Add GeoJSON features for each result
      const features = results
        .filter((result) => result.meta?.ui?.viewer?.geometry)
        .map((result) => ({
          type: 'Feature' as const,
          geometry: result.meta!.ui!.viewer!.geometry,
          properties: {
            id: result.id,
            title: result.attributes.ogm.dct_title_s,
          },
        }));

      if (features.length > 0) {
        debugLog('📍 Adding', features.length, 'features to map...');
        void (async () => {
          const L = await loadLeaflet();
          if (!mapRef.current) return;
          const geoJsonLayer = L.geoJSON(
            {
              type: 'FeatureCollection' as const,
              features: features,
            } as unknown as GeoJSON.GeoJsonObject,
            {
              style: {
                color: '#2563eb',
                weight: 2,
                opacity: 0.6,
                fillOpacity: 0.1,
              },
              onEachFeature: (feature, layer) => {
                layer.bindPopup(feature.properties.title);
              },
            }
          ).addTo(mapRef.current);

          resultLayerRef.current = geoJsonLayer;

          // Fit bounds to show all features or geo filter, whichever is more appropriate
          const bbox = getBBoxFromParams();
          if (bbox && filterRectRef.current) {
            // If there's a geo filter, show both the filter area and the results
            const resultBounds = geoJsonLayer.getBounds();
            const filterBounds = filterRectRef.current.getBounds();
            // Fit to the union of both bounds
            const combinedBounds = resultBounds.extend(filterBounds);
            mapRef.current.fitBounds(combinedBounds, { padding: [20, 20] });
          } else {
            // No filter, just fit to results
            mapRef.current.fitBounds(geoJsonLayer.getBounds());
          }

          const endTime = performance.now();
          debugLog(
            `✅ Map rendered in ${(endTime - startTime).toFixed(2)}ms with ${features.length} features`
          );
        })();
      }
    } else {
      debugLog('⏭️ No results to render');
    }

    return () => {
      // Cleanup on unmount: remove map and clear layer refs so next run doesn't call removeLayer on null
      basemapCleanupRef.current?.();
      basemapCleanupRef.current = null;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      resultLayerRef.current = null;
      filterRectRef.current = null;
      highlightLayerRef.current = null;
    };
  }, [results, getBBoxFromParams, loadLeaflet]);

  // Display geo filter bbox on map and pan/zoom to it
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!mapRef.current) return;

    const bbox = getBBoxFromParams();

    // Clear existing filter rectangle
    if (filterRectRef.current && mapRef.current) {
      mapRef.current.removeLayer(filterRectRef.current);
      filterRectRef.current = null;
    }

    // Add filter bbox as a rectangle if it exists
    if (bbox) {
      try {
        isUpdatingFromParamsRef.current = true;
        void (async () => {
          const L = await loadLeaflet();
          if (!mapRef.current) return;
          const filterBounds = L.latLngBounds(
            [bbox.bottomRight.lat, bbox.topLeft.lon], // Southwest
            [bbox.topLeft.lat, bbox.bottomRight.lon] // Northeast
          );

          // Create a rectangle for the filter area
          const filterRect = L.rectangle(filterBounds, {
            color: '#ef4444',
            weight: 2,
            opacity: 0.8,
            fillColor: '#ef4444',
            fillOpacity: 0.1,
            dashArray: '10, 5',
          }).addTo(mapRef.current);

          filterRectRef.current = filterRect;

          // Pan and zoom to show the filter area
          // If we have results, show both; otherwise just show the filter
          if (resultLayerRef.current) {
            // Combine filter bounds with result bounds
            const resultBounds = resultLayerRef.current.getBounds();
            const combinedBounds = filterBounds.extend(resultBounds);
            mapRef.current.fitBounds(combinedBounds, { padding: [20, 20] });
          } else {
            // No results, just show the filter area
            mapRef.current.fitBounds(filterBounds, { padding: [20, 20] });
          }

          setTimeout(() => {
            isUpdatingFromParamsRef.current = false;
          }, 100);
        })();
      } catch (error) {
        console.error('Error displaying geo filter:', error);
        isUpdatingFromParamsRef.current = false;
      }
    }
  }, [getBBoxFromParams, loadLeaflet]);

  useEffect(() => {
    if (!mapRef.current) return;

    // Clear existing highlight
    if (highlightLayerRef.current && mapRef.current) {
      mapRef.current.removeLayer(highlightLayerRef.current);
      highlightLayerRef.current = null;
    }

    // Add new highlight if there's a hovered geometry
    if (hoveredGeometry) {
      void (async () => {
        try {
          const L = await loadLeaflet();
          if (!mapRef.current) return;
          const parsedGeometry = JSON.parse(hoveredGeometry);
          if (!isValidGeoJsonForLeaflet(parsedGeometry)) return;
          highlightLayerRef.current = L.geoJSON(parsedGeometry, {
            style: {
              color: '#2563eb',
              weight: 3,
              opacity: 1,
              fillOpacity: 0.3,
              fillColor: '#3b82f6',
            },
          }).addTo(mapRef.current);

          // Fit bounds to the highlighted feature
          mapRef.current.fitBounds(highlightLayerRef.current.getBounds(), {
            padding: [50, 50],
          });
        } catch (error) {
          console.error('Error highlighting geometry:', error);
        }
      })();
    }
  }, [hoveredGeometry, loadLeaflet]);

  return (
    <div className="sticky top-[88px]">
      <div
        ref={mapContainer}
        className="h-[calc(100vh-120px)] w-full rounded-lg shadow-md"
      />
    </div>
  );
}
