import Leaflet, { map } from 'leaflet';
import BaseLeafletViewerController from '@geoblacklight/frontend/app/javascript/geoblacklight/controllers/leaflet_viewer_controller';
import Sleep from 'geoblacklight/leaflet/controls/sleep';
import { registerLeafletGestureHandling } from '../config/leafletGestureHandling';

let leafletIiifPromise;

async function ensureLeafletIiif() {
  if (Leaflet.tileLayer.iiif) return;

  globalThis.L = Leaflet;
  if (typeof window !== 'undefined') window.L = Leaflet;

  leafletIiifPromise ||= import('leaflet-iiif');
  await leafletIiifPromise;

  if (!Leaflet.tileLayer.iiif) {
    throw new Error('leaflet-iiif did not register L.tileLayer.iiif');
  }
}

export default class LeafletViewerController extends BaseLeafletViewerController {
  get isIiifImage() {
    return this.protocolValue === 'Iiif';
  }

  // Keep the GeoBlacklight controller behavior, but let local MAP options reach L.map.
  async loadMap() {
    if (this.map) return;

    registerLeafletGestureHandling(Leaflet);

    const sleepSettings = this.optionsValue.SLEEP || { SLEEP: false };
    const mapSettings = this.optionsValue.MAP || {};
    const iiifSettings = this.isIiifImage
      ? {
          center: [0, 0],
          crs: Leaflet.CRS.Simple,
          zoom: 0,
        }
      : {};
    this.map = map(this.element, {
      ...sleepSettings,
      ...mapSettings,
      ...iiifSettings,
    });
    if (sleepSettings.SLEEP) this.map.addHandler('SLEEP', Sleep);

    if (!this.isIiifImage) this.map.addLayer(this.basemap);
    this.map.addLayer(this.overlay);
    if (!this.isIiifImage) this.fitBounds(this.bounds);
    this.map.options.selected_color =
      this.optionsValue.SELECTED_COLOR || 'blue';

    if (this.availableValue && this.protocolValue) {
      await this.addPreviewOverlay();
      this.addInspection();
    } else if (this.drawInitialBoundsValue && this.bounds) {
      this.addBoundsOverlay(this.bounds);
    }

    this.addControls();

    if (this.protocolValue === 'IndexMap') {
      this.fitBounds(this.previewOverlay.getBounds());
    }

    if (this.map.geosearch) this.map.geosearch.enable();

    this.dispatch('loaded');
  }

  async getPreviewOverlay(protocol, url, options) {
    if (protocol === 'Iiif') {
      await ensureLeafletIiif();
      return Leaflet.tileLayer.iiif(url, {
        ...options,
        fitBounds: true,
        setMaxBounds: true,
      });
    }

    return super.getPreviewOverlay(protocol, url, options);
  }
}
