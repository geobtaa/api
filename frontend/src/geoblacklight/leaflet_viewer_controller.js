import Leaflet, { map } from 'leaflet';
import 'leaflet-fullscreen';
import BaseLeafletViewerController from '@geoblacklight/frontend/app/javascript/geoblacklight/controllers/leaflet_viewer_controller';
import Sleep from 'geoblacklight/leaflet/controls/sleep';
import { registerLeafletGestureHandling } from '../config/leafletGestureHandling';
import {
  fetchIiifImageInfo,
  getIiifImageApiVersion,
  getIiifImageBounds,
  getIiifLeafletMapOptions,
  getIiifMaxNativeZoom,
  getIiifTileFormat,
  getIiifTileSize,
  getIiifTileUrl,
  IIIF_MIN_ZOOM,
  normalizeIiifImageServiceId,
  resizeIiifTileToNaturalSize,
} from './iiif_image_layer';

function buildIiifTileLayer(options) {
  const IiifTileLayer = Leaflet.TileLayer.extend({
    getTileUrl(coords) {
      return getIiifTileUrl({
        coords,
        imageApiVersion: this.options.imageApiVersion,
        imageHeight: this.options.imageHeight,
        imageWidth: this.options.imageWidth,
        maxNativeZoom: this.maxNativeZoom,
        serviceId: this.options.serviceId,
        tileFormat: this.options.tileFormat,
        tileQuality: this.options.tileQuality,
        tileSize: this.options.tileSize,
      });
    },
  });

  const layer = new IiifTileLayer('', {
    ...options,
    noWrap: true,
    updateWhenIdle: true,
  });
  layer.maxNativeZoom = options.maxNativeZoom || 0;
  layer.on('tileload', ({ tile }) => {
    resizeIiifTileToNaturalSize(tile, options.tileSize);
  });
  return layer;
}

export default class LeafletViewerController extends BaseLeafletViewerController {
  get isIiifImage() {
    return this.protocolValue === 'Iiif';
  }

  connect() {
    if (!this.isIiifImage) {
      super.connect();
      return;
    }

    Leaflet.Icon.Default.imagePath =
      'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/';
    this.overlay = Leaflet.layerGroup();
    this.bounds = null;
    void this.loadMap().catch((error) => {
      console.error('Failed to load IIIF image viewer:', error);
    });
  }

  disconnect() {
    if (!this.isIiifImage) return;

    if (this.iiifCleanup) {
      this.iiifCleanup();
      this.iiifCleanup = null;
    }
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
  }

  // Keep the GeoBlacklight controller behavior, but let local MAP options reach L.map.
  async loadMap() {
    if (this.map) return;

    registerLeafletGestureHandling(Leaflet);

    if (this.isIiifImage) {
      await this.loadIiifImageMap();
      return;
    }

    const sleepSettings = this.optionsValue.SLEEP || { SLEEP: false };
    const mapSettings = this.optionsValue.MAP || {};
    this.map = map(this.element, {
      ...sleepSettings,
      ...mapSettings,
    });
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

  async loadIiifImageMap() {
    if (!this.availableValue || !this.urlValue) return;

    const info = await fetchIiifImageInfo(this.urlValue);
    const width = info.width;
    const height = info.height;
    if (!width || !height) {
      throw new Error('IIIF info.json is missing image dimensions.');
    }

    const tileSize = getIiifTileSize(info);
    const maxNativeZoom = getIiifMaxNativeZoom(width, height, tileSize);
    const imageBounds = getIiifImageBounds(
      Leaflet,
      width,
      height,
      maxNativeZoom
    );
    const sleepSettings = this.optionsValue.SLEEP || { SLEEP: false };
    const mapSettings = this.optionsValue.MAP || {};

    this.map = map(
      this.element,
      getIiifLeafletMapOptions(
        Leaflet,
        imageBounds,
        maxNativeZoom,
        sleepSettings,
        mapSettings
      )
    );
    if (sleepSettings.SLEEP) this.map.addHandler('SLEEP', Sleep);

    this.previewOverlay = buildIiifTileLayer({
      bounds: imageBounds,
      imageApiVersion: getIiifImageApiVersion(info),
      imageHeight: height,
      imageWidth: width,
      maxNativeZoom,
      maxZoom: maxNativeZoom,
      minNativeZoom: 0,
      minZoom: IIIF_MIN_ZOOM,
      serviceId: normalizeIiifImageServiceId(this.urlValue, info),
      tileFormat: getIiifTileFormat(info),
      tileQuality: 'default',
      tileSize,
    });
    this.overlay.addTo(this.map);
    this.overlay.addLayer(this.previewOverlay);
    this.map.options.selected_color =
      this.optionsValue.SELECTED_COLOR || 'blue';
    this.scheduleIiifRefits(imageBounds);
    this.addIiifControls();
    this.dispatch('loaded');
  }

  scheduleIiifRefits(imageBounds) {
    const refit = () => {
      if (!this.map) return;

      this.map.invalidateSize();
      this.map.fitBounds(imageBounds, {
        animate: false,
        padding: [16, 16],
      });
      this.bounds = imageBounds;
      this.element.dataset.bounds = imageBounds.toBBoxString();
    };

    const timeoutIds = [0, 100, 300].map((delay) =>
      window.setTimeout(refit, delay)
    );
    let firstFrame = null;
    let secondFrame = null;

    if (typeof window.requestAnimationFrame === 'function') {
      firstFrame = window.requestAnimationFrame(() => {
        refit();
        secondFrame = window.requestAnimationFrame(refit);
      });
    }

    const resizeObserver =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(refit)
        : null;
    resizeObserver?.observe(this.element);
    refit();

    this.iiifCleanup = () => {
      if (firstFrame !== null) window.cancelAnimationFrame(firstFrame);
      if (secondFrame !== null) window.cancelAnimationFrame(secondFrame);
      timeoutIds.forEach((id) => window.clearTimeout(id));
      resizeObserver?.disconnect();
    };
  }

  addIiifControls() {
    const fullscreenControl = this.getControl('Fullscreen');
    if (fullscreenControl) this.addControl(fullscreenControl);
  }
}
