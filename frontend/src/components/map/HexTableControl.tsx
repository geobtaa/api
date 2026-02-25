import { useContext, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import L from 'leaflet';
import { Table, Hexagon } from 'lucide-react';
import { LeafletContext } from '@react-leaflet/core';
import { HexTableModal } from './HexTableModal';

const HEX_TABLE_MODAL_ID = 'hex-table-modal';

export interface HexTableControlProps {
  hexes: Array<{ h3: string; count: number }>;
  resolution: number;
  searchQuery?: string;
  queryString?: string;
  loading?: boolean;
  /** Optional class for the wrapper div (overlay mode only). Default: top-[86px] left-2 */
  wrapperClassName?: string;
  /** When true, match Leaflet zoom control size, border, and border-radius exactly */
  compact?: boolean;
}

/**
 * Button + modal content; shared by both overlay and Leaflet Control modes.
 */
function HexTableButton({
  compact,
  onOpenChange,
  isOpen,
}: HexTableControlProps & {
  onOpenChange: (open: boolean) => void;
  isOpen: boolean;
}) {
  return (
    <>
      <button
        type="button"
        onClick={() => onOpenChange(!isOpen)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-controls={isOpen ? HEX_TABLE_MODAL_ID : undefined}
        aria-label={isOpen ? 'Close hex data table' : 'View hex data as table'}
        title={isOpen ? 'Close hex data table' : 'View hex table'}
        className={`flex items-center justify-center bg-white hover:bg-[#f4f4f4] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors ${
          compact
            ? 'leaflet-control-custom-button'
            : 'h-10 w-10 rounded-lg border border-gray-200 shadow-sm backdrop-blur-sm hover:bg-gray-50 hover:border-gray-300 [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11'
        }`}
      >
        <span className="relative inline-flex" aria-hidden>
          <Table
            className={`text-gray-700 ${compact ? 'h-4 w-4' : 'h-5 w-5'}`}
            strokeWidth={2}
          />
          <Hexagon
            className={`absolute -right-0.5 text-blue-600 fill-current ${
              compact
                ? '-bottom-0.5 h-1.5 w-1.5'
                : '-bottom-1 -right-1 h-2.5 w-2.5'
            }`}
            fill="currentColor"
            strokeWidth={0}
          />
        </span>
      </button>
    </>
  );
}

/**
 * Renders the hex table button inside Leaflet's control container (div.leaflet-top.leaflet-left).
 * Uses map.addControl() so it appears alongside the zoom control in the proper layout.
 */
function HexTableControlInLeaflet(props: HexTableControlProps) {
  const context = useContext(LeafletContext);
  const map = context?.map;
  const [isOpen, setIsOpen] = useState(false);
  const [container, setContainer] = useState<HTMLDivElement | null>(null);

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
    setContainer(control.getContainer());

    return () => {
      control.remove();
      setContainer(null);
    };
  }, [map]);

  if (!container) return null;

  return createPortal(
    <>
      <HexTableModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        hexes={props.hexes}
        resolution={props.resolution}
        searchQuery={props.searchQuery}
        queryString={props.queryString}
        loading={props.loading}
      />
      <HexTableButton {...props} isOpen={isOpen} onOpenChange={setIsOpen} />
    </>,
    container
  );
}

/**
 * Overlay mode: positioned with absolute + wrapperClassName, used when not inside MapContainer.
 */
function HexTableControlOverlay(props: HexTableControlProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { wrapperClassName = 'top-[86px] left-2' } = props;

  return (
    <>
      <HexTableModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        hexes={props.hexes}
        resolution={props.resolution}
        searchQuery={props.searchQuery}
        queryString={props.queryString}
        loading={props.loading}
      />
      <div className={`absolute ${wrapperClassName} z-[1000]`}>
        <HexTableButton {...props} isOpen={isOpen} onOpenChange={setIsOpen} />
      </div>
    </>
  );
}

/**
 * Leaflet-style control: button with table+hex icon in top-left corner.
 * Opens the H3 hex data table in a full lightbox modal (same as facet "More").
 *
 * When used as a child of MapContainer, renders inside Leaflet's control layout
 * (div.leaflet-control-container > div.leaflet-top.leaflet-left).
 * When used outside MapContainer (e.g. GeospatialFilterMap), uses absolute positioning.
 */
export function HexTableControl(props: HexTableControlProps) {
  const context = useContext(LeafletContext);

  if (context?.map) {
    return <HexTableControlInLeaflet {...props} />;
  }

  return <HexTableControlOverlay {...props} />;
}
