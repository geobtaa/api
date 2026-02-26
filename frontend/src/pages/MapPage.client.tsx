// MapPage renders three synchronized maps (country, region, county) and supporting UI.
// Data is fetched via useGeoFacets; county auto-fit/logic handled in specialized components/hooks.
import { useState, useCallback } from 'react';
import { Link } from 'react-router';
import { Seo } from '../components/Seo';
import { MapContainer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { SearchField } from '../components/SearchField';
import { useApi } from '../context/ApiContext';
import { useGeoFacets } from '../hooks/useGeoFacets';
import { MapUpdater } from '../components/map/MapUpdater';
import { MapUpdaterHex } from '../components/map/MapUpdaterHex';
import { HexTableControl } from '../components/map/HexTableControl';
import { MapCard } from '../components/map/MapCard';
import { Legend } from '../components/map/Legend';
import { ZoomLevelControls } from '../components/map/ZoomLevelControls';
import { SelectedFeaturePanel } from '../components/map/SelectedFeaturePanel';
import { StatsBar } from '../components/map/StatsBar';
import { BasemapSwitcherControl } from '../components/map/BasemapSwitcherControl';
import { formatCount } from '../utils/formatNumber';
import { DEFAULT_US_CENTER, DEFAULT_US_ZOOM } from '../config/mapView';
import type { ZoomLevel } from '../types/map';
import type { MapFeatureClickPayload } from '../types/map';

export function MapPage() {
  // Local UI state: selected feature popup, current search query, and zoom level tab
  const [selectedFeature, setSelectedFeature] =
    useState<MapFeatureClickPayload | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('hex');
  const [hexStats, setHexStats] = useState<{
    hexCount: number;
    totalInView: number;
    loading: boolean;
    error: string | null;
    hexes: Array<{ h3: string; count: number }>;
    resolution: number;
  }>({
    hexCount: 0,
    totalInView: 0,
    loading: false,
    error: null,
    hexes: [],
    resolution: 6,
  });

  const { setLastApiUrl } = useApi();
  const { data, loading, error, globalCount } = useGeoFacets(
    searchQuery,
    setLastApiUrl
  );

  const handleFeatureClick = (feature: MapFeatureClickPayload) => {
    setSelectedFeature(feature);
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setSelectedFeature(null);
  };

  const handleZoomLevelChange = (level: ZoomLevel) => {
    setZoomLevel(level);
    setSelectedFeature(null);
  };

  const handleHexData = useCallback(
    (stats: {
      hexCount: number;
      totalInView: number;
      loading: boolean;
      error: string | null;
      hexes: Array<{ h3: string; count: number }>;
      resolution: number;
    }) => {
      setHexStats(stats);
    },
    []
  );

  const getCurrentData = () => {
    if (zoomLevel === 'hex') return [];
    return data[zoomLevel] || [];
  };

  const getTotalResources = () => {
    if (zoomLevel === 'hex') return hexStats.totalInView;
    return (data[zoomLevel] || []).reduce(
      (sum, item) => sum + item.attributes.hits,
      0
    );
  };

  // Loading and error states for the whole page (maps require facet data)
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Seo title="Map" />
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading map data...</p>
            </div>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Seo title="Map" />
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <div className="flex">
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>{error}</p>
                </div>
                <div className="mt-4">
                  <button
                    onClick={() => window.location.reload()}
                    className="bg-red-100 px-3 py-2 rounded-md text-sm font-medium text-red-800 hover:bg-red-200"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div
      className={`bg-gray-50 flex flex-col ${zoomLevel === 'hex' ? 'h-screen overflow-hidden' : 'min-h-screen'}`}
    >
      <Seo title="Map" />
      <Header />

      <main
        className={`flex-1 flex flex-col min-h-0 ${zoomLevel === 'hex' ? 'relative overflow-hidden' : ''}`}
      >
        {zoomLevel === 'hex' ? (
          /* Hex view: map fills viewport, compact controls overlay */
          <>
            <div className="relative flex-1 min-h-0">
              <div className="absolute inset-0">
                <MapContainer
                  center={DEFAULT_US_CENTER}
                  zoom={DEFAULT_US_ZOOM}
                  className="h-full w-full"
                  scrollWheelZoom
                >
                  <BasemapSwitcherControl />
                  <MapUpdaterHex
                    searchQuery={searchQuery}
                    onFeatureClick={handleFeatureClick}
                    onHexData={handleHexData}
                    queryString={
                      typeof window !== 'undefined'
                        ? window.location.search
                        : undefined
                    }
                  />
                  <HexTableControl
                    hexes={hexStats.hexes}
                    resolution={hexStats.resolution}
                    searchQuery={searchQuery}
                    queryString={
                      typeof window !== 'undefined'
                        ? window.location.search.slice(1)
                        : undefined
                    }
                    loading={hexStats.loading}
                    compact
                  />
                </MapContainer>
                <div className="absolute bottom-4 right-4 z-[1000] bg-white/95 rounded-lg shadow-sm border border-gray-200 p-3">
                  <Legend />
                </div>
                {selectedFeature && (
                  <div className="absolute top-14 right-4 z-[1000] bg-white rounded-lg shadow-md border border-gray-200 p-4 max-w-xs">
                    <h3 className="font-semibold text-gray-900 mb-2">
                      {selectedFeature.properties?.name ?? 'Selected'}
                    </h3>
                    <p className="text-sm text-gray-600">
                      <span className="font-medium">
                        {formatCount(selectedFeature.properties?.hits ?? 0)}
                      </span>{' '}
                      resources
                    </p>
                  </div>
                )}
              </div>
              <div className="absolute top-0 left-0 right-0 z-[1000] flex flex-wrap items-center gap-3 px-4 py-2 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-sm">
                <div className="min-w-0 flex-1 max-w-sm">
                  <SearchField
                    onSearch={handleSearch}
                    initialQuery={searchQuery}
                  />
                </div>
                <ZoomLevelControls
                  zoomLevel={zoomLevel}
                  onChange={handleZoomLevelChange}
                />
                <div className="flex items-center gap-3 text-sm text-gray-600 shrink-0">
                  <span>
                    <span className="font-semibold">
                      {formatCount(getTotalResources())}
                    </span>{' '}
                    in view
                  </span>
                  {hexStats.hexCount > 0 && (
                    <span>{formatCount(hexStats.hexCount)} hexes</span>
                  )}
                  {globalCount > 0 && (
                    <Link
                      to={`/search?q=${encodeURIComponent(searchQuery)}&include_filters[geo_global][]=true`}
                      className="text-blue-600 hover:underline"
                    >
                      {formatCount(globalCount)} global
                    </Link>
                  )}
                  {hexStats.loading && (
                    <span className="text-amber-600">Loading…</span>
                  )}
                  {hexStats.error && (
                    <span className="text-red-600">{hexStats.error}</span>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="container mx-auto px-4 py-8">
            <div className="mb-8">
              <SearchField onSearch={handleSearch} initialQuery={searchQuery} />
              <ZoomLevelControls
                zoomLevel={zoomLevel}
                onChange={handleZoomLevelChange}
              />
            </div>
            <StatsBar
              zoomLevel={zoomLevel}
              dataForLevel={getCurrentData()}
              totalResources={getTotalResources()}
              query={searchQuery}
              globalCount={globalCount}
              hexCount={hexStats.hexCount}
              hexTotalInView={hexStats.totalInView}
              hexLoading={hexStats.loading}
              hexError={hexStats.error}
            />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8 mt-6">
              <MapCard title="Country View" isActive={zoomLevel === 'country'}>
                <MapContainer
                  center={DEFAULT_US_CENTER}
                  zoom={DEFAULT_US_ZOOM}
                  className="h-80 w-full rounded-lg"
                >
                  <BasemapSwitcherControl />
                  <MapUpdater
                    level="country"
                    data={data}
                    onFeatureClick={handleFeatureClick}
                    searchQuery={searchQuery}
                  />
                </MapContainer>
              </MapCard>

              <MapCard title="Region View" isActive={zoomLevel === 'region'}>
                <MapContainer
                  center={DEFAULT_US_CENTER}
                  zoom={DEFAULT_US_ZOOM}
                  className="h-80 w-full rounded-lg"
                >
                  <BasemapSwitcherControl />
                  <MapUpdater
                    level="region"
                    data={data}
                    onFeatureClick={handleFeatureClick}
                    searchQuery={searchQuery}
                  />
                </MapContainer>
              </MapCard>

              <MapCard title="County View" isActive={zoomLevel === 'county'}>
                <MapContainer
                  center={DEFAULT_US_CENTER}
                  zoom={DEFAULT_US_ZOOM}
                  className="h-80 w-full rounded-lg"
                >
                  <BasemapSwitcherControl />
                  <MapUpdater
                    level="county"
                    data={data}
                    onFeatureClick={handleFeatureClick}
                    searchQuery={searchQuery}
                  />
                </MapContainer>
              </MapCard>
            </div>
            {selectedFeature && (
              <SelectedFeaturePanel
                name={selectedFeature.properties?.name ?? ''}
                hits={selectedFeature.properties?.hits ?? 0}
                level={
                  zoomLevel === 'county'
                    ? 'county'
                    : zoomLevel === 'region'
                      ? 'region'
                      : 'country'
                }
              />
            )}
            <Legend />
          </div>
        )}
      </main>

      {zoomLevel !== 'hex' && <Footer />}
    </div>
  );
}

export default MapPage;
