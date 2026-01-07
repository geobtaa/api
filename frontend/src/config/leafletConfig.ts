// src/config/leafletConfig.ts
export const leafletViewerOptions = {
  MAP: {},
  BOUNDSOVERLAY: {
    INDEX: { color: '#3388ff' },
    SHOW: { color: '#3388ff' },
    STATIC_MAP: { color: '#3388ff' },
  },
  SELECTED_COLOR: '#2C7FB8',
  SLEEP: {
    SLEEP: true,
    MARGIN_DISTANCE: 100,
    SLEEPTIME: 750,
    WAKETIME: 750,
    HOVERTOWAKE: false,
    MESSAGE: 'Click to Wake',
    BACKGROUND: 'rgba(214, 214, 214, .7)',
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
