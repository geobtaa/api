/**
 * Fix for Leaflet default marker icons in production (Vite/Kamal).
 *
 * Leaflet's L.Icon.Default uses relative paths (e.g. marker-icon-2x.png) which
 * resolve correctly in Vite dev (node_modules served) but 404 in production
 * where the built app is served from /assets/ and no leaflet images exist.
 *
 * This module patches L.Icon.Default to use CDN URLs. Import it once at app
 * startup (e.g. main.tsx) so all Leaflet usage—homepage featured map,
 * MapPage, resource leaflet-viewer, etc.—gets correct marker icons.
 */
import L from 'leaflet';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});
