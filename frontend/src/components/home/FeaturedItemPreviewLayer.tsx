import { getAllmapsAnnotationUrl } from '../../utils/allmaps';
import { toAardvarkRecord } from '../../utils/ogmViewerRecord';
import { BASEMAP_STYLES } from '../../config/mapStyles';
import { useEffect } from 'react';
import { useMap } from '../../mapping/react';
import type { GeoDocumentDetails } from '../../types/api';

/** Resources with Allmaps georeferenced maps (IIIF with annotation in resource_allmaps). */
export function hasAllmapsViewer(
  detail: GeoDocumentDetails | null
): detail is GeoDocumentDetails & {
  meta: {
    ui: {
      allmaps: {
        allmaps_annotated: true;
        allmaps_annotation_url?: string;
        allmaps_manifest_uri?: string;
      };
    };
  };
} {
  const allmaps = detail?.meta?.ui?.allmaps;
  if (!detail || !allmaps || !allmaps.allmaps_annotated) return false;
  const hasUrl =
    !!allmaps.allmaps_annotation_url ||
    (!!allmaps.allmaps_manifest_uri &&
      typeof allmaps.allmaps_manifest_uri === 'string');
  return hasUrl;
}

export function FeaturedItemPreviewLayer({
  activeIndex,
  featuredDetails,
  featuredInitiated,
}: {
  activeIndex: number;
  featuredDetails: (GeoDocumentDetails | null)[];
  featuredInitiated: boolean;
}) {
  const map = useMap();
  useEffect(() => {
    if (!featuredInitiated) return;
    const detail = featuredDetails[activeIndex];
    if (!detail) return;
    let cancelled = false;
    let clear: (() => void) | undefined;
    async function draw() {
      try {
        if (hasAllmapsViewer(detail)) {
          const { WarpedMapLayer } = await import('@allmaps/maplibre');
          const url = getAllmapsAnnotationUrl(detail.meta?.ui?.allmaps)!;
          const response = await fetch(url);
          if (!response.ok) throw Error('Allmaps annotation unavailable');
          const annotation = await response.json();
          if (cancelled) return;
          const layer = new WarpedMapLayer({ layerId: 'featured-allmaps' });
          map.whenReady(async () => {
            if (cancelled) return;
            map.native.addLayer(layer as never);
            clear = () => {
              if (map.native.getLayer(layer.id))
                map.native.removeLayer(layer.id);
            };
            try {
              await layer.addGeoreferenceAnnotation(annotation);
            } catch (error) {
              clear?.();
              if (!cancelled)
                console.warn('Featured Allmaps preview unavailable', error);
            }
          });
        } else {
          const {
            OgmRecord,
            resourcesFor,
            previewersForResources,
            MapLibreTheme,
          } = await import('ogm-viewer/lib');
          const record = new OgmRecord(toAardvarkRecord(detail!));
          const previewers = await previewersForResources(resourcesFor(record));
          if (cancelled) return;
          const preview = previewers.find((p) => p.renderer === 'map');
          if (!preview || preview.renderer !== 'map') return;
          const theme = new MapLibreTheme(map.getContainer(), 'light', {
            lightBasemap: BASEMAP_STYLES.liberty,
            darkBasemap: BASEMAP_STYLES.dark,
          });
          map.whenReady(async () => {
            if (cancelled) return;
            preview.attach(map.native, theme.getStyle());
            clear = () => {
              void preview.clearPreview();
            };
            try {
              await preview.preview();
              if (cancelled) await preview.clearPreview();
            } catch (error) {
              console.warn('Featured map unavailable', error);
            }
          });
        }
      } catch (error) {
        if (!cancelled) console.warn('Featured map unavailable', error);
      }
    }
    void draw();
    return () => {
      cancelled = true;
      clear?.();
    };
  }, [map, activeIndex, featuredDetails, featuredInitiated]);
  return null;
}
