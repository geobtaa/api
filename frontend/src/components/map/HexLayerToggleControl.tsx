import { useContext, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import L from 'leaflet';
import { Hexagon, Table } from 'lucide-react';
import { LeafletContext } from '@react-leaflet/core';
import { HexTableModal } from './HexTableModal';

const MAP_CONTROL_ICON_PROPS = {
  size: 17,
  strokeWidth: 1.85,
  absoluteStrokeWidth: true as const,
};

interface HexLayerToggleControlProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  hexes: Array<{ h3: string; count: number }>;
  resolution: number;
  searchQuery?: string;
  queryString?: string;
  loading?: boolean;
  mapInstance?: L.Map | null;
  stackOrder?: 'default' | 'beforeBasemap';
}

export function HexLayerToggleControl({
  enabled,
  onToggle,
  hexes,
  resolution,
  searchQuery,
  queryString,
  loading,
  mapInstance,
  stackOrder = 'default',
}: HexLayerToggleControlProps) {
  const context = useContext(LeafletContext);
  const map = context?.map ?? mapInstance ?? null;
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [isTableOpen, setIsTableOpen] = useState(false);

  useEffect(() => {
    if (!map) return;

    const CustomControl = L.Control.extend({
      onAdd: () => {
        const div = document.createElement('div');
        div.className = 'leaflet-control leaflet-bar';
        L.DomEvent.disableClickPropagation(div);
        return div;
      },
    });

    const control = new CustomControl({
      position: 'topleft' as L.ControlPosition,
    });
    control.addTo(map);
    const controlContainer = control.getContainer();
    if (stackOrder === 'beforeBasemap') {
      const cornerContainer = controlContainer?.parentElement;
      if (cornerContainer && controlContainer) {
        const basemapControl = cornerContainer.querySelector(
          '.leaflet-control-layers'
        );
        if (basemapControl) {
          cornerContainer.insertBefore(controlContainer, basemapControl);
        }
      }
    }
    setContainer(controlContainer);

    return () => {
      control.remove();
      setContainer(null);
    };
  }, [map, stackOrder]);

  if (!container) return null;

  return createPortal(
    <>
      <HexTableModal
        isOpen={isTableOpen}
        onClose={() => setIsTableOpen(false)}
        hexes={hexes}
        resolution={resolution}
        searchQuery={searchQuery}
        queryString={queryString}
        loading={loading}
      />
      <div>
        <button
          type="button"
          onClick={() => {
            const next = !enabled;
            onToggle(next);
            if (!next) {
              setIsTableOpen(false);
            }
          }}
          aria-label={enabled ? 'Hide hex map layer' : 'Show hex map layer'}
          title={enabled ? 'Hide hex map layer' : 'Show hex map layer'}
          className={`leaflet-control-custom-button focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors ${
            enabled ? 'bg-blue-50 hover:bg-blue-100' : ''
          }`}
        >
          <Hexagon
            {...MAP_CONTROL_ICON_PROPS}
            className={enabled ? 'text-blue-600 fill-current' : 'text-gray-500'}
            fill={enabled ? 'currentColor' : 'none'}
          />
        </button>
        <button
          type="button"
          onClick={() => setIsTableOpen((open) => !open)}
          disabled={!enabled}
          aria-haspopup="dialog"
          aria-expanded={isTableOpen}
          aria-label={
            isTableOpen ? 'Close hex data table' : 'View hex data as table'
          }
          title={isTableOpen ? 'Close hex data table' : 'View hex table'}
          className="leaflet-control-custom-button focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors disabled:cursor-not-allowed disabled:text-gray-300"
        >
          <Table {...MAP_CONTROL_ICON_PROPS} className="text-gray-700" />
        </button>
      </div>
    </>,
    container
  );
}
