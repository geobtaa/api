export const DEFAULT_US_CENTER: [number, number] = [39.8283, -98.5795];
export const DEFAULT_US_ZOOM = 3;
export const FIT_PADDING: [number, number] = [20, 20];

/** Match production's [44, -80] camera plus a 400px eastward pan at
 * legacy zoom 3 (256px tiles). Resolve that offset into the initial longitude
 * so MapLibre opens in the same place without generating startup movement. */
const HOME_PAGE_BASE_CENTER: [number, number] = [44, -80];
const HOME_PAGE_EASTWARD_OFFSET_PX = 400;
export const HOME_PAGE_MAP_CENTER: [number, number] = [
  HOME_PAGE_BASE_CENTER[0],
  HOME_PAGE_BASE_CENTER[1] +
    (HOME_PAGE_EASTWARD_OFFSET_PX / (256 * 2 ** DEFAULT_US_ZOOM)) * 360,
];
