import type { Map, ControlPosition } from '../mapping/maplibre';
import {
  BasemapControl,
  BASEMAP_STYLES,
  getSavedBasemapKey,
} from 'ogm-viewer/basemaps';
export {
  BASEMAP_STYLES,
  getAvailableBasemapKeys,
  getSavedBasemapKey,
  type BasemapKey,
} from 'ogm-viewer/basemaps';

export function attachBasemapSwitcher(
  map: Map,
  _namespace: unknown,
  position: ControlPosition = 'topright'
) {
  let basemapSources = new Set<string>();
  let basemapLayers = new Set<string>();
  const control = new BasemapControl(
    BASEMAP_STYLES[getSavedBasemapKey()],
    (style) => {
      const current = map.native.getStyle();
      if (map.removed || !current) throw Error('Map unavailable');
      const sources = Object.fromEntries(
        Object.entries(current.sources).filter(
          ([id]) => !basemapSources.has(id)
        )
      );
      const layers = current.layers.filter(
        (layer) => !basemapLayers.has(layer.id)
      );
      basemapSources = new Set(Object.keys(style.sources));
      basemapLayers = new Set(
        style.layers.map((layer: { id: string }) => layer.id)
      );
      const center = map.native.getCenter?.();
      const camera = center
        ? {
            center: [center.lng, center.lat] as [number, number],
            zoom: map.native.getZoom(),
            bearing: map.native.getBearing(),
            pitch: map.native.getPitch(),
          }
        : {};
      map.native.setStyle({
        ...style,
        ...camera,
        sources: { ...style.sources, ...sources },
        layers: [...style.layers, ...layers],
      });
    }
  );
  map.whenReady(() => {
    const initial = map.native.getStyle();
    basemapSources = new Set(
      Object.keys(initial.sources).filter((id) => !id.startsWith('map-data-'))
    );
    basemapLayers = new Set(
      initial.layers
        .filter(
          (layer) =>
            !('source' in layer && String(layer.source).startsWith('map-data-'))
        )
        .map((layer) => layer.id)
    );
  });
  const positions = {
    topleft: 'top-left',
    topright: 'top-right',
    bottomleft: 'bottom-left',
    bottomright: 'bottom-right',
  } as const;
  map.native.addControl(control, positions[position]);
  return () => {
    if (!map.removed) map.native.removeControl(control);
  };
}
