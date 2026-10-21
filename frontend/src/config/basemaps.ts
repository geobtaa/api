import Cookies from 'js-cookie';
import type L from 'leaflet';

type BasemapDefinition = {
  label: string;
  url: string;
  attribution: string;
  options?: L.TileLayerOptions;
};

const BASEMAP_COOKIE_NAME = 'preferred_basemap';
const BASEMAP_COOKIE_EXPIRY_DAYS = 365;
const DEFAULT_BASEMAP_KEY = 'openStreetMap';

const BASEMAP_DEFINITIONS = {
  openStreetMap: {
    label: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    options: {
      maxZoom: 19,
      referrerPolicy: 'strict-origin-when-cross-origin',
    },
  },
  esriWorldImagery: {
    label: 'Esri World Imagery',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution:
      'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    options: {
      maxZoom: 18,
    },
  },
} as const satisfies Record<string, BasemapDefinition>;

export type BasemapKey = keyof typeof BASEMAP_DEFINITIONS;

export function getAvailableBasemapKeys(): BasemapKey[] {
  return Object.keys(BASEMAP_DEFINITIONS) as BasemapKey[];
}

function isBasemapKey(value: string): value is BasemapKey {
  return Object.prototype.hasOwnProperty.call(BASEMAP_DEFINITIONS, value);
}

export function getSavedBasemapKey(): BasemapKey {
  const saved = Cookies.get(BASEMAP_COOKIE_NAME);
  if (saved && isBasemapKey(saved)) {
    return saved;
  }
  return DEFAULT_BASEMAP_KEY;
}

function saveBasemapKey(key: BasemapKey): void {
  Cookies.set(BASEMAP_COOKIE_NAME, key, {
    expires: BASEMAP_COOKIE_EXPIRY_DAYS,
  });
}

export function createBasemapLayer(
  Leaflet: typeof L,
  key: BasemapKey
): L.TileLayer {
  const config = BASEMAP_DEFINITIONS[key];
  return Leaflet.tileLayer(config.url, {
    attribution: config.attribution,
    ...config.options,
  });
}

export function attachBasemapSwitcher(
  map: L.Map,
  Leaflet: typeof L,
  position: L.ControlPosition = 'topleft',
  onTileErrorChange?: (unavailable: boolean) => void
): () => void {
  const basemapLayers = {} as Record<BasemapKey, L.TileLayer>;
  const labeledLayers: Record<string, L.TileLayer> = {};

  // Remember failures per layer for this map's lifetime. A later successful
  // tile must not hide a warning about other missing tiles in the same view.
  const failedLayers = new Set<BasemapKey>();
  const errorHandlers = new Map<
    L.TileLayer,
    (event: L.TileErrorEvent) => void
  >();

  (Object.keys(BASEMAP_DEFINITIONS) as BasemapKey[]).forEach((key) => {
    const config = BASEMAP_DEFINITIONS[key];
    const layer = createBasemapLayer(Leaflet, key);
    if (onTileErrorChange) {
      const onTileError = (event: L.TileErrorEvent) => {
        // A 403 can contain a provider's error image. Keep it from obscuring
        // the resource geometry, without making another network request.
        event.tile.style.visibility = 'hidden';
        failedLayers.add(key);
        if (map.hasLayer(layer)) onTileErrorChange(true);
      };
      layer.on('tileerror', onTileError);
      errorHandlers.set(layer, onTileError);
    }
    basemapLayers[key] = layer;
    labeledLayers[config.label] = layer;
  });

  const selectedBasemap = getSavedBasemapKey();
  onTileErrorChange?.(false);
  basemapLayers[selectedBasemap].addTo(map);

  const control = Leaflet.control.layers(labeledLayers, undefined, {
    position,
    collapsed: true,
  });
  control.addTo(map);

  const onBaseLayerChange = (event: L.LayersControlEvent) => {
    const matchedKey = (Object.keys(basemapLayers) as BasemapKey[]).find(
      (key) => basemapLayers[key] === event.layer
    );
    if (matchedKey) {
      saveBasemapKey(matchedKey);
      onTileErrorChange?.(failedLayers.has(matchedKey));
    }
  };

  map.on('baselayerchange', onBaseLayerChange);

  return () => {
    map.off('baselayerchange', onBaseLayerChange);
    control.remove();
    errorHandlers.forEach((handler, layer) => layer.off('tileerror', handler));
    (Object.keys(basemapLayers) as BasemapKey[]).forEach((key) => {
      const layer = basemapLayers[key];
      if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    });
  };
}
