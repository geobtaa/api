import { ChevronDown } from 'lucide-react';
import { useSearchParams } from 'react-router';
import { GeospatialFilterMap } from './GeospatialFilterMap';
import { DEFAULT_OPEN_FACET_IDS } from '../FacetList';
import type { FacetAccordionState } from '../../hooks/useFacetAccordion';

const GEO_FACET_ID = 'geo';

function hasGeoBbox(searchParams: URLSearchParams): boolean {
  const type = searchParams.get('include_filters[geo][type]');
  if (type !== 'bbox') return false;
  const topLeftLat = searchParams.get('include_filters[geo][top_left][lat]');
  const topLeftLon = searchParams.get('include_filters[geo][top_left][lon]');
  const bottomRightLat = searchParams.get(
    'include_filters[geo][bottom_right][lat]'
  );
  const bottomRightLon = searchParams.get(
    'include_filters[geo][bottom_right][lon]'
  );
  return !!(
    topLeftLat &&
    topLeftLon &&
    bottomRightLat &&
    bottomRightLon
  );
}

interface LocationFacetCollapsibleProps {
  accordion: FacetAccordionState;
  setAccordion: React.Dispatch<
    React.SetStateAction<FacetAccordionState>
  >;
}

export function LocationFacetCollapsible({
  accordion,
  setAccordion,
}: LocationFacetCollapsibleProps) {
  const [searchParams] = useSearchParams();
  const isForcedOpen = hasGeoBbox(searchParams);
  const isOpen =
    isForcedOpen ||
    accordion.opened.has(GEO_FACET_ID) ||
    (DEFAULT_OPEN_FACET_IDS.has(GEO_FACET_ID) &&
      !accordion.closed.has(GEO_FACET_ID));

  return (
    <details
      open={isOpen}
      onToggle={(e) => {
        const nextOpen = (e.currentTarget as HTMLDetailsElement).open;
        setAccordion((prev) => {
          if (!nextOpen && isForcedOpen) return prev;

          const opened = new Set(prev.opened);
          const closed = new Set(prev.closed);

          if (nextOpen) {
            opened.add(GEO_FACET_ID);
            closed.delete(GEO_FACET_ID);
          } else {
            opened.delete(GEO_FACET_ID);
            if (DEFAULT_OPEN_FACET_IDS.has(GEO_FACET_ID)) {
              closed.add(GEO_FACET_ID);
            } else {
              closed.delete(GEO_FACET_ID);
            }
          }

          return { opened, closed };
        });
      }}
      className="group border-b pb-4 mb-6 !mt-0"
    >
      <summary
        id="filter-location-heading"
        className="flex items-center justify-between cursor-pointer select-none py-2"
      >
        <h3 className="font-semibold text-gray-900">Location</h3>
        <ChevronDown className="h-4 w-4 text-gray-500 transition-transform group-open:rotate-180 shrink-0" />
      </summary>
      <div className="pt-2">
        <GeospatialFilterMap hideHeading />
      </div>
    </details>
  );
}
