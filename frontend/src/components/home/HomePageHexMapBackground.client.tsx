import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  ChevronLeft,
  ChevronRight,
  Home,
  Pause,
  Play,
  Search,
} from 'lucide-react';
import {
  MapContainer,
  Rectangle,
  TileLayer,
  useMap,
  ZoomControl,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { MapUpdaterHex } from '../map/MapUpdaterHex';
import { HexTableControl } from '../map/HexTableControl';
import { HOME_PAGE_MAP_CENTER, DEFAULT_US_ZOOM } from '../../config/mapView';
import { FEATURED_RESOURCE_IDS } from '../../config/featured';
import { fetchResourceDetails } from '../../services/api';
import type { GeoDocumentDetails } from '../../types/api';
import { getResourceIcon } from '../../utils/resourceIcons';
import { parseBboxToLeafletBounds } from '../../utils/bbox';
import { FeaturedMapController } from './FeaturedMapController';
import { FeaturedItemPreviewLayer } from './FeaturedItemPreviewLayer';

/** Route API thumbnail URLs through app paths for SSR/relative requests. */
function toSsrThumbnailUrl(url: string | undefined): string {
  if (!url || typeof url !== 'string') return '';
  try {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      const u = new URL(url);
      if (u.pathname.startsWith('/api/v1/thumbnails/')) {
        return (
          u.pathname.replace('/api/v1/thumbnails/', '/thumbnails/') + u.search
        );
      }
      if (u.pathname.match(/^\/api\/v1\/resources\/[^/]+\/thumbnail$/)) {
        return u.pathname.replace('/api/v1', '') + u.search;
      }
      return url;
    }
    if (url.startsWith('/api/v1/thumbnails/')) {
      return url.replace('/api/v1/thumbnails/', '/thumbnails/');
    }
    const m = url.match(/^\/api\/v1(\/resources\/[^/]+\/thumbnail)/);
    if (m) return m[1];
    return url;
  } catch {
    if (url.includes('/api/v1/thumbnails/'))
      return url.replace('/api/v1/thumbnails/', '/thumbnails/');
    if (url.includes('/api/v1/resources/') && url.endsWith('/thumbnail'))
      return url.replace('/api/v1', '');
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
    map.on('moveend', handler);
    map.on('zoomend', handler);
    return () => {
      map.off('moveend', handler);
      map.off('zoomend', handler);
    };
  }, [map, programmaticFlyRef, onUserEngaged]);
  return null;
}

const FEATURED_BOUNDS_PANE = 'featuredBoundsPane';
const FEATURED_ITEM_DURATION_MS = 10_000;
const FEATURED_PROGRESS_TICK_MS = 100;
/** Dark Big Ten blue for progress bar (BTAA primary) */
const DARK_BIG_TEN_BLUE = '#003C5B';

/** Ensures a pane exists for the featured bounds rectangle. Layer order: hexes (back) -> bounds -> preview (front). */
function useFeaturedBoundsPane() {
  const map = useMap();
  useEffect(() => {
    let pane = map.getPane(FEATURED_BOUNDS_PANE);
    if (!pane) {
      pane = map.createPane(FEATURED_BOUNDS_PANE);
      pane.style.setProperty('z-index', '410', 'important'); // above hexes, below featuredPreviewPane (420)
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
        color: '#2563eb',
        weight: 2,
        fillColor: '#3b82f6',
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
        map.off('moveend', onMoveEnd);
      };
      map.on('moveend', onMoveEnd);
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
    map.on('moveend', handleMoveEnd);
    map.on('zoomend', handleMoveEnd);
    return () => {
      map.off('moveend', handleMoveEnd);
      map.off('zoomend', handleMoveEnd);
    };
  }, [map]);

  const handleSearchHere = () => {
    setShowSearchButton(false);
    const bounds = map.getBounds();
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    const params = new URLSearchParams();
    params.set('include_filters[geo][type]', 'bbox');
    params.set('include_filters[geo][field]', 'dcat_bbox');
    params.set('include_filters[geo][top_left][lat]', ne.lat.toString());
    params.set('include_filters[geo][top_left][lon]', sw.lng.toString());
    params.set('include_filters[geo][bottom_right][lat]', sw.lat.toString());
    params.set('include_filters[geo][bottom_right][lon]', ne.lng.toString());
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
  const navigate = useNavigate();
  const [activeIndex, setActiveIndex] = useState(0);
  const [featuredDetails, setFeaturedDetails] = useState<
    (GeoDocumentDetails | null)[]
  >(() => FEATURED_RESOURCE_IDS.map(() => null));
  const [featuredInitiated, setFeaturedInitiated] = useState(false);
  const [userEngagedMap, setUserEngagedMap] = useState(false);
  const [featuredProgress, setFeaturedProgress] = useState(1); // 1 = full (10s left), 0 = empty (advancing)
  const userEngagedMapRef = useRef(false);
  // Start true so initial map load/tile moveend events don't count as user engagement
  const programmaticFlyRef = useRef(true);
  const featuredStartTimeRef = useRef(Date.now());
  const featuredIntervalRef = useRef<ReturnType<typeof setInterval> | null>(
    null
  );
  const featuredCardHoverRef = useRef(false);
  const featuredPauseStartRef = useRef(0);
  const featuredTotalPausedRef = useRef(0);
  const [carouselPaused, setCarouselPaused] = useState(false);
  const carouselPausedRef = useRef(false);
  const [hexDataForTable, setHexDataForTable] = useState<{
    hexes: Array<{ h3: string; count: number }>;
    resolution: number;
    loading: boolean;
  }>({ hexes: [], resolution: 6, loading: false });

  const handleHexData = useCallback(
    (data: {
      hexes: Array<{ h3: string; count: number }>;
      resolution: number;
      loading: boolean;
    }) => {
      setHexDataForTable({
        hexes: data.hexes,
        resolution: data.resolution,
        loading: data.loading,
      });
    },
    []
  );

  const [preCarouselProgress] = useState(1);

  useEffect(() => {
    carouselPausedRef.current = carouselPaused;
  }, [carouselPaused]);

  useEffect(() => {
    if (userEngagedMap) userEngagedMapRef.current = true;
  }, [userEngagedMap]);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled(
      FEATURED_RESOURCE_IDS.map((id) => fetchResourceDetails(id))
    ).then((results) => {
      if (cancelled) return;
      setFeaturedDetails(
        results.map((r) => (r.status === 'fulfilled' ? r.value : null))
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
      if (carouselPausedRef.current) return;
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
      <p className="sr-only">
        For a list of hex data, use the hex table button in the bottom-left
        corner of the map.
      </p>
      <div
        className="relative h-full w-full"
        role="img"
        aria-label="Resource density hex map"
      >
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
          zoomAnimationThreshold={1}
        >
          <ZoomControl position="topright" />
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          <MapPanner programmaticFlyRef={programmaticFlyRef} />
          <SearchHereControl />
          <HexTableControl
            hexes={hexDataForTable.hexes}
            resolution={hexDataForTable.resolution}
            searchQuery=""
            queryString={
              typeof window !== 'undefined' ? window.location.search : undefined
            }
            loading={hexDataForTable.loading}
          />
          <MapUpdaterHex
            searchQuery=""
            onFeatureClick={() => {}}
            onHexHover={() => {}}
            onHexData={handleHexData}
            queryString={
              typeof window !== 'undefined' ? window.location.search : undefined
            }
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
          <FeaturedItemPreviewLayer
            activeIndex={activeIndex}
            featuredDetails={featuredDetails}
            featuredInitiated={featuredInitiated}
          />
          <FeaturedItemBoundsLayer
            activeIndex={activeIndex}
            featuredDetails={featuredDetails}
            featuredInitiated={featuredInitiated}
          />
        </MapContainer>

        {/* Live region: announce active slide change for screen readers */}
        <div aria-live="polite" aria-atomic className="sr-only" role="status">
          {featuredInitiated && activeDetail
            ? `Current featured item: ${activeDetail.attributes?.ogm?.dct_title_s || 'Untitled'}`
            : ''}
        </div>

        {/* Featured resource popup overlay — bottom-right, list-view fields */}
        {featuredInitiated && activeDetail && (
          <div
            className="absolute bottom-44 right-4 z-20 w-full max-w-xl rounded-lg bg-white/70 backdrop-blur-sm shadow-lg border border-gray-200 overflow-hidden"
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
                      { className: 'w-12 h-12' }
                    )}
                  </div>
                )}
              </div>
              <div className="flex-1 flex flex-col min-w-0 p-4">
                <Link to={`/resources/${activeDetail.id}`} className="flex-1">
                  <h3 className="text-base font-semibold text-blue-600 hover:text-blue-800 line-clamp-2">
                    {activeDetail.attributes?.ogm?.dct_title_s || 'Untitled'}
                  </h3>
                </Link>
                {activeDetail.attributes?.ogm?.dct_description_sm?.[0] && (
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                    {typeof activeDetail.attributes.ogm
                      .dct_description_sm[0] === 'string'
                      ? activeDetail.attributes.ogm.dct_description_sm[0]
                      : String(
                          activeDetail.attributes.ogm.dct_description_sm[0]
                        )}
                  </p>
                )}
                <div className="flex items-center justify-between gap-2 mt-2 text-xs text-gray-500">
                  <span>
                    {activeDetail.attributes?.ogm?.gbl_indexYear_im?.[0] ??
                      activeDetail.attributes?.ogm?.gbl_indexyear_im?.[0] ??
                      '—'}
                  </span>
                  <span className="uppercase tracking-tighter opacity-80 border border-gray-200 px-1.5 py-0.5 rounded">
                    {activeDetail.attributes?.ogm?.gbl_resourceClass_sm?.[0] ??
                      'Item'}
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
            {/* Progress bar at bottom: time left for current item, drains towards the right */}
            <div
              role="progressbar"
              aria-valuenow={Math.round(featuredProgress * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Time remaining in current featured item"
              className="h-1 w-full bg-gray-200 rounded-b-lg overflow-hidden flex justify-end"
            >
              <div
                className="h-full rounded-b-lg transition-[width] duration-100 ease-linear"
                style={{
                  width: `${featuredProgress * 100}%`,
                  backgroundColor: DARK_BIG_TEN_BLUE,
                }}
              />
            </div>
          </div>
        )}

        {/* Featured resources carousel at bottom of map — always visible so users can click before the 10s timer */}
        <div
          role="region"
          aria-roledescription="carousel"
          aria-label="Featured resources"
          aria-describedby="featured-carousel-desc"
          className="absolute bottom-14 left-1/2 -translate-x-1/2 z-20 flex gap-2 px-3 py-2 rounded-lg bg-white/60 backdrop-blur-sm shadow-lg border border-gray-200"
          data-featured-carousel
          onMouseEnter={() => {
            featuredCardHoverRef.current = true;
            featuredPauseStartRef.current = Date.now();
          }}
          onMouseLeave={() => {
            featuredCardHoverRef.current = false;
            featuredTotalPausedRef.current +=
              Date.now() - featuredPauseStartRef.current;
          }}
          onFocus={() => {
            setCarouselPaused(true);
          }}
          onKeyDown={(e) => {
            const carouselEl = e.currentTarget;
            if (!carouselEl.contains(document.activeElement)) return;
            const len = FEATURED_RESOURCE_IDS.length;
            let newIndex: number | null = null;
            if (e.key === 'ArrowLeft') {
              e.preventDefault();
              newIndex = (activeIndex - 1 + len) % len;
              setActiveIndex(newIndex);
              featuredStartTimeRef.current = Date.now();
              featuredTotalPausedRef.current = 0;
              setFeaturedProgress(1);
              setFeaturedInitiated(true);
            } else if (e.key === 'ArrowRight') {
              e.preventDefault();
              newIndex = (activeIndex + 1) % len;
              setActiveIndex(newIndex);
              featuredStartTimeRef.current = Date.now();
              featuredTotalPausedRef.current = 0;
              setFeaturedProgress(1);
              setFeaturedInitiated(true);
            } else if (e.key === 'Home') {
              e.preventDefault();
              newIndex = 0;
              setActiveIndex(0);
              featuredStartTimeRef.current = Date.now();
              featuredTotalPausedRef.current = 0;
              setFeaturedProgress(1);
              setFeaturedInitiated(true);
            } else if (e.key === 'End') {
              e.preventDefault();
              newIndex = len - 1;
              setActiveIndex(len - 1);
              featuredStartTimeRef.current = Date.now();
              featuredTotalPausedRef.current = 0;
              setFeaturedProgress(1);
              setFeaturedInitiated(true);
            }
            if (newIndex !== null) {
              setTimeout(() => {
                carouselEl
                  .querySelector<HTMLButtonElement>(
                    `[data-carousel-thumb][data-index="${newIndex}"]`
                  )
                  ?.focus();
              }, 0);
            }
          }}
        >
          <p id="featured-carousel-desc" className="sr-only">
            Use previous and next buttons to change the featured item, or select
            a thumbnail to jump to an item.
          </p>
          <button
            type="button"
            onClick={() => setFeaturedInitiated(false)}
            className={`flex-shrink-0 w-16 h-16 rounded-lg flex items-center justify-center border-2 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
              !featuredInitiated
                ? 'border-blue-600 ring-2 ring-blue-600/30 bg-blue-50'
                : 'border-transparent hover:border-gray-300 bg-gray-50 hover:bg-gray-100'
            }`}
            aria-label="Return to home map view"
            title="Home"
          >
            <Home className="w-8 h-8 text-gray-600" />
          </button>
          <div className="relative flex-shrink-0 w-16 h-16 flex items-center justify-center">
            {/* Circular countdown ring behind Play; button is transparent during countdown so ring shows through */}
            {!featuredInitiated && preCarouselProgress > 0 && (
              <svg
                className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none"
                viewBox="0 0 64 64"
                aria-hidden
              >
                <circle
                  cx="32"
                  cy="32"
                  r="28"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  className="text-gray-200"
                />
                <circle
                  cx="32"
                  cy="32"
                  r="28"
                  fill="none"
                  stroke={DARK_BIG_TEN_BLUE}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 28 * preCarouselProgress} ${2 * Math.PI * 28}`}
                  className="transition-[stroke-dasharray] duration-100 ease-linear"
                />
              </svg>
            )}
            <button
              type="button"
              onClick={() => {
                if (!featuredInitiated) {
                  setFeaturedInitiated(true);
                  setCarouselPaused(false);
                  return;
                }
                setCarouselPaused((p) => !p);
              }}
              className={`relative z-10 w-16 h-16 rounded-lg flex items-center justify-center border-2 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
                !featuredInitiated
                  ? preCarouselProgress > 0
                    ? 'border-transparent bg-transparent text-gray-500 hover:text-gray-600'
                    : 'border-transparent hover:border-gray-300 bg-gray-50 hover:bg-gray-100 text-gray-600'
                  : carouselPaused
                    ? 'border-transparent hover:border-gray-300 bg-gray-50 hover:bg-gray-100 text-gray-600'
                    : 'border-transparent hover:border-gray-300 bg-gray-50 hover:bg-gray-100 text-gray-600'
              }`}
              aria-label={
                !featuredInitiated
                  ? 'Start featured carousel'
                  : carouselPaused
                    ? 'Play featured carousel'
                    : 'Pause featured carousel'
              }
              title={
                !featuredInitiated ? 'Start' : carouselPaused ? 'Play' : 'Pause'
              }
            >
              {carouselPaused || !featuredInitiated ? (
                <Play className="w-8 h-8" />
              ) : (
                <Pause className="w-8 h-8" />
              )}
            </button>
          </div>
          {FEATURED_RESOURCE_IDS.map((id, index) => {
            const detail = featuredDetails[index];
            const isActive = index === activeIndex;
            const title =
              detail?.attributes?.ogm?.dct_title_s ||
              (detail ? 'Untitled' : 'Loading…');
            const thumbUrl = detail?.meta?.ui?.thumbnail_url;
            const resourceClass =
              detail?.attributes?.ogm?.gbl_resourceClass_sm?.[0];

            return (
              <button
                key={id}
                type="button"
                data-carousel-thumb
                data-index={index}
                onClick={() => {
                  setActiveIndex(index);
                  setFeaturedInitiated(true);
                }}
                className={`flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
                  isActive
                    ? 'border-blue-600 ring-2 ring-blue-600/30'
                    : 'border-transparent hover:border-gray-300'
                }`}
                aria-label={title}
                aria-current={isActive ? 'true' : undefined}
              >
                {thumbUrl ? (
                  <img
                    src={toSsrThumbnailUrl(thumbUrl)}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-100 text-gray-400">
                    {getResourceIcon(resourceClass, { className: 'w-8 h-8' })}
                  </div>
                )}
              </button>
            );
          })}
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveIndex(
                  (prev) =>
                    (prev - 1 + FEATURED_RESOURCE_IDS.length) %
                    FEATURED_RESOURCE_IDS.length
                );
                featuredStartTimeRef.current = Date.now();
                featuredTotalPausedRef.current = 0;
                setFeaturedProgress(1);
                setFeaturedInitiated(true);
              }}
              className="flex-shrink-0 w-16 h-16 rounded-lg flex items-center justify-center border-2 border-transparent hover:border-gray-300 bg-gray-50 hover:bg-gray-100 text-gray-600 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
              aria-label="Previous featured item"
            >
              <ChevronLeft className="w-8 h-8" />
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveIndex(
                  (prev) => (prev + 1) % FEATURED_RESOURCE_IDS.length
                );
                featuredStartTimeRef.current = Date.now();
                featuredTotalPausedRef.current = 0;
                setFeaturedProgress(1);
                setFeaturedInitiated(true);
              }}
              className="flex-shrink-0 w-16 h-16 rounded-lg flex items-center justify-center border-2 border-transparent hover:border-gray-300 bg-gray-50 hover:bg-gray-100 text-gray-600 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
              aria-label="Next featured item"
            >
              <ChevronRight className="w-8 h-8" />
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
