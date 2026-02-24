import { useEffect } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';
import { attachBasemapSwitcher } from '../../config/basemaps';

interface BasemapSwitcherControlProps {
  position?: L.ControlPosition;
}

export function BasemapSwitcherControl({
  position = 'topleft',
}: BasemapSwitcherControlProps) {
  const map = useMap();

  useEffect(() => {
    return attachBasemapSwitcher(map, L, position);
  }, [map, position]);

  return null;
}
