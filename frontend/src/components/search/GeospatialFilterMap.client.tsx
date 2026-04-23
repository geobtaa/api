import { useEffect, useRef, useCallback, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useSearchParams } from 'react-router';
import { cellToBoundary } from 'h3-js';
import { fetchMapH3 } from '../../services/api';
import { HexLayerToggleControl } from '../map/HexLayerToggleControl';
import { MapGeosearchControl } from '../map/MapGeosearchControl';
import { attachBasemapSwitcher } from '../../config/basemaps';
import {
  getSavedHexLayerEnabled,
  saveHexLayerEnabled,
} from '../../utils/hexLayerPreference';

function zoomToResolution(zoom: number): number {
  if (zoom <= 3) return 2;
  if (zoom <= 4) return 3;
  if (zoom <= 6) return 4;
  if (zoom <= 8) return 5;
  if (zoom <= 10) return 6;
  if (zoom <= 12) return 7;
  return 8;
}

function clampBbox(
  west: number,
  south: number,
  east: number,
  north: number
): string {
  const clampLon = (x: number) => Math.max(-180, Math.min(180, x));
  const clampLat = (x: number) => Math.max(-90, Math.min(90, x));
  return `${clampLon(west)},${clampLat(south)},${clampLon(east)},${clampLat(north)}`;
}

/** 10-step blue ramp (light to dark) for resource density. */
const HEX_RAMP_COLORS = [
  '#DBEAFE',
  '#BFDBFE',
  '#93C5FD',
  '#7AB3FD',
  '#60A5FA',
  '#3B82F6',
  '#2563EB',
  '#1D4ED8',
  '#1E40AF',
  '#003C5B',
];
const HEX_RAMP_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

function getHexColor(intensity: number): string {
  for (let i = 0; i < HEX_RAMP_THRESHOLDS.length; i++) {
    if (intensity <= HEX_RAMP_THRESHOLDS[i]) return HEX_RAMP_COLORS[i];
  }
  return HEX_RAMP_COLORS[HEX_RAMP_COLORS.length - 1];
}

/** Return Leaflet LatLngBounds that encompass all given H3 cells, or null if empty. */
function boundsOfHexes(hexIndexes: string[]): L.LatLngBounds | null {
  if (hexIndexes.length === 0) return null;
  let minLat = 90;
  let maxLat = -90;
  let minLng = 180;
  let maxLng = -180;
  for (const h3 of hexIndexes) {
    const vs = cellToBoundary(h3);
    for (const [lat, lng] of vs) {
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLng = Math.min(minLng, lng);
      maxLng = Math.max(maxLng, lng);
    }
  }
  if (minLat > maxLat || minLng > maxLng) return null;
  return L.latLngBounds([minLat, minLng], [maxLat, maxLng]);
}

interface BBox {
  topLeft: { lat: number; lon: number };
  bottomRight: { lat: number; lon: number };
}

type BBoxRelationMode = 'intersects' | 'within';

interface GeospatialFilterMapProps {
  /** When true, hide the "Location" heading and Clear button (e.g. when used inside LocationFacetCollapsible). */
  hideHeading?: boolean;
}

export function GeospatialFilterMap({
  hideHeading = false,
}: GeospatialFilterMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const isUpdatingFromParamsRef = useRef(false);
  const selectedPlaceGeoJsonRef = useRef<L.GeoJSON | null>(null);
  const bboxRectangleRef = useRef<L.Rectangle | null>(null);
  const [showSearchButton, setShowSearchButton] = useState(false);
  const previewRectangleRef = useRef<L.Rectangle | null>(null);
  const hexLayerRef = useRef<L.GeoJSON | null>(null);
  const basemapCleanupRef = useRef<(() => void) | null>(null);
  const lastAutoFitSearchKeyRef = useRef<string | null>(null);
  const [hexesInView, setHexesInView] = useState<
    Array<{ h3: string; count: number }>
  >([]);
  const [hexResolution, setHexResolution] = useState(6);
  const [hexLoading, setHexLoading] = useState(false);
  const [hexLayerEnabled, setHexLayerEnabled] = useState(
    getSavedHexLayerEnabled
  );

  const getRelationFromParams = useCallback((): BBoxRelationMode => {
    const relation = searchParams.get('include_filters[geo][relation]');
    if (relation === 'within') return 'within';
    return 'intersects';
  }, [searchParams]);

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
          lat: Number.parseFloat(topLeftLat),
          lon: Number.parseFloat(topLeftLon),
        },
        bottomRight: {
          lat: Number.parseFloat(bottomRightLat),
          lon: Number.parseFloat(bottomRightLon),
        },
      };
    }
    return null;
  }, [searchParams]);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        zoomControl: true,
        attributionControl: false,
        minZoom: 1,
      });
      setMapInstance(mapRef.current);
      basemapCleanupRef.current = attachBasemapSwitcher(mapRef.current, L);

      // Set initial view: if URL has a location bbox, fit to it; otherwise world
      const initialBbox = getBBoxFromParams();
      if (initialBbox) {
        const bounds = L.latLngBounds(
          [initialBbox.bottomRight.lat, initialBbox.topLeft.lon],
          [initialBbox.topLeft.lat, initialBbox.bottomRight.lon]
        );
        if (bounds.isValid()) {
          mapRef.current.fitBounds(bounds, { padding: [20, 20] });
          bboxRectangleRef.current = L.rectangle(bounds, {
            color: '#2563eb',
            weight: 2,
            opacity: 0.8,
            fillColor: '#2563eb',
            fillOpacity: 0.2,
          }).addTo(mapRef.current);
        } else {
          mapRef.current.setView([20, 0], 1);
        }
      } else {
        mapRef.current.setView([20, 0], 1);
      }

      // Invalidate size to ensure tiles render properly after container is ready
      // Use requestAnimationFrame to ensure DOM is fully rendered
      requestAnimationFrame(() => {
        setTimeout(() => {
          if (mapRef.current && mapContainerRef.current) {
            // Check if container is visible
            const rect = mapContainerRef.current.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
              mapRef.current.invalidateSize();
              // If we have a bbox in URL, re-fit so bounds are correct after layout
              const bbox = getBBoxFromParams();
              if (bbox) {
                const bounds = L.latLngBounds(
                  [bbox.bottomRight.lat, bbox.topLeft.lon],
                  [bbox.topLeft.lat, bbox.bottomRight.lon]
                );
                if (bounds.isValid()) {
                  isUpdatingFromParamsRef.current = true;
                  mapRef.current.fitBounds(bounds, { padding: [20, 20] });
                  setTimeout(() => {
                    isUpdatingFromParamsRef.current = false;
                  }, 500);
                }
              }
            } else {
              // If not visible yet, try again after a delay
              setTimeout(() => {
                if (mapRef.current) {
                  mapRef.current.invalidateSize();
                }
              }, 300);
            }
          }
        }, 100);
      });

      // Handle map move/zoom events - show preview rectangle and "Search here" button
      const handleMapMoveEnd = () => {
        if (isUpdatingFromParamsRef.current) return;
        if (!mapRef.current) return;

        const bounds = mapRef.current.getBounds();

        // Clear place geometry when user manually moves the map
        if (selectedPlaceGeoJsonRef.current) {
          mapRef.current.removeLayer(selectedPlaceGeoJsonRef.current);
          selectedPlaceGeoJsonRef.current = null;
        }

        // Remove existing preview rectangle if it exists
        if (previewRectangleRef.current) {
          mapRef.current.removeLayer(previewRectangleRef.current);
          previewRectangleRef.current = null;
        }

        // Add preview rectangle to show what area would be searched
        // Use a different style to indicate it's a preview (not yet applied)
        const previewRectangle = L.rectangle(bounds, {
          color: '#3b82f6',
          weight: 2,
          opacity: 0.6,
          fillColor: '#3b82f6',
          fillOpacity: 0.15,
          dashArray: '5, 5', // Dashed line to indicate preview
        }).addTo(mapRef.current);

        previewRectangleRef.current = previewRectangle;

        // Show the "Search here" button
        setShowSearchButton(true);
      };

      mapRef.current.on('moveend', handleMapMoveEnd);
      mapRef.current.on('zoomend', handleMapMoveEnd);
    }

    return () => {
      setMapInstance(null);
      basemapCleanupRef.current?.();
      basemapCleanupRef.current = null;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [setSearchParams]);

  // Update map view from URL params
  // This handles cases where bbox params are set programmatically (e.g., from autocomplete)
  // or when the page loads with bbox params already in the URL
  useEffect(() => {
    if (!mapRef.current) return;

    const bbox = getBBoxFromParams();
    if (bbox) {
      // Always update map bounds when bbox params change
      // Use a small delay to ensure map is ready and to batch updates
      const timeoutId = setTimeout(() => {
        if (!mapRef.current) return;

        isUpdatingFromParamsRef.current = true;
        try {
          // Invalidate size to ensure map is properly rendered
          mapRef.current.invalidateSize();

          // Reconstruct bounds from bbox
          // top_left is northwest (higher lat, lower lon)
          // bottom_right is southeast (lower lat, higher lon)
          const bounds = L.latLngBounds(
            [bbox.bottomRight.lat, bbox.topLeft.lon], // Southwest (south lat, west lon)
            [bbox.topLeft.lat, bbox.bottomRight.lon] // Northeast (north lat, east lon)
          );

          if (bounds && bounds.isValid()) {
            // Remove existing rectangles if they exist
            if (bboxRectangleRef.current) {
              mapRef.current.removeLayer(bboxRectangleRef.current);
              bboxRectangleRef.current = null;
            }
            if (previewRectangleRef.current) {
              mapRef.current.removeLayer(previewRectangleRef.current);
              previewRectangleRef.current = null;
            }

            // Add rectangle overlay to visualize the active bbox filter
            const rectangle = L.rectangle(bounds, {
              color: '#2563eb',
              weight: 2,
              opacity: 0.8,
              fillColor: '#2563eb',
              fillOpacity: 0.2,
            }).addTo(mapRef.current);

            bboxRectangleRef.current = rectangle;

            // Hide search button when bbox is set from URL (not from user interaction)
            setShowSearchButton(false);

            // Fit map to bounds with padding, but keep the flag set longer
            // to prevent moveend from overwriting the bbox
            mapRef.current.fitBounds(bounds, { padding: [20, 20] });

            // Keep flag set longer to prevent moveend from firing and overwriting
            setTimeout(() => {
              isUpdatingFromParamsRef.current = false;
            }, 1000); // Longer delay to ensure moveend doesn't fire
            return; // Early return to skip the setTimeout below
          }
        } catch (error) {
          console.error('Error setting map bounds from params:', error);
          isUpdatingFromParamsRef.current = false;
        }
        // Only reset flag if we didn't already set it above
        if (isUpdatingFromParamsRef.current) {
          setTimeout(() => {
            isUpdatingFromParamsRef.current = false;
          }, 1000);
        }
      }, 50);

      return () => clearTimeout(timeoutId);
    } else {
      // No bbox in params, remove rectangle overlays if they exist
      if (bboxRectangleRef.current && mapRef.current) {
        mapRef.current.removeLayer(bboxRectangleRef.current);
        bboxRectangleRef.current = null;
      }
      if (previewRectangleRef.current && mapRef.current) {
        mapRef.current.removeLayer(previewRectangleRef.current);
        previewRectangleRef.current = null;
      }

      // Hide search button when bbox is cleared
      setShowSearchButton(false);

      // Show world view only if zoomed out past minZoom
      if (mapRef.current.getZoom() < 1) {
        isUpdatingFromParamsRef.current = true;
        mapRef.current.setView([20, 0], 1);
        setTimeout(() => {
          isUpdatingFromParamsRef.current = false;
        }, 100);
      }
    }
  }, [getBBoxFromParams]);

  useEffect(() => {
    saveHexLayerEnabled(hexLayerEnabled);
  }, [hexLayerEnabled]);

  // Handle visibility changes (e.g., when details element opens); also fit to bbox if map was created with zero size
  useEffect(() => {
    if (!mapRef.current || !mapContainerRef.current) return;

    const fitToBboxIfNeeded = () => {
      const bbox = getBBoxFromParams();
      if (!bbox || !mapRef.current) return;
      const bounds = L.latLngBounds(
        [bbox.bottomRight.lat, bbox.topLeft.lon],
        [bbox.topLeft.lat, bbox.bottomRight.lon]
      );
      if (!bounds.isValid()) return;
      const zoom = mapRef.current.getZoom();
      if (zoom <= 2) {
        isUpdatingFromParamsRef.current = true;
        mapRef.current.fitBounds(bounds, { padding: [20, 20] });
        if (!bboxRectangleRef.current) {
          bboxRectangleRef.current = L.rectangle(bounds, {
            color: '#2563eb',
            weight: 2,
            opacity: 0.8,
            fillColor: '#2563eb',
            fillOpacity: 0.2,
          }).addTo(mapRef.current);
        }
        setTimeout(() => {
          isUpdatingFromParamsRef.current = false;
        }, 500);
      }
    };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && mapRef.current) {
            setTimeout(() => {
              if (mapRef.current) {
                mapRef.current.invalidateSize();
                fitToBboxIfNeeded();
              }
            }, 100);
          }
        });
      },
      { threshold: 0.1 }
    );

    observer.observe(mapContainerRef.current);

    return () => {
      observer.disconnect();
    };
  }, [getBBoxFromParams]);

  // H3 hex layer: fetch hexes for current view and add GeoJSON layer; fit to hex cluster when search changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (!hexLayerEnabled) {
      if (hexLayerRef.current && map.hasLayer(hexLayerRef.current)) {
        map.removeLayer(hexLayerRef.current);
        hexLayerRef.current = null;
      }
      setHexLoading(false);
      return;
    }

    let cancelled = false;
    const query = searchParams.get('q') ?? '';
    const searchKey = searchParams.toString();
    const hasActiveBBox = getBBoxFromParams() !== null;
    const shouldAutoFitInitialHexes =
      !hasActiveBBox && lastAutoFitSearchKeyRef.current !== searchKey;

    const updateHexLayer = async (shouldFitToHexes: boolean) => {
      const bounds = map.getBounds();
      const zoom = map.getZoom();
      const bbox = clampBbox(
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth()
      );
      const resolution = zoomToResolution(zoom);
      const queryString =
        typeof window !== 'undefined' ? window.location.search.slice(1) : '';

      setHexLoading(true);
      try {
        const res = await fetchMapH3(
          query,
          bbox,
          resolution,
          queryString ? `?${queryString}` : undefined
        );
        if (cancelled) return;

        if (shouldFitToHexes) {
          lastAutoFitSearchKeyRef.current = searchKey;
        }

        setHexesInView(res.hexes);
        setHexResolution(resolution);

        if (hexLayerRef.current && map.hasLayer(hexLayerRef.current)) {
          map.removeLayer(hexLayerRef.current);
          hexLayerRef.current = null;
        }
        if (!res.hexes.length) {
          setHexLoading(false);
          return;
        }

        const maxCount = Math.max(...res.hexes.map((h) => h.count), 1);
        const features = res.hexes.map((h) => {
          const vs = cellToBoundary(h.h3);
          const ring = vs.map(
            ([lat, lng]: [number, number]) => [lng, lat] as [number, number]
          );
          ring.push(ring[0]);
          return {
            type: 'Feature' as const,
            properties: { h3: h.h3, count: h.count },
            geometry: {
              type: 'Polygon' as const,
              coordinates: [ring],
            },
          };
        });
        const fc = { type: 'FeatureCollection' as const, features };

        const layer = L.geoJSON(fc, {
          style: (feature) => {
            const c = (feature?.properties as { count?: number })?.count ?? 0;
            const intensity =
              maxCount > 0 ? Math.log(c + 1) / Math.log(maxCount + 1) : 0;
            return {
              fillColor: getHexColor(intensity),
              weight: 1,
              opacity: 1,
              color: 'white',
              fillOpacity: 0.7,
            };
          },
          onEachFeature: () => {
            // No popup on search map hexes
          },
        });
        layer.addTo(map);
        hexLayerRef.current = layer;

        if (shouldFitToHexes && res.hexes.length > 0) {
          const hexBounds = boundsOfHexes(res.hexes.map((h) => h.h3));
          if (hexBounds && hexBounds.isValid()) {
            isUpdatingFromParamsRef.current = true;
            map.fitBounds(hexBounds, { padding: [24, 24], maxZoom: 14 });
            setTimeout(() => {
              isUpdatingFromParamsRef.current = false;
            }, 600);
          }
        }
      } catch {
        // ignore fetch errors
      } finally {
        if (!cancelled) setHexLoading(false);
      }
    };

    let initialFetchTimeout: number | null = null;
    let initialIdleCallbackId: number | null = null;

    const scheduleInitialHexFetch = () => {
      const run = () => {
        initialFetchTimeout = window.setTimeout(() => {
          void updateHexLayer(shouldAutoFitInitialHexes);
        }, 250);
      };

      if ('requestIdleCallback' in window) {
        initialIdleCallbackId = window.requestIdleCallback(run, {
          timeout: 2000,
        });
        return;
      }

      run();
    };

    if (document.readyState === 'complete') {
      scheduleInitialHexFetch();
    } else {
      window.addEventListener('load', scheduleInitialHexFetch, { once: true });
    }

    const onMoveOrZoom = () => updateHexLayer(false);
    map.on('moveend', onMoveOrZoom);
    map.on('zoomend', onMoveOrZoom);

    return () => {
      cancelled = true;
      window.removeEventListener('load', scheduleInitialHexFetch);
      if (initialFetchTimeout !== null) {
        window.clearTimeout(initialFetchTimeout);
      }
      if (
        initialIdleCallbackId !== null &&
        'cancelIdleCallback' in window &&
        typeof window.cancelIdleCallback === 'function'
      ) {
        window.cancelIdleCallback(initialIdleCallbackId);
      }
      map.off('moveend', onMoveOrZoom);
      map.off('zoomend', onMoveOrZoom);
      if (hexLayerRef.current && map.hasLayer(hexLayerRef.current)) {
        map.removeLayer(hexLayerRef.current);
        hexLayerRef.current = null;
      }
    };
  }, [searchParams, hexLayerEnabled]);

  const handleSearchHere = () => {
    if (!mapRef.current) return;

    const bounds = mapRef.current.getBounds();
    const newParams = new URLSearchParams(searchParams);
    const relation = getRelationFromParams();

    // Remove existing geo filters
    Array.from(newParams.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => newParams.delete(key));

    // Add new bbox filter from current map bounds
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();

    // Top-left is northwest corner (north = higher lat, west = lower lon)
    // Bottom-right is southeast corner (south = lower lat, east = higher lon)
    newParams.set('include_filters[geo][type]', 'bbox');
    newParams.set('include_filters[geo][field]', 'dcat_bbox');
    newParams.set('include_filters[geo][relation]', relation);
    newParams.set('include_filters[geo][top_left][lat]', ne.lat.toString());
    newParams.set('include_filters[geo][top_left][lon]', sw.lng.toString());
    newParams.set('include_filters[geo][bottom_right][lat]', sw.lat.toString());
    newParams.set('include_filters[geo][bottom_right][lon]', ne.lng.toString());

    // Reset to page 1 when bbox changes
    newParams.delete('page');

    setSearchParams(newParams);

    // Hide the search button (it will show again if user moves map)
    setShowSearchButton(false);

    // Remove preview rectangle and it will be replaced by the active bbox rectangle
    if (previewRectangleRef.current && mapRef.current) {
      mapRef.current.removeLayer(previewRectangleRef.current);
      previewRectangleRef.current = null;
    }
  };

  const handleClearBBox = () => {
    // Clear place geometry
    if (selectedPlaceGeoJsonRef.current && mapRef.current) {
      mapRef.current.removeLayer(selectedPlaceGeoJsonRef.current);
      selectedPlaceGeoJsonRef.current = null;
    }

    // Clear bbox rectangle overlay
    if (bboxRectangleRef.current && mapRef.current) {
      mapRef.current.removeLayer(bboxRectangleRef.current);
      bboxRectangleRef.current = null;
    }

    // Clear preview rectangle
    if (previewRectangleRef.current && mapRef.current) {
      mapRef.current.removeLayer(previewRectangleRef.current);
      previewRectangleRef.current = null;
    }

    // Hide search button
    setShowSearchButton(false);

    const newParams = new URLSearchParams(searchParams);
    Array.from(newParams.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => newParams.delete(key));
    newParams.delete('page');
    setSearchParams(newParams);
  };

  const handleRelationModeChange = (relation: BBoxRelationMode) => {
    if (!hasBBox) return;
    const newParams = new URLSearchParams(searchParams);
    newParams.set('include_filters[geo][relation]', relation);
    newParams.delete('page');
    setSearchParams(newParams);
  };

  // Clear place geometry and bbox rectangle when bbox is cleared
  useEffect(() => {
    const bbox = getBBoxFromParams();
    if (!bbox) {
      if (selectedPlaceGeoJsonRef.current && mapRef.current) {
        mapRef.current.removeLayer(selectedPlaceGeoJsonRef.current);
        selectedPlaceGeoJsonRef.current = null;
      }
      if (bboxRectangleRef.current && mapRef.current) {
        mapRef.current.removeLayer(bboxRectangleRef.current);
        bboxRectangleRef.current = null;
      }
    }
  }, [getBBoxFromParams]);

  const hasBBox = getBBoxFromParams() !== null;
  const relationMode = getRelationFromParams();

  return (
    <div className={hideHeading ? '' : 'mb-6'}>
      {!hideHeading && (
        <div className="flex items-center justify-between mb-1">
          <h3
            id="filter-location-heading"
            className="font-semibold text-gray-950"
            style={{
              color: '#111827',
              backgroundColor: '#ffffff',
              display: 'inline-block',
              paddingInline: '0.25rem',
              borderRadius: '0.125rem',
            }}
          >
            Location
          </h3>
          {hasBBox && (
            <button
              onClick={handleClearBBox}
              className="text-xs text-blue-600 hover:text-blue-800 underline"
              aria-label="Clear location filter"
            >
              Clear
            </button>
          )}
        </div>
      )}
      <div
        className="relative"
        role="group"
        aria-labelledby={hideHeading ? undefined : 'filter-location-heading'}
        aria-label={hideHeading ? 'Location filter map' : undefined}
      >
        {hasBBox && (
          <div className="mb-2">
            <div
              className="inline-flex rounded-md border border-gray-200 bg-white p-0.5"
              role="group"
              aria-label="Map within and overlap toggle"
            >
              <button
                type="button"
                onClick={() => handleRelationModeChange('within')}
                className={`rounded px-2 py-1 text-xs ${
                  relationMode === 'within'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
                aria-label="Set map mode to within"
              >
                Within
              </button>
              <button
                type="button"
                onClick={() => handleRelationModeChange('intersects')}
                className={`rounded px-2 py-1 text-xs ${
                  relationMode === 'intersects'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
                aria-label="Set map mode to overlap"
              >
                Overlap
              </button>
            </div>
          </div>
        )}
        <div className="relative">
          <div
            ref={mapContainerRef}
            className="aspect-square w-full rounded-lg border border-gray-200"
          />
          <MapGeosearchControl mapInstance={mapInstance} />
          {showSearchButton && (
            <button
              onClick={handleSearchHere}
              className="absolute top-2 right-2 z-[1000] flex items-center px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
              aria-label="Search in this area"
            >
              <span>Search here</span>
            </button>
          )}
        </div>
        <HexLayerToggleControl
          mapInstance={mapInstance}
          enabled={hexLayerEnabled}
          hexes={hexesInView}
          resolution={hexResolution}
          searchQuery={searchParams.get('q') ?? ''}
          queryString={searchParams.toString()}
          loading={hexLoading}
          stackOrder="beforeBasemap"
          onToggle={(enabled) => {
            setHexLayerEnabled(enabled);
          }}
        />
      </div>
    </div>
  );
}

export default GeospatialFilterMap;
