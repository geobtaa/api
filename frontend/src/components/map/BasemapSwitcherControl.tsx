import { useEffect } from 'react';
import L from '../../mapping/maplibre';
import type * as MapTypes from '../../mapping/maplibre';
import { useMap } from '../../mapping/react';
import { attachBasemapSwitcher } from '../../config/basemaps';

interface BasemapSwitcherControlProps {
  position?: MapTypes.ControlPosition;
}

export function BasemapSwitcherControl({
  position = 'topright',
}: BasemapSwitcherControlProps) {
  const map = useMap();

  useEffect(() => {
    return attachBasemapSwitcher(map, L, position);
  }, [map, position]);

  return null;
}
