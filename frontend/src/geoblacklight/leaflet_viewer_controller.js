import Leaflet, { map } from 'leaflet';
import BaseLeafletViewerController from '@geoblacklight/frontend/app/javascript/geoblacklight/controllers/leaflet_viewer_controller';
import Sleep from 'geoblacklight/leaflet/controls/sleep';
import { registerLeafletGestureHandling } from '../config/leafletGestureHandling';

registerLeafletGestureHandling(Leaflet);

export default class LeafletViewerController extends BaseLeafletViewerController {
  // Keep the GeoBlacklight controller behavior, but let local MAP options reach L.map.
  async loadMap() {
    if (this.map) return;

    const sleepSettings = this.optionsValue.SLEEP || { SLEEP: false };
    const mapSettings = this.optionsValue.MAP || {};
    this.map = map(this.element, { ...sleepSettings, ...mapSettings });
    if (sleepSettings.SLEEP) this.map.addHandler('SLEEP', Sleep);

    this.map.addLayer(this.basemap);
    this.map.addLayer(this.overlay);
    this.fitBounds(this.bounds);
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
}
