/* eslint-disable @typescript-eslint/no-explicit-any -- Adapter for existing GeoJSON and map event contracts. */
import { Map, Marker, latLng } from './maplibre';
/** Spread coincident result pins in screen space, restoring their coordinates
 * when the camera moves or the results change. */
export default class Spiderfier {
  private markers: Marker[] = [];
  private listeners = new globalThis.Map<string, ((...a: any[]) => void)[]>();
  private originals = new globalThis.Map<Marker, ReturnType<typeof latLng>>();
  constructor(private map: Map) {
    map.on('movestart', this.restore);
  }
  addListener(n: string, f: (...a: any[]) => void) {
    this.listeners.set(n, [...(this.listeners.get(n) ?? []), f]);
  }
  removeListener(n: string, f: (...a: any[]) => void) {
    this.listeners.set(
      n,
      (this.listeners.get(n) ?? []).filter((x) => x !== f)
    );
  }
  addMarker(m: Marker) {
    this.markers.push(m);
    m.on('click', () => {
      const p = this.map.native.project([m.getLatLng().lng, m.getLatLng().lat]);
      const near = this.markers.filter((x) => {
        const q = this.map.native.project([
          x.getLatLng().lng,
          x.getLatLng().lat,
        ]);
        return Math.hypot(q.x - p.x, q.y - p.y) < 24;
      });
      if (near.length > 1 && !this.originals.size) {
        near.forEach((x, i) => {
          this.originals.set(x, x.getLatLng());
          const angle = (i * 2 * Math.PI) / near.length;
          const c = this.map.native.unproject([
            p.x + 40 * Math.cos(angle),
            p.y + 40 * Math.sin(angle),
          ]);
          x.setLatLng(latLng(c.lat, c.lng));
        });
        return;
      }
      this.listeners.get('click')?.forEach((f) => f(m));
    });
  }
  restore = () => {
    this.originals.forEach((p, m) => m.setLatLng(p));
    this.originals.clear();
    this.listeners.get('unspiderfy')?.forEach((f) => f());
  };
  clearMarkers() {
    this.restore();
    this.markers = [];
  }
  destroy() {
    this.clearMarkers();
    this.map.off('movestart', this.restore);
  }
}
