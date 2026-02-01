import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import type { GeoDocumentDetails } from '../../types/api';
import { parseBboxToLeafletBounds } from '../../utils/bbox';
import { HOME_PAGE_MAP_CENTER, DEFAULT_US_ZOOM } from '../../config/mapView';
import { hasAllmapsViewer } from './FeaturedItemPreviewLayer';

interface FeaturedMapControllerProps {
  activeIndex: number;
  featuredDetails: (GeoDocumentDetails | null)[];
  featuredInitiated: boolean;
  programmaticFlyRef: React.MutableRefObject<boolean>;
}

/**
 * When featuredInitiated and activeIndex/featuredDetails change, flies the map
 * to the active resource's bbox. Sets programmaticFlyRef so engagement tracker
 * does not treat the fly as user engagement.
 */
export function FeaturedMapController({
  activeIndex,
  featuredDetails,
  featuredInitiated,
  programmaticFlyRef,
}: FeaturedMapControllerProps) {
  const map = useMap();
  const wasInitiatedRef = useRef(false);

  // When user clicks HOME (featuredInitiated becomes false), fly back to default map view
  useEffect(() => {
    if (featuredInitiated) {
      wasInitiatedRef.current = true;
      return;
    }
    if (!wasInitiatedRef.current) return;
    programmaticFlyRef.current = true;
    map.flyTo(
      L.latLng(HOME_PAGE_MAP_CENTER[0], HOME_PAGE_MAP_CENTER[1]),
      DEFAULT_US_ZOOM,
      {
        duration: 0.6,
      }
    );
    const onMoveEnd = () => {
      programmaticFlyRef.current = false;
      map.off('moveend', onMoveEnd);
    };
    map.on('moveend', onMoveEnd);
    return () => map.off('moveend', onMoveEnd);
  }, [map, featuredInitiated, programmaticFlyRef]);

  useEffect(() => {
    if (!featuredInitiated) return;

    const detail = featuredDetails[activeIndex];
    if (!detail?.attributes?.ogm?.dcat_bbox) return;

    const bounds = parseBboxToLeafletBounds(detail.attributes.ogm.dcat_bbox);
    if (!bounds) return;

    const leafletBounds = L.latLngBounds(bounds[0], bounds[1]);
    if (!leafletBounds.isValid()) return;

    // Allmaps georeferenced maps: zoom tighter so georeferencing work is visible
    const isAllmaps = hasAllmapsViewer(detail);
    const flyOptions = isAllmaps
      ? { padding: [20, 20], maxZoom: 12, duration: 1.5 }
      : { padding: [60, 60], maxZoom: 10, duration: 1.5 };

    programmaticFlyRef.current = true;
    map.flyToBounds(leafletBounds, flyOptions);

    const onMoveEnd = () => {
      programmaticFlyRef.current = false;
      map.off('moveend', onMoveEnd);
    };
    map.on('moveend', onMoveEnd);
    return () => {
      map.off('moveend', onMoveEnd);
    };
  }, [
    map,
    activeIndex,
    featuredDetails,
    featuredInitiated,
    programmaticFlyRef,
  ]);

  return null;
}
