export type FeaturedMapCameraMode = 'fitBounds' | 'flyTo';

export interface FeaturedMapCameraConfig {
  /**
   * flyTo: use explicit center/zoom (or derived center/zoom if one is omitted)
   * fitBounds: fit the resource bbox into the viewport
   */
  mode?: FeaturedMapCameraMode;
  center?: [number, number];
  zoom?: number;
  minZoom?: number;
  maxZoom?: number;
  padding?: [number, number];
  paddingTopLeft?: [number, number];
  paddingBottomRight?: [number, number];
  duration?: number;
  verticalOffsetPx?: number;
}

export interface FeaturedItemConfig {
  /** Resource ID used by /resources/{id} */
  id: string;
  /** Optional per-item camera overrides for homepage featured fly behavior */
  camera?: FeaturedMapCameraConfig;
}

/**
 * Featured homepage items with optional map camera overrides.
 * Leave center/zoom undefined to auto-derive from bbox at runtime.
 */
export const FEATURED_ITEMS: FeaturedItemConfig[] = [
  {
    id: 'c69b75a12ca64324a0109d48db735f6d_0', // WebServices
    camera: {
      mode: 'flyTo',
      minZoom: 3,
      maxZoom: 10,
      padding: [24, 24],
      verticalOffsetPx: -120,
      duration: 1,
    },
  },
  {
    id: 'eee6150b-ce2f-4837-9d17-ce72a0c1c26f', // Imagery
    camera: { 
      mode: 'flyTo',
      minZoom: 7,
      maxZoom: 14,
      duration: 1.5
    },
  },
  {
    id: '11c34a17-bc6d-429c-8770-64888ccb5302', // Allmaps georeferenced map (resource_allmaps)
    camera: { mode: 'fitBounds', duration: 1.5 },
  },
  {
    id: 'p16022coll289:22', // Allmaps georeferenced map
    camera: { mode: 'fitBounds', duration: 1.5 },
  },
  {
    id: 'ee251fd05e504374831ab4ddf5e589f2_2', // Beach segment up and down coast points (ArcGIS FeatureLayer)
    camera: { mode: 'fitBounds', duration: 1.5 },
  },
];

/** Backward-compatible ID list for existing consumers/tests. */
export const FEATURED_RESOURCE_IDS: string[] = FEATURED_ITEMS.map(
  (item) => item.id
);
