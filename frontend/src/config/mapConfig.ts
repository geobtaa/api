// src/config/mapConfig.ts
import type * as MapTypes from '../mapping/maplibre';

export type MapInteractionOptions = MapTypes.MapOptions & {
  gestureHandling: true;
  scrollWheelZoom: true;
};

export const mapInteractionOptions: MapInteractionOptions = {
  gestureHandling: true,
  scrollWheelZoom: true,
};
