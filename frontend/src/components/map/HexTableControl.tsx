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
  /** Optional class for the wrapper div (e.g. to customize position). Default: bottom-4 left-4 */
  wrapperClassName?: string;
  /** When true, use 30x30px button to match Leaflet zoom control size */
  compact?: boolean;
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
  wrapperClassName = 'bottom-4 left-4',
  compact = false,
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
      <div className={`absolute ${wrapperClassName} z-[1000]`}>
        <button
          ref={toggleRef}
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          aria-haspopup="dialog"
          aria-expanded={isOpen}
          aria-controls={isOpen ? HEX_TABLE_MODAL_ID : undefined}
          aria-label={isOpen ? 'Close hex data table' : 'View hex data as table'}
          title={isOpen ? 'Close hex data table' : 'View hex table'}
          className={`flex items-center justify-center rounded-lg border border-gray-200 bg-white/95 shadow-sm backdrop-blur-sm hover:bg-gray-50 hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors ${
            compact
              ? 'h-[30px] w-[30px]'
              : 'h-10 w-10 [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11'
          }`}
        >
          <span className="relative inline-flex" aria-hidden>
            <Table
              className={`text-gray-700 ${compact ? 'h-4 w-4' : 'h-5 w-5'}`}
              strokeWidth={2}
            />
            <Hexagon
              className={`absolute -right-0.5 text-blue-600 fill-current ${
                compact ? '-bottom-0.5 h-1.5 w-1.5' : '-bottom-1 -right-1 h-2.5 w-2.5'
              }`}
              fill="currentColor"
              strokeWidth={0}
            />
          </span>
        </button>
      </div>
    </>
  );
}
