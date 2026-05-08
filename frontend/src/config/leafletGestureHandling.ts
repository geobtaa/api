import type * as Leaflet from 'leaflet';

const REGISTERED_FLAG = '__btaaGestureHandlingRegistered';
const SCROLL_WARNING_CLASS = 'leaflet-gesture-handling-scroll-warning';
const SCROLL_WARNING_DURATION_MS = 1000;

type LeafletMapConstructor = typeof Leaflet.Map & {
  [REGISTERED_FLAG]?: boolean;
};

type GestureHandlerInstance = Leaflet.Handler & {
  _map: Leaflet.Map;
  _gestureScrollTimer?: number;
  _handleScroll: (event: Event) => void;
  _handleMouseOut: () => void;
};

export function registerLeafletGestureHandling(
  LeafletNamespace: typeof Leaflet
): void {
  const mapConstructor = LeafletNamespace.Map as LeafletMapConstructor;

  if (mapConstructor[REGISTERED_FLAG]) return;
  if (typeof window === 'undefined') return;

  const GestureHandling = LeafletNamespace.Handler.extend({
    addHooks(this: GestureHandlerInstance) {
      const map = this._map;
      const container = map.getContainer();
      const isMac = navigator.platform.toUpperCase().includes('MAC');

      container.setAttribute(
        'data-gesture-handling-scroll-content',
        isMac
          ? 'Use command + scroll to zoom the map'
          : 'Use control + scroll to zoom the map'
      );
      map.scrollWheelZoom.disable();

      LeafletNamespace.DomEvent.on(
        container,
        'wheel',
        this._handleScroll,
        this
      );
      map.on('mouseout', this._handleMouseOut, this);
    },

    removeHooks(this: GestureHandlerInstance) {
      const map = this._map;
      const container = map.getContainer();

      if (this._gestureScrollTimer !== undefined) {
        window.clearTimeout(this._gestureScrollTimer);
      }
      LeafletNamespace.DomUtil.removeClass(container, SCROLL_WARNING_CLASS);
      LeafletNamespace.DomEvent.off(
        container,
        'wheel',
        this._handleScroll,
        this
      );
      map.off('mouseout', this._handleMouseOut, this);
      map.scrollWheelZoom.enable();
    },

    _handleScroll(this: GestureHandlerInstance, event: Event) {
      const wheelEvent = event as WheelEvent;
      const map = this._map;
      const container = map.getContainer();

      if (wheelEvent.ctrlKey || wheelEvent.metaKey) {
        LeafletNamespace.DomEvent.preventDefault(wheelEvent);
        LeafletNamespace.DomUtil.removeClass(container, SCROLL_WARNING_CLASS);
        map.scrollWheelZoom.enable();
        return;
      }

      map.scrollWheelZoom.disable();
      LeafletNamespace.DomUtil.addClass(container, SCROLL_WARNING_CLASS);
      window.clearTimeout(this._gestureScrollTimer);
      this._gestureScrollTimer = window.setTimeout(() => {
        LeafletNamespace.DomUtil.removeClass(container, SCROLL_WARNING_CLASS);
      }, SCROLL_WARNING_DURATION_MS);
    },

    _handleMouseOut(this: GestureHandlerInstance) {
      const map = this._map;
      const container = map.getContainer();

      map.scrollWheelZoom.disable();
      LeafletNamespace.DomUtil.removeClass(container, SCROLL_WARNING_CLASS);
    },
  });

  LeafletNamespace.Map.addInitHook(
    'addHandler',
    'gestureHandling',
    GestureHandling
  );
  mapConstructor[REGISTERED_FLAG] = true;
}
