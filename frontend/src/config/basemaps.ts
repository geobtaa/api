import Cookies from 'js-cookie';
import type { Map, ControlPosition } from '../mapping/maplibre';
import { Control } from '../mapping/maplibre';
import { BASEMAP_STYLES } from './mapStyles';
export { BASEMAP_STYLES } from './mapStyles';
export type BasemapKey = keyof typeof BASEMAP_STYLES;
export const getAvailableBasemapKeys = () =>
  Object.keys(BASEMAP_STYLES) as BasemapKey[];
export function getSavedBasemapKey(): BasemapKey {
  const key = Cookies.get('preferred_basemap');
  return key && Object.hasOwn(BASEMAP_STYLES, key)
    ? (key as BasemapKey)
    : 'liberty';
}
export function attachBasemapSwitcher(
  map: Map,
  _namespace: unknown,
  position: ControlPosition = 'topright'
) {
  const control = new Control({ position });
  let disposed = false;
  let generation = 0;
  let basemapSources = new Set<string>();
  let basemapLayers = new Set<string>();
  const apply = (key: BasemapKey) => {
    const request = ++generation;
    const old = map.native.getStyle();
    if (!old) return;
    fetch(BASEMAP_STYLES[key])
      .then((r) => {
        if (!r.ok) throw Error('Basemap unavailable');
        return r.json();
      })
      .then((style) => {
        if (disposed || map.removed || request !== generation) return;
        const current = map.native.getStyle();
        const sources = Object.fromEntries(
          Object.entries(current.sources).filter(
            ([id]) => !basemapSources.has(id)
          )
        );
        const layers = current.layers.filter(
          (layer) => !basemapLayers.has(layer.id)
        );
        basemapSources = new Set(Object.keys(style.sources));
        basemapLayers = new Set(
          style.layers.map((layer: { id: string }) => layer.id)
        );
        const center = map.native.getCenter?.();
        const camera = center
          ? {
              center: [center.lng, center.lat] as [number, number],
              zoom: map.native.getZoom(),
              bearing: map.native.getBearing(),
              pitch: map.native.getPitch(),
            }
          : {};
        map.native.setStyle({
          ...style,
          ...camera,
          sources: { ...style.sources, ...sources },
          layers: [...style.layers, ...layers],
        });
        Cookies.set('preferred_basemap', key, { expires: 365 });
      })
      .catch(console.warn);
  };
  map.whenReady(() => {
    const initial = map.native.getStyle();
    basemapSources = new Set(
      Object.keys(initial.sources).filter((id) => !id.startsWith('map-data-'))
    );
    basemapLayers = new Set(
      initial.layers
        .filter(
          (layer) =>
            !('source' in layer && String(layer.source).startsWith('map-data-'))
        )
        .map((layer) => layer.id)
    );
    const saved = getSavedBasemapKey();
    if (saved !== 'liberty') apply(saved);
  });
  let removeOutsideListener = () => {};
  control.onAdd = () => {
    const div = document.createElement('div');
    div.className = 'maplibregl-ctrl maplibregl-ctrl-group geo-map-basemap';
    div.style.position = 'relative';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'geo-map-control-button';
    button.title = 'Basemaps';
    button.setAttribute('aria-label', 'Change basemap');
    button.setAttribute('aria-haspopup', 'true');
    button.setAttribute('aria-expanded', 'false');
    button.innerHTML =
      '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 10 5-10 5L2 8l10-5Z"/><path d="m2 12 10 5 10-5M2 16l10 5 10-5"/></svg>';
    const panel = document.createElement('div');
    panel.hidden = true;
    panel.setAttribute('role', 'radiogroup');
    panel.setAttribute('aria-label', 'Basemap style');
    panel.style.cssText =
      'min-width:180px;padding:8px;background:white;color:#111827;border:1px solid #b9b9b9;border-radius:4px;box-shadow:0 1px 5px #0004;';
    const setOpen = (open: boolean, focus = false) => {
      // Expand in place, as the production layers control does. The button and
      // options share one continuous hit area; there is no hover gap to cross.
      button.hidden = open;
      button.style.display = open ? 'none' : '';
      panel.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
      if (open && focus)
        panel.querySelector<HTMLInputElement>('input:checked')?.focus();
    };
    const name = 'basemap-' + Math.random().toString(36).slice(2);
    for (const key of getAvailableBasemapKeys()) {
      const label = document.createElement('label');
      label.style.cssText =
        'display:flex;align-items:center;gap:7px;padding:4px;white-space:nowrap;font:13px/1.4 system-ui;cursor:pointer;';
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = name;
      radio.value = key;
      radio.checked = key === getSavedBasemapKey();
      radio.onchange = () => {
        if (radio.checked) {
          apply(key);
          setOpen(false);
          button.focus();
        }
      };
      label.append(
        radio,
        document.createTextNode(
          'OpenFreeMap ' + key[0].toUpperCase() + key.slice(1)
        )
      );
      panel.append(label);
    }
    button.onclick = () => setOpen(true, true);
    div.onmouseenter = () => setOpen(true);
    div.onmouseleave = (event) => {
      if (
        event.relatedTarget instanceof Node &&
        div.contains(event.relatedTarget)
      )
        return;
      if (!panel.contains(document.activeElement)) setOpen(false);
    };
    div.onkeydown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
        button.focus();
      }
    };
    const outside = (event: PointerEvent) => {
      if (!div.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    removeOutsideListener = () =>
      document.removeEventListener('pointerdown', outside);
    div.append(button, panel);
    return div;
  };
  control.addTo(map);
  return () => {
    disposed = true;
    removeOutsideListener();
    control.remove();
  };
}
