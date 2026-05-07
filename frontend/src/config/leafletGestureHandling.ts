import type * as Leaflet from 'leaflet';
import { GestureHandling } from 'leaflet-gesture-handling';
import 'leaflet-gesture-handling/dist/leaflet-gesture-handling.css';

const REGISTERED_FLAG = '__btaaGestureHandlingRegistered';

type LeafletMapConstructor = typeof Leaflet.Map & {
  [REGISTERED_FLAG]?: boolean;
};

export function registerLeafletGestureHandling(
  LeafletNamespace: typeof Leaflet
) {
  const mapConstructor = LeafletNamespace.Map as LeafletMapConstructor;

  if (mapConstructor[REGISTERED_FLAG]) return;

  LeafletNamespace.Map.addInitHook(
    'addHandler',
    'gestureHandling',
    GestureHandling
  );
  mapConstructor[REGISTERED_FLAG] = true;
}
