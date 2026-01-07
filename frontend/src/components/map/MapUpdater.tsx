// Wrapper that routes to the appropriate map updater by zoomLevel
import type {
  ChoroplethData,
  ZoomLevel,
  MapFeatureClickPayload,
} from '../../types/map';
import { MapUpdaterCountry } from './MapUpdaterCountry';
import { MapUpdaterRegion } from './MapUpdaterRegion';
import { MapUpdaterCounty } from './MapUpdaterCounty';

export function MapUpdater({
  data,
  zoomLevel,
  onFeatureClick,
  searchQuery,
}: {
  data: ChoroplethData;
  zoomLevel: ZoomLevel;
  onFeatureClick: (feature: MapFeatureClickPayload) => void;
  searchQuery: string;
}) {
  if (zoomLevel === 'country') {
    return <MapUpdaterCountry data={data} onFeatureClick={onFeatureClick} />;
  }
  if (zoomLevel === 'region') {
    return <MapUpdaterRegion data={data} onFeatureClick={onFeatureClick} />;
  }
  return (
    <MapUpdaterCounty
      data={data}
      onFeatureClick={onFeatureClick}
      searchQuery={searchQuery}
    />
  );
}
