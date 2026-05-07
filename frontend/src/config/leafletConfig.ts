// src/config/leafletConfig.ts
export const leafletViewerOptions = {
  MAP: {
    gestureHandling: true,
    scrollWheelZoom: true,
  },
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
