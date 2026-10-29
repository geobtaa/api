import { addPaneLayer } from './panes';
import { BASEMAP_STYLES } from '../config/mapStyles';
/* eslint-disable @typescript-eslint/no-explicit-any -- Adapter for existing GeoJSON and map event contracts. */
/** Application map primitives backed entirely by MapLibre GL. Coordinates at this
 * boundary remain latitude/longitude for existing search/camera contracts. */
import * as ml from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
ml.setWorkerUrl(workerUrl);
import 'maplibre-gl/dist/maplibre-gl.css';
export type LatLng = { lat: number; lng: number };
export type ControlPosition =
  | 'topleft'
  | 'topright'
  | 'bottomleft'
  | 'bottomright';
export type PathOptions = {
  color?: string;
  weight?: number;
  opacity?: number;
  fillColor?: string;
  fillOpacity?: number;
  radius?: number;
  dashArray?: string;
  pane?: string;
  className?: string;
};
export type MapOptions = {
  zoomControl?: boolean;
  dragging?: boolean;
  doubleClickZoom?: boolean;
  touchZoom?: boolean;
  keyboard?: boolean;
  attributionControl?: boolean;
  minZoom?: number;
  maxZoom?: number;
  center?: [number, number];
  zoom?: number;
  gestureHandling?: boolean;
  scrollWheelZoom?: boolean;
};
export type LeafletMouseEvent = { latlng: LatLng; originalEvent: MouseEvent };
export const latLng = (a: number | number[] | LatLng, b?: number): LatLng =>
  Array.isArray(a)
    ? { lat: a[0], lng: a[1] }
    : typeof a === 'number'
      ? { lat: a, lng: b! }
      : a;
export const point = (x: number, y: number) => ({ x, y });
const ll = (v: LatLng | number[]): [number, number] => {
  const p = latLng(v);
  return [p.lng, p.lat];
};
export class LatLngBounds {
  w = Infinity;
  s = Infinity;
  e = -Infinity;
  n = -Infinity;
  constructor(a?: unknown, b?: unknown) {
    if (a) this.extend(a);
    if (b) this.extend(b);
  }
  extend(value: unknown): this {
    if (value instanceof LatLngBounds) {
      this.extend(value.getSouthWest());
      this.extend(value.getNorthEast());
    } else if (Array.isArray(value) && Array.isArray(value[0])) {
      for (const p of value) this.extend(p);
    } else {
      const p = latLng(value as LatLng);
      this.w = Math.min(this.w, p.lng);
      this.e = Math.max(this.e, p.lng);
      this.s = Math.min(this.s, p.lat);
      this.n = Math.max(this.n, p.lat);
    }
    return this;
  }
  isValid() {
    return [this.w, this.s, this.e, this.n].every(Number.isFinite);
  }
  getWest() {
    return this.w;
  }
  getEast() {
    return this.e;
  }
  getSouth() {
    return this.s;
  }
  getNorth() {
    return this.n;
  }
  getSouthWest() {
    return latLng(this.s, this.w);
  }
  getNorthEast() {
    return latLng(this.n, this.e);
  }
  getCenter() {
    return latLng((this.s + this.n) / 2, (this.w + this.e) / 2);
  }
  contains(p: LatLng | number[]) {
    const q = latLng(p);
    return (
      q.lat >= this.s && q.lat <= this.n && q.lng >= this.w && q.lng <= this.e
    );
  }
  intersects(b: LatLngBounds) {
    return this.w <= b.e && this.e >= b.w && this.s <= b.n && this.n >= b.s;
  }
  toBBoxString() {
    return [this.w, this.s, this.e, this.n].join(',');
  }
  toArray(): [[number, number], [number, number]] {
    return [
      [this.w, Math.max(-85.05112878, this.s)],
      [this.e, Math.min(85.05112878, this.n)],
    ];
  }
}
export const latLngBounds = (a?: unknown, b?: unknown) =>
  new LatLngBounds(a, b);
let serial = 0;
export class Map {
  native: ml.Map;
  layers = new Set<Layer>();
  removed = false;
  observer: ResizeObserver;
  constructor(container: HTMLElement, options: MapOptions = {}) {
    this.native = new ml.Map({
      container,
      style: BASEMAP_STYLES.liberty,
      center: options.center ? ll(options.center) : [0, 20],
      zoom: Math.max(0, (options.zoom ?? 2) - 1),
      minZoom: Math.max(0, (options.minZoom ?? 1) - 1),
      cooperativeGestures: true,
      dragPan: options.dragging ?? true,
      doubleClickZoom: options.doubleClickZoom ?? true,
      touchZoomRotate: options.touchZoom ?? true,
      keyboard: options.keyboard ?? true,
      attributionControl: { compact: true },
    });
    const canvas = this.native.getCanvas();
    if (
      typeof canvas.getContext === 'function' &&
      !canvas.getContext('webgl2')
    ) {
      try {
        this.native.remove();
      } catch {
        /* Partially initialized GPU state. */
      }
      throw new Error('WebGL2 is unavailable');
    }
    if (options.zoomControl !== false)
      this.native.addControl(new ml.NavigationControl(), 'top-left');
    this.native.addControl(new ml.FullscreenControl(), 'top-right');
    this.native.on('error', () => {
      if (!this.removed && !this.native.getStyle())
        this.native.setStyle({
          version: 8,
          sources: {},
          layers: [
            {
              id: 'background',
              type: 'background',
              paint: { 'background-color': '#eef2f6' },
            },
          ],
        });
    });
    this.observer = new ResizeObserver(() => this.native.resize());
    this.observer.observe(container);
  }
  addPaneLayer(layer: ml.AddLayerObject, pane?: string) {
    const order = pane ? Number(this.getPane(pane)?.style.zIndex) || 400 : 400;
    addPaneLayer(this.native, layer, order);
  }
  panBy(p: number[], options: { animate?: boolean } = {}) {
    this.native.panBy([p[0], p[1]], {
      duration: options.animate === false ? 0 : 300,
    });
    return this;
  }
  get dragging() {
    return this.native.dragPan;
  }
  get scrollWheelZoom() {
    return this.native.scrollZoom;
  }
  setView(
    center: LatLng | number[],
    zoom: number,
    options: { animate?: boolean } = {}
  ) {
    void options;
    this.native.jumpTo({ center: ll(center), zoom: Math.max(0, zoom - 1) });
    return this;
  }
  flyTo(
    center: LatLng | number[],
    zoom: number,
    options: { duration?: number } = {}
  ) {
    this.native.flyTo({
      center: ll(center),
      zoom: Math.max(0, zoom - 1),
      duration: (options.duration ?? 0.5) * 1000,
    });
    return this;
  }
  fitBounds(
    bounds: LatLngBounds | unknown,
    options: Record<string, unknown> = {}
  ) {
    const b = bounds instanceof LatLngBounds ? bounds : latLngBounds(bounds);
    if (!b.isValid()) return this;
    const pad = (options.padding as number[] | undefined) ?? [20, 20];
    const tl = (options.paddingTopLeft as number[] | undefined) ?? pad;
    const br = (options.paddingBottomRight as number[] | undefined) ?? pad;
    this.native.fitBounds(b.toArray(), {
      padding: { left: tl[0], top: tl[1], right: br[0], bottom: br[1] },
      maxZoom: typeof options.maxZoom === 'number' ? options.maxZoom - 1 : 18,
      duration:
        typeof options.duration === 'number' ? options.duration * 1000 : 0,
    });
    return this;
  }
  flyToBounds(b: LatLngBounds, o: Record<string, unknown> = {}) {
    return this.fitBounds(b, { duration: 0.5, ...o });
  }
  getBounds() {
    const b = this.native.getBounds();
    return latLngBounds(
      latLng(b.getSouth(), b.getWest()),
      latLng(b.getNorth(), b.getEast())
    );
  }
  getZoom() {
    return this.native.getZoom() + 1;
  }
  getCenter() {
    const c = this.native.getCenter();
    return latLng(c.lat, c.lng);
  }
  getMinZoom() {
    return this.native.getMinZoom() + 1;
  }
  getMaxZoom() {
    return this.native.getMaxZoom() + 1;
  }
  getBoundsZoom(b: LatLngBounds, _inside = false, p = { x: 20, y: 20 }) {
    void _inside;
    return (
      (this.native.cameraForBounds(b.toArray(), { padding: Math.max(p.x, p.y) })
        ?.zoom ?? 2) + 1
    );
  }
  project(p: LatLng, z: number) {
    const m = ml.MercatorCoordinate.fromLngLat(ll(p));
    const scale = 512 * 2 ** (z - 1);
    return point(m.x * scale, m.y * scale);
  }
  unproject(p: { x: number; y: number }, z: number) {
    const scale = 512 * 2 ** (z - 1);
    const c = new ml.MercatorCoordinate(p.x / scale, p.y / scale).toLngLat();
    return latLng(c.lat, c.lng);
  }
  containerPointToLatLng(p: { x: number; y: number }) {
    const c = this.native.unproject([p.x, p.y]);
    return latLng(c.lat, c.lng);
  }
  openPopup(p: { openOn: (m: Map) => unknown }) {
    p.openOn(this);
    return this;
  }
  getContainer() {
    return this.native.getContainer();
  }
  invalidateSize() {
    this.native.resize();
    return this;
  }
  whenReady(fn: () => void) {
    // A serialized style is available once layers can be added. isStyleLoaded()
    // also waits for source tiles, and idle may never fire for animated previews.
    if (this.native.getStyle()) fn();
    else
      this.native.once('style.load', () => {
        if (!this.removed) fn();
      });
    return this;
  }

  on(name: string, fn: (e: any) => void) {
    this.native.on(name as any, fn);
    return this;
  }
  off(name: string, fn: (e: any) => void) {
    this.native.off(name as any, fn);
    return this;
  }
  once(name: string, fn: () => void) {
    this.native.once(name as any, fn);
    return this;
  }
  addLayer(l: Layer) {
    l.addTo(this);
    return this;
  }
  removeLayer(l: Layer) {
    l.remove();
    return this;
  }
  hasLayer(l: Layer) {
    return this.layers.has(l);
  }
  eachLayer(fn: (l: Layer) => void) {
    this.layers.forEach(fn);
  }
  getPane(name: string) {
    return this.getContainer().querySelector<HTMLElement>(
      `[data-map-pane="${name}"]`
    );
  }
  createPane(name: string) {
    const p = document.createElement('div');
    p.dataset.mapPane = name;
    this.getContainer().append(p);
    return p;
  }
  addControl(c: Control) {
    c.addTo(this);
    return this;
  }
  removeControl(c: Control) {
    c.remove();
    return this;
  }
  remove() {
    this.removed = true;
    this.observer.disconnect();
    for (const l of [...this.layers]) l.remove();
    this.native.remove();
  }
}
export function showMapError(container: HTMLElement) {
  const message = document.createElement('p');
  message.setAttribute('role', 'alert');
  message.textContent = 'Map unavailable. WebGL is required.';
  container.replaceChildren(message);
}
export const map = (c: HTMLElement, o?: MapOptions) => new Map(c, o);
export class Layer {
  protected host?: Map;
  protected events = new globalThis.Map<string, ((e: any) => void)[]>();
  protected popupContent?: string | HTMLElement;
  addTo(map: Map) {
    this.host = map;
    map.layers.add(this);
    return this;
  }
  remove() {
    this.host?.layers.delete(this);
    this.host = undefined;
    return this;
  }
  on(name: string | Record<string, (e: any) => void>, fn?: (e: any) => void) {
    if (typeof name === 'object') {
      for (const [k, v] of Object.entries(name)) this.on(k, v);
    } else this.events.set(name, [...(this.events.get(name) ?? []), fn!]);
    return this;
  }
  fire(name: string, e: unknown) {
    for (const fn of this.events.get(name) ?? []) fn(e);
  }
  bindPopup(content: string | HTMLElement) {
    this.popupContent = content;
    return this;
  }
  bindTooltip(content: string) {
    return this.bindPopup(content);
  }
}
export class Path extends Layer {
  id = `map-data-${++serial}`;
  options: PathOptions;
  feature: any;
  private cleanup: (() => void)[] = [];
  constructor(feature: any, options: PathOptions = {}) {
    super();
    this.feature = feature;
    this.options = options;
  }
  addTo(map: Map) {
    super.addTo(map);
    map.whenReady(() => {
      if (this.host !== map || map.removed) return;
      this.draw();
    });
    return this;
  }
  private draw() {
    const map = this.host!.native;
    map.addSource(this.id, { type: 'geojson', data: this.feature });
    const type = this.feature.geometry?.type ?? '';
    const polygon = type.includes('Polygon');
    const point = type.includes('Point');
    if (polygon)
      this.host!.addPaneLayer(
        {
          id: this.id + '-fill',
          type: 'fill',
          source: this.id,
          paint: {
            'fill-color':
              this.options.fillColor ?? this.options.color ?? '#2563eb',
            'fill-opacity': this.options.fillOpacity ?? 0.1,
          },
        },
        this.options.pane
      );
    this.host!.addPaneLayer(
      point
        ? {
            id: this.id,
            type: 'circle',
            source: this.id,
            paint: {
              'circle-radius': this.options.radius ?? 6,
              'circle-color': this.options.fillColor ?? '#2563eb',
              'circle-opacity': this.options.fillOpacity ?? 0.7,
              'circle-stroke-color': this.options.color ?? '#2563eb',
              'circle-stroke-width': this.options.weight ?? 2,
            },
          }
        : {
            id: this.id,
            type: 'line',
            source: this.id,
            paint: {
              'line-color': this.options.color ?? '#2563eb',
              'line-width': this.options.weight ?? 2,
              'line-opacity': this.options.opacity ?? 0.8,
              ...(this.options.dashArray
                ? {
                    'line-dasharray': this.options.dashArray
                      .split(',')
                      .map(Number),
                  }
                : {}),
            },
          },
      this.options.pane
    );
    for (const [native, event] of [
      ['mouseenter', 'mouseover'],
      ['mouseleave', 'mouseout'],
      ['click', 'click'],
    ] as const) {
      const fn = (e: any) => {
        map.getCanvas().style.cursor = event === 'mouseout' ? '' : 'pointer';
        const p = e.lngLat;
        this.fire(event, {
          ...e,
          latlng: p ? latLng(p.lat, p.lng) : undefined,
        });
        if (
          event === 'click' &&
          this.popupContent &&
          !e.originalEvent?.ctrlKey &&
          !e.originalEvent?.metaKey
        ) {
          const pop = new ml.Popup().setLngLat(e.lngLat);
          if (typeof this.popupContent === 'string')
            pop.setHTML(this.popupContent);
          else pop.setDOMContent(this.popupContent);
          pop.addTo(map);
        }
      };
      map.on(native, this.id, fn);
      this.cleanup.push(() => map.off(native, this.id, fn));
    }
  }
  private sharedUpdate?: () => void;
  attachShared(map: Map, update: () => void) {
    this.host = map;
    this.sharedUpdate = update;
  }
  detachShared() {
    this.host = undefined;
    this.sharedUpdate = undefined;
  }
  showPopup(position: ml.LngLatLike) {
    if (!this.host || !this.popupContent) return;
    const p = new ml.Popup().setLngLat(position);
    if (typeof this.popupContent === 'string') p.setHTML(this.popupContent);
    else p.setDOMContent(this.popupContent);
    p.addTo(this.host.native);
  }
  setStyle(options: PathOptions) {
    Object.assign(this.options, options);
    if (this.sharedUpdate) {
      this.sharedUpdate();
      return this;
    }
    const m = this.host?.native;
    if (m?.getLayer(this.id)) {
      const point = this.feature.geometry?.type.includes('Point');
      for (const [key, value] of Object.entries(
        point
          ? {
              'circle-color': this.options.fillColor ?? this.options.color,
              'circle-stroke-color': this.options.color,
              'circle-stroke-width': this.options.weight,
            }
          : {
              'line-color': this.options.color,
              'line-width': this.options.weight,
              'line-opacity': this.options.opacity,
            }
      ))
        if (value !== undefined)
          m.setPaintProperty(this.id, key as never, value as never);
      if (m.getLayer(this.id + '-fill')) {
        m.setPaintProperty(
          this.id + '-fill',
          'fill-color',
          this.options.fillColor ?? this.options.color ?? '#2563eb'
        );
        m.setPaintProperty(
          this.id + '-fill',
          'fill-opacity',
          this.options.fillOpacity ?? 0.1
        );
      }
    }
    return this;
  }
  bringToFront() {
    const m = this.host?.native;
    if (m?.getLayer(this.id)) m.moveLayer(this.id);
    return this;
  }
  getBounds() {
    const b = new LatLngBounds();
    const visit = (x: any) => {
      if (Array.isArray(x) && typeof x[0] === 'number')
        b.extend(latLng(x[1], x[0]));
      else if (Array.isArray(x)) x.forEach(visit);
    };
    visit(this.feature.geometry?.coordinates);
    return b;
  }
  remove() {
    const m = this.host?.native;
    this.cleanup.splice(0).forEach((fn) => fn());
    if (m && !this.host?.removed) {
      for (const id of [this.id, this.id + '-fill'])
        if (m.getLayer(id)) m.removeLayer(id);
      if (m.getSource(this.id)) m.removeSource(this.id);
    }
    return super.remove();
  }
}
export type GeoJSONOptions = {
  style?: PathOptions | ((feature: any) => PathOptions);
  onEachFeature?: (feature: any, layer: Path) => void;
  filter?: (feature: any) => boolean;
  pointToLayer?: (feature: any, latlng: LatLng) => Path;
};
export class GeoJSON extends Layer {
  children: Path[] = [];
  private id = `map-data-${++serial}`;
  private cleanup: (() => void)[] = [];
  constructor(data: any, options: GeoJSONOptions = {}) {
    super();
    const features = Array.isArray(data)
      ? data
      : data.type === 'FeatureCollection'
        ? data.features
        : [
            data.type === 'Feature'
              ? data
              : { type: 'Feature', geometry: data, properties: {} },
          ];
    for (const feature of features) {
      if (options.filter && !options.filter(feature)) continue;
      const style =
        typeof options.style === 'function'
          ? options.style(feature)
          : options.style;
      const child = new Path(feature, style);
      options.onEachFeature?.(feature, child);
      this.children.push(child);
    }
  }
  addTo(map: Map) {
    super.addTo(map);
    map.whenReady(() => {
      if (this.host !== map || map.removed) return;
      const native = map.native;
      const data = {
        type: 'FeatureCollection' as const,
        features: this.children.map((c, id) => ({
          ...c.feature,
          id,
          properties: {
            ...c.feature.properties,
            _fill: c.options.fillColor ?? c.options.color ?? '#2563eb',
            _stroke: c.options.color ?? '#2563eb',
            _width: c.options.weight ?? 2,
            _opacity: c.options.opacity ?? 0.8,
            _fillOpacity: c.options.fillOpacity ?? 0.1,
            _radius: c.options.radius ?? 6,
          },
        })),
      };
      native.addSource(this.id, { type: 'geojson', data });
      const paint = (state: string, property: string) =>
        ['coalesce', ['feature-state', state], ['get', property]] as any;
      const ids = [
        this.id + '-fill',
        this.id + '-line',
        this.id + '-point',
        this.id + '-border',
      ];
      map.addPaneLayer({
        id: ids[0],
        type: 'fill',
        source: this.id,
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: {
          'fill-color': paint('fillColor', '_fill'),
          'fill-opacity': paint('fillOpacity', '_fillOpacity'),
        },
      });
      for (const [id, type] of [
        [ids[1], 'LineString'],
        [ids[3], 'Polygon'],
      ])
        map.addPaneLayer({
          id,
          type: 'line',
          source: this.id,
          filter: ['==', ['geometry-type'], type],
          paint: {
            'line-color': paint('color', '_stroke'),
            'line-width': paint('weight', '_width'),
            'line-opacity': paint('opacity', '_opacity'),
          },
        });
      map.addPaneLayer({
        id: ids[2],
        type: 'circle',
        source: this.id,
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
          'circle-radius': paint('radius', '_radius'),
          'circle-color': paint('fillColor', '_fill'),
          'circle-stroke-color': paint('color', '_stroke'),
          'circle-stroke-width': paint('weight', '_width'),
        },
      });
      this.children.forEach((c, id) =>
        c.attachShared(map, () =>
          native.setFeatureState({ source: this.id, id }, c.options)
        )
      );
      for (const layerId of ids.slice(0, 3))
        for (const [nativeName, eventName] of [
          ['mousemove', 'mouseover'],
          ['mouseleave', 'mouseout'],
          ['click', 'click'],
        ]) {
          let last: Path | undefined;
          const fn = (e: any) => {
            const child = this.children[e.features?.[0]?.id];
            if (eventName === 'mouseout') {
              last?.fire('mouseout', e);
              last = undefined;
              native.getCanvas().style.cursor = '';
              return;
            }
            if (!child) return;
            if (eventName === 'mouseover' && last !== child) {
              last?.fire('mouseout', e);
              last = child;
            }
            native.getCanvas().style.cursor = 'pointer';
            child.fire(eventName, {
              ...e,
              latlng: e.lngLat ? latLng(e.lngLat.lat, e.lngLat.lng) : undefined,
            });
            if (eventName === 'click') child.showPopup(e.lngLat);
          };
          native.on(nativeName as any, layerId, fn);
          this.cleanup.push(() => native.off(nativeName as any, layerId, fn));
        }
    });
    return this;
  }
  remove() {
    const map = this.host;
    this.cleanup.splice(0).forEach((fn) => fn());
    this.children.forEach((c) => c.detachShared());
    if (map && !map.removed) {
      for (const id of [
        this.id + '-fill',
        this.id + '-line',
        this.id + '-point',
        this.id + '-border',
      ])
        if (map.native.getLayer(id)) map.native.removeLayer(id);
      if (map.native.getSource(this.id)) map.native.removeSource(this.id);
    }
    return super.remove();
  }
  getBounds() {
    const b = new LatLngBounds();
    this.children.forEach((c) => b.extend(c.getBounds()));
    return b;
  }
  eachLayer(fn: (l: Path) => void) {
    this.children.forEach(fn);
  }
  setStyle(s: PathOptions) {
    this.children.forEach((c) => c.setStyle(s));
    return this;
  }
}

export const geoJSON = (d: any, o?: GeoJSONOptions) => new GeoJSON(d, o);
export class Rectangle extends Path {
  constructor(bounds: LatLngBounds | unknown, options?: PathOptions) {
    const b = bounds instanceof LatLngBounds ? bounds : latLngBounds(bounds);
    super(
      {
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [b.w, b.s],
              [b.e, b.s],
              [b.e, b.n],
              [b.w, b.n],
              [b.w, b.s],
            ],
          ],
        },
      },
      options
    );
  }
}
export const rectangle = (b: unknown, o?: PathOptions) => new Rectangle(b, o);
export const circleMarker = (p: LatLng, o?: PathOptions) =>
  new Path(
    {
      type: 'Feature',
      properties: {},
      geometry: { type: 'Point', coordinates: ll(p) },
    },
    o
  );
export const featureGroup = (layers: Layer[] = []) => {
  const group = new GeoJSON({ type: 'FeatureCollection', features: [] });
  group.children = layers as Path[];
  return group;
};
export const layerGroup = featureGroup;
export class Control {
  options: { position?: ControlPosition };
  element?: HTMLElement;
  host?: Map;
  private nativeControl?: ml.IControl;
  onAdd: () => HTMLElement = () => document.createElement('div');
  constructor(options: { position?: ControlPosition } = {}) {
    this.options = options;
  }
  static extend(def: { onAdd: () => HTMLElement }) {
    return class extends Control {
      onAdd = def.onAdd;
    };
  }
  addTo(map: Map) {
    this.host = map;
    this.nativeControl = {
      onAdd: () => {
        this.element = this.onAdd();
        this.element.classList.add('maplibregl-ctrl');
        return this.element;
      },
      onRemove: () => this.element?.remove(),
    };
    map.native.addControl(
      this.nativeControl,
      (
        {
          topleft: 'top-left',
          topright: 'top-right',
          bottomleft: 'bottom-left',
          bottomright: 'bottom-right',
        } as const
      )[this.options.position ?? 'topleft']
    );
    return this;
  }
  getContainer() {
    return this.element as HTMLDivElement;
  }
  remove() {
    if (this.nativeControl && this.host && !this.host.removed)
      this.host.native.removeControl(this.nativeControl);
    this.nativeControl = undefined;
    this.element?.remove();
    return this;
  }
}
export const DomEvent = {
  stopPropagation: (e: any) => {
    (e.originalEvent ?? e).stopPropagation?.();
  },
  disableClickPropagation: (el: HTMLElement) => {
    for (const n of ['mousedown', 'click', 'dblclick', 'touchstart'])
      el.addEventListener(n, (e) => e.stopPropagation());
  },
  disableScrollPropagation: (el: HTMLElement) =>
    el.addEventListener('wheel', (e) => e.stopPropagation()),
};
export type DivIcon = {
  html: string;
  className?: string;
  iconSize?: number[];
  iconAnchor?: number[];
  popupAnchor?: number[];
};
export const divIcon = (o: DivIcon) => o;
export class Marker extends Layer {
  native: ml.Marker;
  position: LatLng;
  constructor(
    p: LatLng | number[],
    public options: { icon?: DivIcon; title?: string } = {}
  ) {
    super();
    this.position = latLng(p);
    const el = document.createElement('div');
    el.title = options.title ?? '';
    el.setAttribute('aria-label', options.title ?? 'Map result');
    el.setAttribute('role', 'button');
    el.tabIndex = 0;
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.fire('click', { originalEvent: e, latlng: this.position });
      }
    });
    if (options.icon) {
      el.innerHTML = options.icon.html;
      el.className = options.icon.className ?? '';
      if (options.icon.iconSize) {
        el.style.width = options.icon.iconSize[0] + 'px';
        el.style.height = options.icon.iconSize[1] + 'px';
      }
    }
    this.native = new ml.Marker({ element: el, anchor: 'bottom' }).setLngLat(
      ll(p)
    );
    for (const [n, event] of [
      ['mouseenter', 'mouseover'],
      ['mouseleave', 'mouseout'],
      ['click', 'click'],
    ])
      el.addEventListener(n, (e) =>
        this.fire(event, { originalEvent: e, latlng: this.position })
      );
  }
  addTo(m: Map) {
    super.addTo(m);
    this.native.addTo(m.native);
    return this;
  }
  remove() {
    this.native.remove();
    return super.remove();
  }
  getElement() {
    return this.native.getElement();
  }
  getLatLng() {
    return this.position;
  }
  setLatLng(p: LatLng | number[]) {
    this.position = latLng(p);
    this.native.setLngLat(ll(p));
    return this;
  }
  setZIndexOffset(n: number) {
    this.getElement().style.zIndex = String(n);
    return this;
  }
}
export const marker = (
  p: LatLng | number[],
  o?: { icon?: DivIcon; title?: string }
) => new Marker(p, o);
export const popup = () => {
  const p = new ml.Popup();
  return {
    setContent(c: string | HTMLElement) {
      if (typeof c === 'string') p.setHTML(c);
      else p.setDOMContent(c);
      return this;
    },
    setLatLng(l: LatLng) {
      p.setLngLat(ll(l));
      return this;
    },
    openOn(m: Map) {
      p.addTo(m.native);
      return this;
    },
    remove() {
      p.remove();
    },
  };
};
const api = {
  showMapError,
  Map,
  map,
  latLng,
  latLngBounds,
  point,
  GeoJSON,
  geoJSON,
  rectangle,
  circleMarker,
  featureGroup,
  layerGroup,
  Control,
  DomEvent,
  divIcon,
  marker,
  popup,
};
export default api;
