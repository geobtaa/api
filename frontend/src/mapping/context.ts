import { createContext } from 'react';
import type { Map } from './maplibre';
export const MapContext = createContext<{ map: Map } | null>(null);
