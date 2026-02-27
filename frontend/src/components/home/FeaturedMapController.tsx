import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import type { GeoDocumentDetails } from '../../types/api';
import { parseBboxToLeafletBounds } from '../../utils/bbox';
import { HOME_PAGE_MAP_CENTER, DEFAULT_US_ZOOM } from '../../config/mapView';
import type { FeaturedMapCameraConfig } from '../../config/featured';
import { hasAllmapsViewer } from './FeaturedItemPreviewLayer';

interface FeaturedMapControllerProps {
  activeIndex: number;
  featuredDetails: (GeoDocumentDetails | null)[];
  featuredCamera?: FeaturedMapCameraConfig;
  featuredInitiated: boolean;
  programmaticFlyRef: React.MutableRefObject<boolean>;
  initialHomeViewRef?: React.MutableRefObject<{
    center: [number, number];
    zoom: number;
  } | null>;
}

/**
 * When featuredInitiated and activeIndex/featuredDetails change, flies the map
 * to the active resource's bbox. Sets programmaticFlyRef so engagement tracker
 * does not treat the fly as user engagement.
 */
export function FeaturedMapController({
  activeIndex,
  featuredDetails,
  featuredCamera,
  featuredInitiated,
  programmaticFlyRef,
  initialHomeViewRef,
}: FeaturedMapControllerProps) {
  const map = useMap();
  const wasInitiatedRef = useRef(false);
  const getHomeView = () => {
    if (initialHomeViewRef?.current) return initialHomeViewRef.current;
    return { center: HOME_PAGE_MAP_CENTER, zoom: DEFAULT_US_ZOOM };
  };

  // When user clicks HOME (featuredInitiated becomes false), fly back to default map view
  useEffect(() => {
    if (featuredInitiated) {
      wasInitiatedRef.current = true;
      return;
    }
    if (!wasInitiatedRef.current) return;
    const homeView = getHomeView();
    programmaticFlyRef.current = true;
    map.flyTo(L.latLng(homeView.center[0], homeView.center[1]), homeView.zoom, {
      duration: 0.6,
    });
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
    programmaticFlyRef.current = true;

    const duration = featuredCamera?.duration ?? 1.5;
    const hasExplicitCenter = Array.isArray(featuredCamera?.center);
    const hasExplicitZoom = typeof featuredCamera?.zoom === 'number';
    const flyMode =
      featuredCamera?.mode === 'flyTo' || hasExplicitCenter || hasExplicitZoom;

    const cleanupMoveListener = () => {
      const onMoveEnd = () => {
        programmaticFlyRef.current = false;
        map.off('moveend', onMoveEnd);
      };
      map.on('moveend', onMoveEnd);
      return () => map.off('moveend', onMoveEnd);
    };

    const fallbackToHome = () => {
      const homeView = getHomeView();
      map.flyTo(
        L.latLng(homeView.center[0], homeView.center[1]),
        homeView.zoom,
        { duration }
      );
    };

    const isAllmaps = hasAllmapsViewer(detail);
    const defaultPadding: [number, number] = isAllmaps ? [20, 20] : [60, 60];
    const padding = featuredCamera?.padding ?? defaultPadding;
    const maxZoom =
      featuredCamera?.maxZoom ?? (isAllmaps ? 12 : 10);
    const minZoom =
      featuredCamera?.minZoom ?? Number.NEGATIVE_INFINITY;

    const bbox = detail?.attributes?.ogm?.dcat_bbox;
    const parsedBounds = parseBboxToLeafletBounds(bbox);
    const leafletBounds = parsedBounds
      ? L.latLngBounds(parsedBounds[0], parsedBounds[1])
      : null;
    const hasValidBounds = !!leafletBounds?.isValid();

    if (flyMode) {
      if (hasExplicitCenter && hasExplicitZoom) {
        map.flyTo(
          L.latLng(featuredCamera!.center![0], featuredCamera!.center![1]),
          Math.min(Math.max(featuredCamera!.zoom!, minZoom), maxZoom),
          { duration }
        );
        return cleanupMoveListener();
      }

      if (!hasValidBounds) {
        fallbackToHome();
        return cleanupMoveListener();
      }

      const fittedZoom = map.getBoundsZoom(
        leafletBounds!,
        false,
        L.point(padding[0], padding[1])
      );
      const computedZoom = hasExplicitZoom ? featuredCamera!.zoom! : fittedZoom;
      const targetZoom = Math.min(Math.max(computedZoom, minZoom), maxZoom);

      const rawCenter = hasExplicitCenter
        ? L.latLng(featuredCamera!.center![0], featuredCamera!.center![1])
        : leafletBounds!.getCenter();
      const verticalOffset = featuredCamera?.verticalOffsetPx ?? 0;

      if (verticalOffset !== 0) {
        const centerPoint = map.project(rawCenter, targetZoom);
        const shiftedCenter = map.unproject(
          L.point(centerPoint.x, centerPoint.y + verticalOffset),
          targetZoom
        );
        map.flyTo(shiftedCenter, targetZoom, { duration });
      } else {
        map.flyTo(rawCenter, targetZoom, { duration });
      }
    } else {
      if (!hasValidBounds) {
        fallbackToHome();
        return cleanupMoveListener();
      }

      map.flyToBounds(leafletBounds!, {
        ...(featuredCamera?.paddingTopLeft
          ? { paddingTopLeft: featuredCamera.paddingTopLeft }
          : {}),
        ...(featuredCamera?.paddingBottomRight
          ? { paddingBottomRight: featuredCamera.paddingBottomRight }
          : {}),
        padding,
        maxZoom,
        duration,
      });
    }

    return cleanupMoveListener();
  }, [
    map,
    activeIndex,
    featuredDetails,
    featuredCamera,
    featuredInitiated,
    programmaticFlyRef,
  ]);

  return null;
}
