import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Search } from "lucide-react";
import { MapContainer, TileLayer, useMap, ZoomControl } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { MapUpdaterHex, type HexHoverData } from "../map/MapUpdaterHex";
import { formatCount } from "../../utils/formatNumber";
import { HOME_PAGE_MAP_CENTER, DEFAULT_US_ZOOM } from "../../config/mapView";

/** One-time pan so Chicago (dense hex cluster) appears in the desired position on the homepage. */
function MapPanner() {
  const map = useMap();
  const panned = useRef(false);
  useEffect(() => {
    if (panned.current) return;
    map.whenReady(() => {
      map.panBy([400, 0], { animate: false });
      panned.current = true;
    });
  }, [map]);
  return null;
}

/** Show "Search here" button when user pans/zooms; on click navigate to search with current map bbox. */
function SearchHereControl() {
  const map = useMap();
  const navigate = useNavigate();
  const [showSearchButton, setShowSearchButton] = useState(false);
  const initialMoveDone = useRef(false);

  useEffect(() => {
    const handleMoveEnd = () => {
      if (!initialMoveDone.current) {
        initialMoveDone.current = true;
        return;
      }
      setShowSearchButton(true);
    };
    map.on("moveend", handleMoveEnd);
    map.on("zoomend", handleMoveEnd);
    return () => {
      map.off("moveend", handleMoveEnd);
      map.off("zoomend", handleMoveEnd);
    };
  }, [map]);

  const handleSearchHere = () => {
    setShowSearchButton(false);
    const bounds = map.getBounds();
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    const params = new URLSearchParams();
    params.set("include_filters[geo][type]", "bbox");
    params.set("include_filters[geo][field]", "dcat_bbox");
    params.set("include_filters[geo][top_left][lat]", ne.lat.toString());
    params.set("include_filters[geo][top_left][lon]", sw.lng.toString());
    params.set("include_filters[geo][bottom_right][lat]", sw.lat.toString());
    params.set("include_filters[geo][bottom_right][lon]", ne.lng.toString());
    navigate(`/search?${params.toString()}`);
  };

  if (!showSearchButton) return null;
  return (
    <div className="absolute top-2 right-2 z-[1000]">
      <button
        type="button"
        onClick={handleSearchHere}
        className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
        aria-label="Search in this area"
      >
        <Search className="w-4 h-4" />
        <span>Search here</span>
      </button>
    </div>
  );
}

/**
 * Non-interactive Leaflet hex map used as the background of the homepage.
 * Center is south of the US so North America appears just under the search form.
 * Hovering a hex shows a glowing blue border and popover at bottom-left.
 */
export function HomePageHexMapBackground() {
  const [hoveredHex, setHoveredHex] = useState<HexHoverData | null>(null);

  return (
    <div className="absolute inset-0 z-0">
      <style>{`.hex-hover-glow { filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.9)); }`}</style>
      <div className="relative h-full w-full">
        <MapContainer
          center={HOME_PAGE_MAP_CENTER}
          zoom={DEFAULT_US_ZOOM}
          className="h-full w-full"
          zoomControl={false}
          dragging={true}
          scrollWheelZoom={false}
          doubleClickZoom={true}
          touchZoom={true}
          keyboard={true}
          attributionControl={false}
        >
          <ZoomControl position="topright" />
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          <MapPanner />
          <SearchHereControl />
          <MapUpdaterHex
            searchQuery=""
            onFeatureClick={() => {}}
            onHexHover={setHoveredHex}
            hoveredHex={hoveredHex}
            queryString={typeof window !== "undefined" ? window.location.search : undefined}
          />
        </MapContainer>
        {hoveredHex && (
          <div
            data-hex-popover
            className="fixed bottom-4 left-4 z-10 max-w-xs rounded-lg bg-white/95 backdrop-blur-sm p-4 shadow-lg border border-gray-200"
            onMouseLeave={() => setHoveredHex(null)}
          >
          <h3 className="text-sm font-semibold text-gray-900 mb-1">
            H3 {hoveredHex.h3}
          </h3>
          <p className="text-sm text-gray-600 mb-3">
            <strong>Resources:</strong> {formatCount(hoveredHex.count)}
          </p>
          <Link
            to={`/search?include_filters[h3_res${hoveredHex.resolution}][]=${encodeURIComponent(hoveredHex.h3)}`}
            className="text-sm text-blue-600 hover:underline"
          >
            Search this hex
          </Link>
          </div>
        )}
      </div>
    </div>
  );
}
