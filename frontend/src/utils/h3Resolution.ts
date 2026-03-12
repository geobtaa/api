/** Map Leaflet zoom to H3 resolution so hex size changes more visibly when zooming (e.g. into Chicago). */
export function zoomToResolution(zoom: number): number {
  if (zoom <= 3) return 2;
  if (zoom <= 4) return 3;
  if (zoom <= 6) return 4;
  if (zoom <= 8) return 5;
  if (zoom <= 10) return 6;
  if (zoom <= 12) return 7;
  return 8;
}
