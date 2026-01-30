import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { MapUpdaterHex } from "../map/MapUpdaterHex";
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

/**
 * Non-interactive Leaflet hex map used as the background of the homepage.
 * Center is south of the US so North America appears just under the search form.
 */
export function HomePageHexMapBackground() {
  return (
    <div className="absolute inset-0 z-0">
      <MapContainer
        center={HOME_PAGE_MAP_CENTER}
        zoom={DEFAULT_US_ZOOM}
        className="h-full w-full"
        zoomControl={false}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        touchZoom={false}
        keyboard={false}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        <MapPanner />
        <MapUpdaterHex
          searchQuery=""
          onFeatureClick={() => {}}
          queryString={typeof window !== "undefined" ? window.location.search : undefined}
        />
      </MapContainer>
    </div>
  );
}
