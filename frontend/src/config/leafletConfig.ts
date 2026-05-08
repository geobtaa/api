// src/config/leafletConfig.ts
import type * as Leaflet from 'leaflet';

export type LeafletGestureMapOptions = Leaflet.MapOptions & {
  gestureHandling: true;
  scrollWheelZoom: true;
};

export const leafletGestureMapOptions: LeafletGestureMapOptions = {
  gestureHandling: true,
  scrollWheelZoom: true,
};

export const leafletViewerOptions = {
  MAP: leafletGestureMapOptions,
  BOUNDSOVERLAY: {
    INDEX: { color: '#3388ff' },
    SHOW: { color: '#3388ff' },
    STATIC_MAP: { color: '#3388ff' },
  },
  SELECTED_COLOR: '#2C7FB8',
  SLEEP: {
    SLEEP: false,
  },
  LAYERS: {
    DETECT_RETINA: true,
    INDEX: {
      DEFAULT: {
        color: '#7FCDBB',
        weight: 1,
        radius: 4,
        sr_color_name: 'Green',
      },
      UNAVAILABLE: {
        color: '#EDF8B1',
        sr_color_name: 'Yellow',
      },
      SELECTED: {
        color: '#2C7FB8',
        sr_color_name: 'Blue',
      },
    },
  },
};
