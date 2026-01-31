import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Search } from "lucide-react";
import { MapContainer, Rectangle, TileLayer, useMap, ZoomControl } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { MapUpdaterHex, type HexHoverData } from "../map/MapUpdaterHex";
import { formatCount } from "../../utils/formatNumber";
import { HOME_PAGE_MAP_CENTER, DEFAULT_US_ZOOM } from "../../config/mapView";
import { FEATURED_RESOURCE_IDS } from "../../config/featured";
import { fetchResourceDetails } from "../../services/api";
import type { GeoDocumentDetails } from "../../types/api";
import { getResourceIcon } from "../../utils/resourceIcons";
import { parseBboxToLeafletBounds } from "../../utils/bbox";
import { FeaturedMapController } from "./FeaturedMapController";

/** Route API thumbnail URLs through app paths for SSR/relative requests. */
function toSsrThumbnailUrl(url: string | undefined): string {
  if (!url || typeof url !== "string") return "";
  try {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      const u = new URL(url);
      if (u.pathname.startsWith("/api/v1/thumbnails/")) {
        return u.pathname.replace("/api/v1/thumbnails/", "/thumbnails/") + u.search;
      }
      if (u.pathname.match(/^\/api\/v1\/resources\/[^/]+\/thumbnail$/)) {
        return u.pathname.replace("/api/v1", "") + u.search;
      }
      return url;
    }
    if (url.startsWith("/api/v1/thumbnails/")) {
      return url.replace("/api/v1/thumbnails/", "/thumbnails/");
    }
    const m = url.match(/^\/api\/v1(\/resources\/[^/]+\/thumbnail)/);
    if (m) return m[1];
    return url;
  } catch {
    if (url.includes("/api/v1/thumbnails/")) return url.replace("/api/v1/thumbnails/", "/thumbnails/");
    if (url.includes("/api/v1/resources/") && url.endsWith("/thumbnail")) return url.replace("/api/v1", "");
    return url;
  }
}

/** Tracks user pan/zoom; calls onUserEngaged when map moves and the move was not programmatic (e.g. flyToBounds). */
function MapUserEngagementTracker({
  programmaticFlyRef,
  onUserEngaged,
}: {
  programmaticFlyRef: React.MutableRefObject<boolean>;
  onUserEngaged: () => void;
}) {
  const map = useMap();
  useEffect(() => {
    const handler = () => {
      if (!programmaticFlyRef.current) onUserEngaged();
    };
    map.on("moveend", handler);
    map.on("zoomend", handler);
    return () => {
      map.off("moveend", handler);
      map.off("zoomend", handler);
    };
  }, [map, programmaticFlyRef, onUserEngaged]);
  return null;
}

const FEATURED_BOUNDS_PANE = "featuredBoundsPane";
const FEATURED_ITEM_DURATION_MS = 17_000;
const FEATURED_PROGRESS_TICK_MS = 100;
/** Dark Big Ten blue for progress bar (BTAA primary) */
const DARK_BIG_TEN_BLUE = "#003C5B";

/** Ensures a high-z-index pane exists for the featured bounds rectangle so it draws above hexagons. */
function useFeaturedBoundsPane() {
  const map = useMap();
  useEffect(() => {
    let pane = map.getPane(FEATURED_BOUNDS_PANE);
    if (!pane) {
      pane = map.createPane(FEATURED_BOUNDS_PANE);
      pane.style.setProperty("z-index", "4", "important"); // above overlay-pane (2) so bounds appear on top of hexes
    }
  }, [map]);
}

/** Renders the active featured item's bounding box on the map when featured is initiated and the active item has a bbox. */
function FeaturedItemBoundsLayer({
  activeIndex,
  featuredDetails,
  featuredInitiated,
}: {
  activeIndex: number;
  featuredDetails: (GeoDocumentDetails | null)[];
  featuredInitiated: boolean;
}) {
  useFeaturedBoundsPane();
  const detail = featuredDetails[activeIndex];
  const bboxStr = detail?.attributes?.ogm?.dcat_bbox;
  const bounds = parseBboxToLeafletBounds(bboxStr);

  if (!featuredInitiated || !bounds) return null;

  return (
    <Rectangle
      bounds={bounds}
      pathOptions={{
        pane: FEATURED_BOUNDS_PANE,
        color: "#2563eb",
        weight: 2,
        fillColor: "#3b82f6",
        fillOpacity: 0.15,
      }}
    />
  );
}

/** One-time pan so Chicago (dense hex cluster) appears in the desired position on the homepage. Marks as programmatic so it is not counted as user engagement. */
function MapPanner({
  programmaticFlyRef,
}: {
  programmaticFlyRef: React.MutableRefObject<boolean>;
}) {
  const map = useMap();
  const panned = useRef(false);
  useEffect(() => {
    if (panned.current) return;
    map.whenReady(() => {
      programmaticFlyRef.current = true;
      map.panBy([400, 0], { animate: false });
      panned.current = true;
      const onMoveEnd = () => {
        programmaticFlyRef.current = false;
        map.off("moveend", onMoveEnd);
      };
      map.on("moveend", onMoveEnd);
    });
  }, [map, programmaticFlyRef]);
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
 * Featured resources carousel at bottom; when an item is active, map flies to its bbox and a popup shows thumbnail and link.
 */
export function HomePageHexMapBackground() {
  const [hoveredHex, setHoveredHex] = useState<HexHoverData | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [featuredDetails, setFeaturedDetails] = useState<(GeoDocumentDetails | null)[]>(() =>
    FEATURED_RESOURCE_IDS.map(() => null)
  );
  const [featuredInitiated, setFeaturedInitiated] = useState(false);
  const [userEngagedMap, setUserEngagedMap] = useState(false);
  const [featuredProgress, setFeaturedProgress] = useState(1); // 1 = full (10s left), 0 = empty (advancing)
  const userEngagedMapRef = useRef(false);
  const programmaticFlyRef = useRef(false);
  const featuredStartTimeRef = useRef(Date.now());
  const featuredIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const featuredCardHoverRef = useRef(false);
  const featuredPauseStartRef = useRef(0);
  const featuredTotalPausedRef = useRef(0);

  useEffect(() => {
    if (userEngagedMap) userEngagedMapRef.current = true;
  }, [userEngagedMap]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (!userEngagedMapRef.current) setFeaturedInitiated(true);
    }, 17000);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled(
      FEATURED_RESOURCE_IDS.map((id) => fetchResourceDetails(id))
    ).then((results) => {
      if (cancelled) return;
      setFeaturedDetails(
        results.map((r) =>
          r.status === "fulfilled" ? r.value : null
        )
      );
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-advance featured carousel every 10s; progress bar shows time left. Pauses while popup card is hovered.
  useEffect(() => {
    if (!featuredInitiated) return;

    featuredStartTimeRef.current = Date.now();
    featuredTotalPausedRef.current = 0;
    setFeaturedProgress(1);

    const tick = () => {
      const now = Date.now();
      let pausedMs = featuredTotalPausedRef.current;
      if (featuredCardHoverRef.current) {
        pausedMs += now - featuredPauseStartRef.current;
      }
      const elapsed = now - featuredStartTimeRef.current - pausedMs;
      if (elapsed >= FEATURED_ITEM_DURATION_MS) {
        setActiveIndex((prev) => (prev + 1) % FEATURED_RESOURCE_IDS.length);
        featuredStartTimeRef.current = Date.now();
        featuredTotalPausedRef.current = 0;
        setFeaturedProgress(1);
      } else {
        setFeaturedProgress(1 - elapsed / FEATURED_ITEM_DURATION_MS);
      }
    };

    featuredIntervalRef.current = setInterval(tick, FEATURED_PROGRESS_TICK_MS);
    return () => {
      if (featuredIntervalRef.current) {
        clearInterval(featuredIntervalRef.current);
        featuredIntervalRef.current = null;
      }
    };
  }, [featuredInitiated, activeIndex]);

  const activeDetail = featuredDetails[activeIndex];

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
          <MapPanner programmaticFlyRef={programmaticFlyRef} />
          <SearchHereControl />
          <MapUpdaterHex
            searchQuery=""
            onFeatureClick={() => {}}
            onHexHover={setHoveredHex}
            hoveredHex={hoveredHex}
            queryString={typeof window !== "undefined" ? window.location.search : undefined}
          />
          <MapUserEngagementTracker
            programmaticFlyRef={programmaticFlyRef}
            onUserEngaged={() => setUserEngagedMap(true)}
          />
          <FeaturedMapController
            activeIndex={activeIndex}
            featuredDetails={featuredDetails}
            featuredInitiated={featuredInitiated}
            programmaticFlyRef={programmaticFlyRef}
          />
          <FeaturedItemBoundsLayer
            activeIndex={activeIndex}
            featuredDetails={featuredDetails}
            featuredInitiated={featuredInitiated}
          />
        </MapContainer>

        {/* Featured resource popup overlay — bottom-right, list-view fields */}
        {featuredInitiated && activeDetail && (
          <div
            className="absolute bottom-24 right-4 z-20 w-full max-w-md rounded-lg bg-white/95 backdrop-blur-sm shadow-lg border border-gray-200 overflow-hidden"
            data-featured-popup
            onMouseEnter={() => {
              featuredCardHoverRef.current = true;
              featuredPauseStartRef.current = Date.now();
            }}
            onMouseLeave={() => {
              featuredCardHoverRef.current = false;
              featuredTotalPausedRef.current +=
                Date.now() - featuredPauseStartRef.current;
            }}
          >
            {/* Progress bar: time left for current item (dark Big Ten blue) */}
            <div className="h-1 w-full bg-gray-200 rounded-t-lg overflow-hidden">
              <div
                className="h-full rounded-t-lg transition-[width] duration-100 ease-linear"
                style={{
                  width: `${featuredProgress * 100}%`,
                  backgroundColor: DARK_BIG_TEN_BLUE,
                }}
              />
            </div>
            <div className="flex">
              <div className="flex-shrink-0 w-32 h-32 sm:w-40 sm:h-40 rounded-l-lg overflow-hidden bg-gray-100">
                {activeDetail.meta?.ui?.thumbnail_url ? (
                  <img
                    src={toSsrThumbnailUrl(activeDetail.meta.ui.thumbnail_url)}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    {getResourceIcon(
                      activeDetail.attributes?.ogm?.gbl_resourceClass_sm?.[0],
                      { className: "w-12 h-12" }
                    )}
                  </div>
                )}
              </div>
              <div className="flex-1 flex flex-col min-w-0 p-4">
                <Link
                  to={`/resources/${activeDetail.id}`}
                  className="flex-1"
                >
                  <h3 className="text-base font-semibold text-blue-600 hover:text-blue-800 line-clamp-2">
                    {activeDetail.attributes?.ogm?.dct_title_s || "Untitled"}
                  </h3>
                </Link>
                {activeDetail.attributes?.ogm?.dct_description_sm?.[0] && (
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                    {typeof activeDetail.attributes.ogm.dct_description_sm[0] === "string"
                      ? activeDetail.attributes.ogm.dct_description_sm[0]
                      : String(activeDetail.attributes.ogm.dct_description_sm[0])}
                  </p>
                )}
                <div className="flex items-center justify-between gap-2 mt-2 text-xs text-gray-500">
                  <span>
                    {activeDetail.attributes?.ogm?.gbl_indexYear_im?.[0] ??
                      activeDetail.attributes?.ogm?.gbl_indexyear_im?.[0] ??
                      "—"}
                  </span>
                  <span className="uppercase tracking-tighter opacity-80 border border-gray-200 px-1.5 py-0.5 rounded">
                    {activeDetail.attributes?.ogm?.gbl_resourceClass_sm?.[0] ?? "Item"}
                  </span>
                </div>
                <Link
                  to={`/resources/${activeDetail.id}`}
                  className="mt-2 text-sm text-blue-600 hover:underline font-medium"
                >
                  View resource
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Featured resources carousel at bottom of map — only after 5s and no map engagement */}
        {featuredInitiated && (
        <div
          className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex gap-2 px-3 py-2 rounded-lg bg-white/90 backdrop-blur-sm shadow-lg border border-gray-200"
          data-featured-carousel
        >
          {FEATURED_RESOURCE_IDS.map((id, index) => {
            const detail = featuredDetails[index];
            const isActive = index === activeIndex;
            const title =
              detail?.attributes?.ogm?.dct_title_s ||
              (detail ? "Untitled" : "Loading…");
            const thumbUrl = detail?.meta?.ui?.thumbnail_url;
            const resourceClass = detail?.attributes?.ogm?.gbl_resourceClass_sm?.[0];

            return (
              <button
                key={id}
                type="button"
                onClick={() => setActiveIndex(index)}
                className={`flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
                  isActive
                    ? "border-blue-600 ring-2 ring-blue-600/30"
                    : "border-transparent hover:border-gray-300"
                }`}
                aria-label={title}
                aria-current={isActive ? "true" : undefined}
              >
                {thumbUrl ? (
                  <img
                    src={toSsrThumbnailUrl(thumbUrl)}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-100 text-gray-400">
                    {getResourceIcon(resourceClass, { className: "w-8 h-8" })}
                  </div>
                )}
              </button>
            );
          })}
        </div>
        )}

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
