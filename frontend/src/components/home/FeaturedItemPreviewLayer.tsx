import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import { layerGroup } from 'leaflet';
import type { GeoDocumentDetails } from '../../types/api';
import { leafletViewerOptions } from '../../config/leafletConfig';

const FEATURED_PREVIEW_PANE = 'featuredPreviewPane';
const DEFAULT_OPACITY = 0.75;

/** Backend protocol names that use Leaflet (GeoBlacklight). Excludes OpenLayers-only: cog, pmtiles, iiif_*, oembed, geo_json. */
const LEAFLET_PROTOCOLS = new Set([
  'wms',
  'wmts',
  'arcgis_dynamic_map_layer',
  'arcgis_feature_layer',
  'arcgis_tiled_map_layer',
  'arcgis_image_map_layer',
  'tile_json',
  'open_index_map',
  'tile_map_service',
  'xyz_tiles',
]);

function formatProtocol(protocol: string): string | null {
  const map: Record<string, string> = {
    arcgis_dynamic_map_layer: 'DynamicMapLayer',
    arcgis_feature_layer: 'FeatureLayer',
    arcgis_tiled_map_layer: 'TiledMapLayer',
    arcgis_image_map_layer: 'ImageMapLayer',
    open_index_map: 'IndexMap',
    tile_map_service: 'Tms',
    xyz_tiles: 'Xyz',
    tile_json: 'Tilejson',
  };
  return (
    map[protocol] ??
    (protocol ? protocol.charAt(0).toUpperCase() + protocol.slice(1) : null)
  );
}

/** Exported for use by parent to conditionally show bounds layer. */
export function hasLeafletViewer(
  detail: GeoDocumentDetails | null
): detail is GeoDocumentDetails & {
  meta: {
    ui: { viewer: { protocol: string; endpoint: string; geometry: unknown } };
  };
} {
  const protocol = detail?.meta?.ui?.viewer?.protocol;
  const endpoint = detail?.meta?.ui?.viewer?.endpoint;
  const geometry = detail?.meta?.ui?.viewer?.geometry;
  return (
    !!detail &&
    !!protocol &&
    !!endpoint &&
    !!geometry &&
    LEAFLET_PROTOCOLS.has(protocol)
  );
}

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

function getAllmapsAnnotationUrl(detail: GeoDocumentDetails): string {
  const url = detail.meta?.ui?.allmaps?.allmaps_annotation_url;
  const manifestUri = detail.meta?.ui?.allmaps?.allmaps_manifest_uri;
  if (!manifestUri) return url ?? '';
  return url ?? `https://annotations.allmaps.org/?url=${encodeURIComponent(manifestUri)}`;
}

/** Ensures a pane exists for the featured preview layer. Layer order: hexes (back) -> bounds -> preview (front). */
function useFeaturedPreviewPane() {
  const map = useMap();
  useEffect(() => {
    let pane = map.getPane(FEATURED_PREVIEW_PANE);
    if (!pane) {
      pane = map.createPane(FEATURED_PREVIEW_PANE);
      pane.style.setProperty('z-index', '420', 'important'); // above bounds (410), front-most for imagery
    }
  }, [map]);
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
  useFeaturedPreviewPane();
  const map = useMap();
  const layerGroupRef = useRef<ReturnType<typeof layerGroup> | null>(null);

  useEffect(() => {
    if (!featuredInitiated) return;

    const detail = featuredDetails[activeIndex];
    const isAllmaps = hasAllmapsViewer(detail);
    const isLeaflet = hasLeafletViewer(detail);

    if (!isAllmaps && !isLeaflet) {
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }
      return;
    }

    // Allmaps georeferenced map path
    if (isAllmaps) {
      const annotationUrl = getAllmapsAnnotationUrl(detail);
      if (!annotationUrl) {
        if (layerGroupRef.current) {
          map.removeLayer(layerGroupRef.current);
          layerGroupRef.current = null;
        }
        return;
      }

      let cancelled = false;
      const group = layerGroup();
      layerGroupRef.current = group;

      async function addAllmapsLayer() {
        try {
          const { WarpedMapLayer } = await import('@allmaps/leaflet');
          const layer = new WarpedMapLayer(annotationUrl, {
            opacity: DEFAULT_OPACITY,
            pane: FEATURED_PREVIEW_PANE,
          });
          if (cancelled) return;
          try {
            group.addLayer(layer);
          } catch (addErr) {
            if (!cancelled)
              console.warn(
                'FeaturedItemPreviewLayer: failed to add Allmaps layer:',
                addErr
              );
            return;
          }
          if (cancelled) return;
          if (!map.hasLayer(group)) {
            map.addLayer(group);
          }
        } catch (err) {
          if (!cancelled) {
            console.warn(
              'FeaturedItemPreviewLayer: failed to add Allmaps preview layer:',
              err
            );
          }
        }
      }

      addAllmapsLayer();

      return () => {
        cancelled = true;
        if (layerGroupRef.current) {
          map.removeLayer(layerGroupRef.current);
          layerGroupRef.current = null;
        }
      };
    }

    // GeoBlacklight / Leaflet viewer path
    const protocol = detail.meta.ui.viewer.protocol;
    const endpoint = detail.meta.ui.viewer.endpoint;
    const gblProtocol = formatProtocol(protocol);
    if (!gblProtocol) {
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }
      return;
    }

    const layerId = detail.attributes?.ogm?.gbl_wxsIdentifier_s ?? '';
    const detectRetina = leafletViewerOptions.LAYERS?.DETECT_RETINA ?? false;
    const options = {
      layerId,
      opacity: DEFAULT_OPACITY,
      detectRetina,
    };

    let cancelled = false;
    const group = layerGroup();
    layerGroupRef.current = group;

    async function addLayer() {
      try {
        const layersModule = await import(
          /* @vite-ignore */
          'geoblacklight/leaflet/layers'
        );
        const L = await import('leaflet');
        const tileLayer = L.tileLayer;

        let layer: L.Layer | null = null;

        switch (gblProtocol) {
          case 'FeatureLayer':
            layer = layersModule.esriFeatureLayer(endpoint, options);
            break;
          case 'DynamicMapLayer':
            layer = layersModule.esriDynamicMapLayer(endpoint, options);
            break;
          case 'ImageMapLayer': {
            const esriLeaflet = await import('esri-leaflet');
            layer = esriLeaflet.imageMapLayer({ url: endpoint, ...options });
            break;
          }
          case 'Wms':
            layer = layersModule.wmsLayer(endpoint, options);
            break;
          case 'Tms':
            layer = tileLayer(endpoint, { tms: true, ...options });
            break;
          case 'Xyz':
            layer = tileLayer(endpoint, options);
            break;
          case 'Wmts':
            layer = await layersModule.wmtsLayer(endpoint, options);
            break;
          case 'TiledMapLayer':
            layer = await layersModule.esriTiledMapLayer(endpoint, options);
            break;
          case 'Tilejson':
            layer = await layersModule.tileJsonLayer(endpoint, options);
            break;
          case 'IndexMap': {
            const indexOptions = {
              ...leafletViewerOptions,
              opacity: DEFAULT_OPACITY,
              LAYERS: leafletViewerOptions.LAYERS,
            };
            layer = await layersModule.indexMapLayer(endpoint, indexOptions);
            break;
          }
          default:
            console.warn(
              `FeaturedItemPreviewLayer: unsupported protocol ${gblProtocol}`
            );
        }

        if (cancelled || !layer) return;

        // Ensure preview renders in our pane (z-index 420) for layer order: hexes -> bounds -> preview
        const layerWithOpts = layer as L.Layer & {
          options?: { pane?: string };
        };
        if (layerWithOpts.options) {
          layerWithOpts.options.pane = FEATURED_PREVIEW_PANE;
        }

        try {
          group.addLayer(layer);
        } catch (addErr) {
          if (!cancelled)
            console.warn(
              'FeaturedItemPreviewLayer: failed to add layer:',
              addErr
            );
          return;
        }
        if (cancelled) return;
        if (!map.hasLayer(group)) {
          map.addLayer(group);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn(
            'FeaturedItemPreviewLayer: failed to add preview layer:',
            err
          );
        }
      }
    }

    addLayer();

    return () => {
      cancelled = true;
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }
    };
  }, [map, activeIndex, featuredDetails, featuredInitiated]);

  return null;
}
