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

export type BasemapKey = keyof typeof BASEMAP_DEFINITIONS | 'cartoLight';

function getBasemapDefinitions(): Partial<
  Record<BasemapKey, BasemapDefinition>
> {
  const definitions: Partial<Record<BasemapKey, BasemapDefinition>> = {
    ...BASEMAP_DEFINITIONS,
  };
  const cartoBasemapKey = (import.meta.env.VITE_CARTO_BASEMAP_KEY || '').trim();

  if (cartoBasemapKey) {
    definitions.cartoLight = {
      label: 'Carto Light',
      url: `https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(cartoBasemapKey)}`,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      options: {
        subdomains: 'abcd',
        maxZoom: 20,
      },
    };
  }

  return definitions;
}

export function getAvailableBasemapKeys(): BasemapKey[] {
  return Object.keys(getBasemapDefinitions()) as BasemapKey[];
}

function isBasemapKey(
  value: string,
  definitions: Partial<Record<BasemapKey, BasemapDefinition>>
): value is BasemapKey {
  return Object.prototype.hasOwnProperty.call(definitions, value);
}

export function getSavedBasemapKey(): BasemapKey {
  const definitions = getBasemapDefinitions();
  const saved = Cookies.get(BASEMAP_COOKIE_NAME);
  if (saved && isBasemapKey(saved, definitions)) {
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
  const config = getBasemapDefinitions()[key];
  if (!config) {
    throw new Error(`Basemap "${key}" is not configured`);
  }
  return Leaflet.tileLayer(config.url, {
    attribution: config.attribution,
    ...config.options,
  });
}

export function attachBasemapSwitcher(
  map: L.Map,
  Leaflet: typeof L,
  position: L.ControlPosition = 'topleft'
): () => void {
  const definitions = getBasemapDefinitions();
  const basemapLayers = {} as Record<BasemapKey, L.TileLayer>;
  const labeledLayers: Record<string, L.TileLayer> = {};

  (Object.keys(definitions) as BasemapKey[]).forEach((key) => {
    const config = definitions[key];
    if (!config) return;
    const layer = createBasemapLayer(Leaflet, key);
    basemapLayers[key] = layer;
    labeledLayers[config.label] = layer;
  });

  const selectedBasemap = getSavedBasemapKey();
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
    }
  };

  map.on('baselayerchange', onBaseLayerChange);

  return () => {
    map.off('baselayerchange', onBaseLayerChange);
    control.remove();
    (Object.keys(basemapLayers) as BasemapKey[]).forEach((key) => {
      const layer = basemapLayers[key];
      if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    });
  };
}
