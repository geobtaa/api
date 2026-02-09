import { LightboxModal } from '../ui/LightboxModal';
import { H3HexDataTable } from './H3HexDataTable';

const HEX_TABLE_MODAL_ID = 'hex-table-modal';
const HEX_TABLE_MODAL_TITLE_ID = 'hex-table-modal-title';

export interface HexTableModalProps {
  isOpen: boolean;
  onClose: () => void;
  hexes: Array<{ h3: string; count: number }>;
  resolution: number;
  searchQuery?: string;
  queryString?: string;
  loading?: boolean;
}

/**
 * Full lightbox modal for the H3 hex data table.
 * Same pattern as the facet "More" modal for consistency.
 */
export function HexTableModal({
  isOpen,
  onClose,
  hexes,
  resolution,
  searchQuery,
  queryString,
  loading = false,
}: HexTableModalProps) {
  return (
    <LightboxModal
      isOpen={isOpen}
      onClose={onClose}
      id={HEX_TABLE_MODAL_ID}
      labelledBy={HEX_TABLE_MODAL_TITLE_ID}
      title="Hex data table"
      subtitle="Resource count by H3 hex in current map view. Use Search this hex to filter results."
      data-testid="hex-table-modal-overlay"
    >
      <div className="flex-1 overflow-y-auto p-6">
        <H3HexDataTable
          hexes={hexes}
          resolution={resolution}
          searchQuery={searchQuery}
          queryString={queryString}
          loading={loading}
        />
      </div>
    </LightboxModal>
  );
}
