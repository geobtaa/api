/* eslint-disable @typescript-eslint/no-explicit-any -- Adapter for existing GeoJSON and map event contracts. */
import {
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import * as M from './maplibre';
import { MapContext } from './context';
export const LeafletContext = MapContext;
export function useMap() {
  const c = useContext(MapContext);
  if (!c) throw new Error('Map component requires a MapContainer');
  return c.map;
}
export function useMapEvents(events: Record<string, (e: any) => void>) {
  const map = useMap();
  useEffect(() => {
    for (const [n, f] of Object.entries(events)) map.on(n, f);
    return () => {
      for (const [n, f] of Object.entries(events)) map.off(n, f);
    };
  }, [map, events]);
  return map;
}
export function MapContainer({
  children,
  className,
  style,
  center,
  zoom,
  zoomControl = true,
  ...options
}: M.MapOptions & {
  children?: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const initialOptions = useRef({ ...options, center, zoom, zoomControl });
  const [map, setMap] = useState<M.Map | null>(null);
  const [error, setError] = useState(false);
  const context = useMemo(() => (map ? { map } : null), [map]);
  useEffect(() => {
    if (!ref.current) return;
    let instance: M.Map;
    try {
      instance = new M.Map(ref.current, initialOptions.current);
      setMap(instance);
    } catch {
      ref.current.replaceChildren();
      setError(true);
      return;
    }
    return () => instance.remove();
  }, []);
  return (
    <div className={className} style={{ position: 'relative', ...style }}>
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} />
      {error && <p role="alert">Map unavailable. WebGL is required.</p>}
      {context && (
        <MapContext.Provider value={context}>{children}</MapContext.Provider>
      )}
    </div>
  );
}
export function GeoJSON({
  data,
  style,
  onEachFeature,
  filter,
}: M.GeoJSONOptions & { data: any }) {
  const map = useMap();
  useEffect(() => {
    const l = M.geoJSON(data, { style, onEachFeature, filter }).addTo(map);
    return () => {
      l.remove();
    };
  }, [map, data, style, onEachFeature, filter]);
  return null;
}
export function Rectangle({ bounds, pathOptions }: any) {
  const map = useMap();
  useEffect(() => {
    const l = M.rectangle(bounds, pathOptions).addTo(map);
    return () => {
      l.remove();
    };
  }, [map, bounds, pathOptions]);
  return null;
}
export function ZoomControl({
  position = 'topleft',
}: {
  position?: M.ControlPosition;
}) {
  const map = useMap();
  useEffect(() => {
    const c = new M.Control({ position });
    c.onAdd = () => {
      const div = document.createElement('div');
      div.className = 'maplibregl-ctrl maplibregl-ctrl-group';
      for (const [text, delta] of [
        ['+', 1],
        ['−', -1],
      ] as const) {
        const b = document.createElement('button');
        b.textContent = text;
        b.setAttribute('aria-label', delta > 0 ? 'Zoom in' : 'Zoom out');
        b.onclick = (event) =>
          map.native.zoomTo(
            map.native.getZoom() + delta,
            {},
            { originalEvent: event }
          );
        div.append(b);
      }
      return div;
    };
    c.addTo(map);
    return () => {
      c.remove();
    };
  }, [map, position]);
  return null;
}
