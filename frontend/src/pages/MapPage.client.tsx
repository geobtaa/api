// MapPage renders three synchronized maps (country, region, county) and supporting UI.
// Data is fetched via useGeoFacets; county auto-fit/logic handled in specialized components/hooks.
import { useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Header } from "../components/layout/Header";
import { Footer } from "../components/layout/Footer";
import { SearchField } from "../components/SearchField";
import { useApi } from "../context/ApiContext";
import { useGeoFacets } from "../hooks/useGeoFacets";
import { MapUpdater } from "../components/map/MapUpdater";
import { MapCard } from "../components/map/MapCard";
import { Legend } from "../components/map/Legend";
import { ZoomLevelControls } from "../components/map/ZoomLevelControls";
import { SelectedFeaturePanel } from "../components/map/SelectedFeaturePanel";
import { StatsBar } from "../components/map/StatsBar";
import { DEFAULT_US_CENTER, DEFAULT_US_ZOOM } from "../config/mapView";
import type { ZoomLevel } from "../types/map";

// Fix for default markers in Leaflet with Vite
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

import type { MapFeatureClickPayload } from "../types/map";

export function MapPage() {
  // Local UI state: selected feature popup, current search query, and zoom level tab
  const [selectedFeature, setSelectedFeature] =
    useState<MapFeatureClickPayload | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>("region");

  // Last API URL is recorded in context for footer display; data fetched via hook
  const { setLastApiUrl } = useApi();
  const { data, loading, error } = useGeoFacets(searchQuery, setLastApiUrl);

  // When user clicks a shape on any map, store a small payload for the details panel
  const handleFeatureClick = (feature: MapFeatureClickPayload) => {
    setSelectedFeature(feature);
  };

  // Search input triggers new facet fetch and resets selected details
  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setSelectedFeature(null);
  };

  // Toggle which map set is emphasized in the StatsBar; all three maps still render
  const handleZoomLevelChange = (level: ZoomLevel) => {
    setZoomLevel(level);
    setSelectedFeature(null);
  };

  // Helpers for StatsBar
  const getCurrentData = () => {
    return data[zoomLevel] || [];
  };

  const getTotalResources = () => {
    return data[zoomLevel].reduce((sum, item) => sum + item.attributes.hits, 0);
  };

  // Loading and error states for the whole page (maps require facet data)
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
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
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Search and Controls */}
        <div className="mb-8">
          <SearchField onSearch={handleSearch} initialQuery={searchQuery} />

          <ZoomLevelControls
            zoomLevel={zoomLevel}
            onZoomLevelChange={handleZoomLevelChange}
          />
        </div>

        {/* Stats Bar */}
        <StatsBar data={getCurrentData()} totalResources={getTotalResources()} />

        {/* Map Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <MapCard title="Country View" isActive={zoomLevel === "country"}>
            <MapContainer
              center={DEFAULT_US_CENTER}
              zoom={DEFAULT_US_ZOOM}
              className="h-80 w-full rounded-lg"
            >
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapUpdater
                level="country"
                data={data}
                onFeatureClick={handleFeatureClick}
                searchQuery={searchQuery}
              />
            </MapContainer>
          </MapCard>

          <MapCard title="Region View" isActive={zoomLevel === "region"}>
            <MapContainer
              center={DEFAULT_US_CENTER}
              zoom={DEFAULT_US_ZOOM}
              className="h-80 w-full rounded-lg"
            >
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapUpdater
                level="region"
                data={data}
                onFeatureClick={handleFeatureClick}
                searchQuery={searchQuery}
              />
            </MapContainer>
          </MapCard>

          <MapCard title="County View" isActive={zoomLevel === "county"}>
            <MapContainer
              center={DEFAULT_US_CENTER}
              zoom={DEFAULT_US_ZOOM}
              className="h-80 w-full rounded-lg"
            >
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapUpdater
                level="county"
                data={data}
                onFeatureClick={handleFeatureClick}
                searchQuery={searchQuery}
              />
            </MapContainer>
          </MapCard>
        </div>

        {/* Selected Feature Details */}
        <SelectedFeaturePanel selectedFeature={selectedFeature} />

        {/* Legend */}
        <Legend />
      </main>

      <Footer />
    </div>
  );
}

export default MapPage;

