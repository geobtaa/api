import { useState, useRef } from 'react';
import { Table, Hexagon } from 'lucide-react';
import { HexTableModal } from './HexTableModal';

const HEX_TABLE_MODAL_ID = 'hex-table-modal';

export interface HexTableControlProps {
  hexes: Array<{ h3: string; count: number }>;
  resolution: number;
  searchQuery?: string;
  queryString?: string;
  loading?: boolean;
}

/**
 * Leaflet-style control: button with table+hex icon in bottom-left corner.
 * Opens the H3 hex data table in a full lightbox modal (same as facet "More").
 */
export function HexTableControl({
  hexes,
  resolution,
  searchQuery,
  queryString,
  loading = false,
}: HexTableControlProps) {
  const [isOpen, setIsOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  return (
    <>
      <HexTableModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        hexes={hexes}
        resolution={resolution}
        searchQuery={searchQuery}
        queryString={queryString}
        loading={loading}
      />
      <div className="absolute bottom-4 left-4 z-[1000]">
        <button
          ref={toggleRef}
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          aria-haspopup="dialog"
          aria-expanded={isOpen}
          aria-controls={isOpen ? HEX_TABLE_MODAL_ID : undefined}
          aria-label={isOpen ? 'Close hex data table' : 'View hex data as table'}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-gray-200 bg-white/95 shadow-sm backdrop-blur-sm hover:bg-gray-50 hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11"
        >
          <span className="relative inline-flex" aria-hidden>
            <Table className="h-5 w-5 text-gray-700" strokeWidth={2} />
            <Hexagon
              className="absolute -bottom-1 -right-1 h-2.5 w-2.5 text-blue-600"
              fill="currentColor"
              strokeWidth={0}
            />
          </span>
        </button>
      </div>
    </>
  );
}
