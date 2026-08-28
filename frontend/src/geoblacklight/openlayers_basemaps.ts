const openStreetMap = {
  url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attributions:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19,
} as const;

export default {
  // GeoBlacklight 5.1.0 hard-codes this lookup key as its fallback.
  positron: openStreetMap,
} as const;
