import { useEffect, useRef, useCallback, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useSearchParams } from "react-router";
import { Search } from "lucide-react";
import { cellToBoundary } from "h3-js";
import { fetchMapH3 } from "../../services/api";
import { formatCount } from "../../utils/formatNumber";

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
  "#DBEAFE", "#BFDBFE", "#93C5FD", "#7AB3FD", "#60A5FA",
  "#3B82F6", "#2563EB", "#1D4ED8", "#1E40AF", "#003C5B",
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
  return L.latLngBounds(
    [minLat, minLng],
    [maxLat, maxLng],
  );
}

interface BBox {
  topLeft: { lat: number; lon: number };
  bottomRight: { lat: number; lon: number };
}

export function GeospatialFilterMap() {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const isUpdatingFromParamsRef = useRef(false);
  const selectedPlaceGeoJsonRef = useRef<L.GeoJSON | null>(null);
  const bboxRectangleRef = useRef<L.Rectangle | null>(null);
  const [showSearchButton, setShowSearchButton] = useState(false);
  const previewRectangleRef = useRef<L.Rectangle | null>(null);
  const hexLayerRef = useRef<L.GeoJSON | null>(null);

  // Parse bbox from URL params
  const getBBoxFromParams = useCallback((): BBox | null => {
    const type = searchParams.get("include_filters[geo][type]");
    if (type !== "bbox") return null;

    const topLeftLat = searchParams.get("include_filters[geo][top_left][lat]");
    const topLeftLon = searchParams.get("include_filters[geo][top_left][lon]");
    const bottomRightLat = searchParams.get(
      "include_filters[geo][bottom_right][lat]",
    );
    const bottomRightLon = searchParams.get(
      "include_filters[geo][bottom_right][lon]",
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
      });

      L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
      }).addTo(mapRef.current);

      // Set initial view to world
      mapRef.current.setView([20, 0], 1);

      // Invalidate size to ensure tiles render properly after container is ready
      // Use requestAnimationFrame to ensure DOM is fully rendered
      requestAnimationFrame(() => {
        setTimeout(() => {
          if (mapRef.current && mapContainerRef.current) {
            // Check if container is visible
            const rect = mapContainerRef.current.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
              mapRef.current.invalidateSize();
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
          color: "#3b82f6",
          weight: 2,
          opacity: 0.6,
          fillColor: "#3b82f6",
          fillOpacity: 0.15,
          dashArray: "5, 5", // Dashed line to indicate preview
        }).addTo(mapRef.current);

        previewRectangleRef.current = previewRectangle;

        // Show the "Search here" button
        setShowSearchButton(true);
      };

      mapRef.current.on("moveend", handleMapMoveEnd);
      mapRef.current.on("zoomend", handleMapMoveEnd);
    }

    return () => {
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
            [bbox.topLeft.lat, bbox.bottomRight.lon], // Northeast (north lat, east lon)
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
              color: "#2563eb",
              weight: 2,
              opacity: 0.8,
              fillColor: "#2563eb",
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
          console.error("Error setting map bounds from params:", error);
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

      // Show world view only if zoomed out
      if (mapRef.current.getZoom() < 1) {
        isUpdatingFromParamsRef.current = true;
        mapRef.current.setView([20, 0], 1);
        setTimeout(() => {
          isUpdatingFromParamsRef.current = false;
        }, 100);
      }
    }
  }, [getBBoxFromParams]);

  // Handle visibility changes (e.g., when details element opens)
  useEffect(() => {
    if (!mapRef.current || !mapContainerRef.current) return;

    // Use IntersectionObserver to detect when container becomes visible
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && mapRef.current) {
            // Container is visible, invalidate size to ensure tiles load
            setTimeout(() => {
              if (mapRef.current) {
                mapRef.current.invalidateSize();
              }
            }, 100);
          }
        });
      },
      { threshold: 0.1 },
    );

    observer.observe(mapContainerRef.current);

    return () => {
      observer.disconnect();
    };
  }, []);

  // H3 hex layer: fetch hexes for current view and add GeoJSON layer; fit to hex cluster when search changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    let cancelled = false;
    const query = searchParams.get("q") ?? "";

    const updateHexLayer = async (shouldFitToHexes: boolean) => {
      const bounds = map.getBounds();
      const zoom = map.getZoom();
      const bbox = clampBbox(
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      );
      const resolution = zoomToResolution(zoom);
      const queryString =
        typeof window !== "undefined" ? window.location.search.slice(1) : "";

      try {
        const res = await fetchMapH3(
          query,
          bbox,
          resolution,
          queryString ? `?${queryString}` : undefined,
        );
        if (cancelled) return;

        if (hexLayerRef.current && map.hasLayer(hexLayerRef.current)) {
          map.removeLayer(hexLayerRef.current);
          hexLayerRef.current = null;
        }
        if (!res.hexes.length) return;

        const maxCount = Math.max(...res.hexes.map((h) => h.count), 1);
        const features = res.hexes.map((h) => {
          const vs = cellToBoundary(h.h3);
          const ring = vs.map(
            ([lat, lng]: [number, number]) => [lng, lat] as [number, number],
          );
          ring.push(ring[0]);
          return {
            type: "Feature" as const,
            properties: { h3: h.h3, count: h.count },
            geometry: {
              type: "Polygon" as const,
              coordinates: [ring],
            },
          };
        });
        const fc = { type: "FeatureCollection" as const, features };

        const layer = L.geoJSON(fc, {
          style: (feature) => {
            const c =
              (feature?.properties as { count?: number })?.count ?? 0;
            const intensity = c / maxCount;
            return {
              fillColor: getHexColor(intensity),
              weight: 1,
              opacity: 1,
              color: "white",
              fillOpacity: 0.7,
            };
          },
          onEachFeature: (feature, layer) => {
            const count =
              (feature?.properties as { count?: number })?.count ?? 0;
            const h3 = (feature?.properties as { h3?: string })?.h3 ?? "";
            const res = zoomToResolution(map.getZoom());
            // Preserve current search params and add/update only the H3 filter
            const params = new URLSearchParams(searchParams.toString());
            Array.from(params.keys())
              .filter((key) => key.startsWith("include_filters[h3_res"))
              .forEach((key) => params.delete(key));
            params.set(`include_filters[h3_res${res}][]`, h3);
            params.delete("page");
            const searchUrl = `/search?${params.toString()}`;
            layer.bindPopup(
              `<div class="map-hex-popup"><h3 class="text-sm font-semibold mb-1">H3 ${h3}</h3><p class="text-sm mb-2"><strong>Resources:</strong> ${formatCount(count)}</p><a href="${searchUrl}" class="text-blue-600 hover:underline text-sm">Search this hex</a></div>`,
            );
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
      }
    };

    updateHexLayer(true);
    const onMoveOrZoom = () => updateHexLayer(false);
    map.on("moveend", onMoveOrZoom);
    map.on("zoomend", onMoveOrZoom);

    return () => {
      cancelled = true;
      map.off("moveend", onMoveOrZoom);
      map.off("zoomend", onMoveOrZoom);
      if (hexLayerRef.current && map.hasLayer(hexLayerRef.current)) {
        map.removeLayer(hexLayerRef.current);
        hexLayerRef.current = null;
      }
    };
  }, [searchParams]);

  const handleSearchHere = () => {
    if (!mapRef.current) return;

    const bounds = mapRef.current.getBounds();
    const newParams = new URLSearchParams(searchParams);

    // Remove existing geo filters
    Array.from(newParams.keys())
      .filter((key) => key.startsWith("include_filters[geo]"))
      .forEach((key) => newParams.delete(key));

    // Add new bbox filter from current map bounds
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();

    // Top-left is northwest corner (north = higher lat, west = lower lon)
    // Bottom-right is southeast corner (south = lower lat, east = higher lon)
    newParams.set("include_filters[geo][type]", "bbox");
    newParams.set("include_filters[geo][field]", "dcat_bbox");
    newParams.set("include_filters[geo][top_left][lat]", ne.lat.toString());
    newParams.set("include_filters[geo][top_left][lon]", sw.lng.toString());
    newParams.set("include_filters[geo][bottom_right][lat]", sw.lat.toString());
    newParams.set("include_filters[geo][bottom_right][lon]", ne.lng.toString());

    // Reset to page 1 when bbox changes
    newParams.delete("page");

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
      .filter((key) => key.startsWith("include_filters[geo]"))
      .forEach((key) => newParams.delete(key));
    newParams.delete("page");
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

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-gray-900">Location</h3>
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
      <div className="relative">
        <div
          ref={mapContainerRef}
          className="w-full rounded-lg border border-gray-200"
          style={{ height: "200px", minHeight: "200px" }}
        />
        {showSearchButton && (
          <button
            onClick={handleSearchHere}
            className="absolute top-2 right-2 z-[1000] flex items-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
            aria-label="Search in this area"
          >
            <Search className="w-4 h-4" />
            <span>Search here</span>
          </button>
        )}
      </div>
    </div>
  );
}

export default GeospatialFilterMap;

