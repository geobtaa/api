import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { GeoDocumentDetails } from "../../types/api";
import { parseBboxToLeafletBounds } from "../../utils/bbox";

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

  useEffect(() => {
    if (!featuredInitiated) return;

    const detail = featuredDetails[activeIndex];
    if (!detail?.attributes?.ogm?.dcat_bbox) return;

    const bounds = parseBboxToLeafletBounds(detail.attributes.ogm.dcat_bbox);
    if (!bounds) return;

    const leafletBounds = L.latLngBounds(bounds[0], bounds[1]);
    if (!leafletBounds.isValid()) return;

    programmaticFlyRef.current = true;
    map.flyToBounds(leafletBounds, {
      padding: [60, 60],
      maxZoom: 10,
      duration: 0.6,
    });

    const onMoveEnd = () => {
      programmaticFlyRef.current = false;
      map.off("moveend", onMoveEnd);
    };
    map.on("moveend", onMoveEnd);
    return () => {
      map.off("moveend", onMoveEnd);
    };
  }, [map, activeIndex, featuredDetails, featuredInitiated, programmaticFlyRef]);

  return null;
}
