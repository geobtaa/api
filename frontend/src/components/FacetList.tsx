import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { ChevronDown, MinusCircle } from 'lucide-react';
import { FACET_LABELS, normalizeFacetId } from '../utils/facetLabels';
import { normalizeFacetValueForUrl } from '../utils/searchParams';
import { CONFIGURED_FACETS } from '../constants/facets';
import { FacetMoreModal } from './search/FacetMoreModal';
import { formatCount } from '../utils/formatNumber';
import { getFacetValueDisplayLabel } from '../utils/facetDisplay';
import { TimelineFacet } from './search/TimelineFacet';
import type { SelectedYearRange } from './search/TimelineFacet';
import type { FacetAccordionState } from '../hooks/useFacetAccordion';

// New JSON:API facet structure
type JsonApiFacetItemTuple = [value: string | number, hits: number];

export interface JsonApiFacet {
  type: 'facet' | 'timeline';
  id: string;
  links?: {
    applyTemplate?: string;
  };
  attributes: {
    label: string;
    items:
      | Array<{
          attributes: {
            label?: string;
            value: string | number;
            hits: number;
          };
          links?: {
            self: string;
          };
        }>
      | JsonApiFacetItemTuple[];
  };
}

interface FacetListProps {
  facets: JsonApiFacet[];
  /** Optional shared accordion state (persisted via useFacetAccordion). When provided, collapse/expand state is shared across facets and persisted. */
  accordion?: FacetAccordionState;
  setAccordion?: React.Dispatch<React.SetStateAction<FacetAccordionState>>;
}

/** Facet IDs that are open by default. Includes geo (Location map) for use by SearchPage. */
export const DEFAULT_OPEN_FACET_IDS = new Set<string>([
  'geo', // Location (map filter)
  'dct_spatial_sm', // Place
  'gbl_resourceClass_sm', // Resource Class
  'gbl_resourceType_sm', // Resource Type
  'year_histogram', // Timeline likely always open
]);

function isCompactTupleItems(
  items: JsonApiFacet['attributes']['items']
): items is JsonApiFacetItemTuple[] {
  return (
    Array.isArray(items) &&
    items.length > 0 &&
    Array.isArray((items as unknown[])[0])
  );
}

export function FacetList({
  facets,
  accordion: controlledAccordion,
  setAccordion: controlledSetAccordion,
}: FacetListProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeFacetModal, setActiveFacetModal] = useState<{
    id: string;
    label: string;
  } | null>(null);

  const applyYearRange = (range: SelectedYearRange | null) => {
    const newParams = new URLSearchParams(searchParams);

    newParams.delete('include_filters[year_range][start]');
    newParams.delete('include_filters[year_range][end]');

    if (range) {
      if (range.start != null) {
        newParams.set(
          'include_filters[year_range][start]',
          range.start.toString()
        );
      }
      if (range.end != null) {
        newParams.set('include_filters[year_range][end]', range.end.toString());
      }
    }

    newParams.delete('page');
    setSearchParams(newParams);
  };

  // Get current range selection
  const yearRangeStart = searchParams.get('include_filters[year_range][start]');
  const yearRangeEnd = searchParams.get('include_filters[year_range][end]');

  // Helper function to check if a facet is active
  const isFacetActive = (field: string, value: string | number) => {
    const normalized = normalizeFacetId(field);
    const valueStr = value.toString();
    const primary = searchParams.getAll(`include_filters[${normalized}][]`);
    if (primary.includes(valueStr)) return true;
    // Boolean facets: URL may store "true"/"false" while API uses "1"/"0"
    if (primary.includes(normalizeFacetValueForUrl(normalized, valueStr)))
      return true;
    // Also check legacy param key(s) for backward compatibility.
    const legacyRaw = searchParams.getAll(`fq[${field}][]`);
    if (legacyRaw.includes(valueStr)) return true;
    if (normalized !== field) {
      const legacyNorm = searchParams.getAll(`fq[${normalized}][]`);
      if (legacyNorm.includes(valueStr)) return true;
    }
    return false;
  };

  // Helper function to toggle a facet
  const handleFacetClick = (field: string, value: string | number) => {
    const newParams = new URLSearchParams(searchParams);
    const normalized = normalizeFacetId(field);
    const facetKey = `include_filters[${normalized}][]`;
    const legacyKeyRaw = `fq[${field}][]`;
    const legacyKeyNorm = normalized !== field ? `fq[${normalized}][]` : null;

    if (isFacetActive(field, value)) {
      // Remove the facet if it's active (clean both legacy and new keys)
      const currentValuesNew = newParams.getAll(facetKey);
      const currentValuesOldRaw = newParams.getAll(legacyKeyRaw);
      const currentValuesOldNorm = legacyKeyNorm
        ? newParams.getAll(legacyKeyNorm)
        : [];

      // Delete both keys
      newParams.delete(facetKey);
      newParams.delete(legacyKeyRaw);
      if (legacyKeyNorm) newParams.delete(legacyKeyNorm);

      // Merge remaining values under normalized key
      [...currentValuesNew, ...currentValuesOldRaw, ...currentValuesOldNorm]
        .filter((v) => v !== value.toString())
        .forEach((v) =>
          newParams.append(facetKey, normalizeFacetValueForUrl(normalized, v))
        );
    } else {
      // Add the facet if it's not active
      newParams.append(
        facetKey,
        normalizeFacetValueForUrl(normalized, value.toString())
      );
    }

    newParams.delete('page');
    setSearchParams(newParams);
  };

  const isFacetExcluded = (field: string, value: string | number) => {
    const normalized = normalizeFacetId(field);
    return searchParams
      .getAll(`exclude_filters[${normalized}][]`)
      .includes(value.toString());
  };

  const handleFacetExclude = (field: string, value: string | number) => {
    const newParams = new URLSearchParams(searchParams);
    const normalized = normalizeFacetId(field);
    const excludeKey = `exclude_filters[${normalized}][]`;
    // Toggle exclude (if already excluded, remove it)
    const existing = newParams.getAll(excludeKey);
    if (existing.includes(value.toString())) {
      newParams.delete(excludeKey);
      existing
        .filter((v) => v !== value.toString())
        .forEach((v) =>
          newParams.append(excludeKey, normalizeFacetValueForUrl(normalized, v))
        );
    } else {
      newParams.append(
        excludeKey,
        normalizeFacetValueForUrl(normalized, value.toString())
      );
    }
    newParams.delete('page');
    setSearchParams(newParams);
  };

  const safeFacets = facets || [];

  // Filter facets to only show those with items and convert to the expected format
  const availableFacets = safeFacets
    .filter(
      (facet) => facet.attributes.items && facet.attributes.items.length > 0
    )
    .map((facet) => {
      // Logic to normalize item structure
      let items: any[] = [];
      if (isCompactTupleItems(facet.attributes.items)) {
        items = facet.attributes.items.map(([value, hits]) => ({
          label: getFacetValueDisplayLabel(
            { attributes: { value, hits } } as any,
            facet.id
          ),
          value,
          hits,
          url: undefined as string | undefined,
        }));
      } else {
        items = facet.attributes.items.map((item) => ({
          label: getFacetValueDisplayLabel(
            {
              id: String(item.attributes.value),
              attributes: item.attributes,
            },
            facet.id
          ),
          value: item.attributes.value,
          hits: item.attributes.hits,
          url: item.links?.self,
        }));
      }

      return {
        type: facet.type,
        id: normalizeFacetId(facet.id),
        rawId: facet.id,
        label: facet.attributes.label,
        items,
      };
    });

  // Order facets according to CONFIGURED_FACETS and filter to only show configured ones
  const orderedFacets = CONFIGURED_FACETS.map((facetId) => {
    const facet = availableFacets.find((f) => f.id === facetId);
    return facet;
  }).filter((facet): facet is NonNullable<typeof facet> => facet !== undefined);

  // Derive "forced open" facet groups from the current URL params.
  // This is computed without effects to avoid render loops.
  const forcedOpenFacetIds = useMemo(() => {
    const key = searchParams.toString();
    // If there are no params, fast-path empty.
    if (!key) return new Set<string>();

    const hasAny = (k: string) => searchParams.getAll(k).length > 0;
    const forced = new Set<string>();
    for (const facet of orderedFacets) {
      const norm = normalizeFacetId(facet.id);
      const raw = normalizeFacetId(facet.rawId);

      if (hasAny(`include_filters[${norm}][]`)) forced.add(facet.id);
      else if (hasAny(`exclude_filters[${norm}][]`)) forced.add(facet.id);
      else if (hasAny(`fq[${norm}][]`)) forced.add(facet.id);
      else if (raw !== norm && hasAny(`fq[${raw}][]`)) forced.add(facet.id);

      // Also force open if year range is active and it's timeline
      if (
        facet.type === 'timeline' &&
        (hasAny('include_filters[year_range][start]') ||
          hasAny('include_filters[year_range][end]'))
      ) {
        forced.add(facet.id);
      }
    }
    return forced;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderedFacets, searchParams.toString()]);

  // Track user toggles separately from default/forced-open behavior.
  // Use controlled accordion when provided (persisted); otherwise internal state.
  const [internalAccordion, setInternalAccordion] =
    useState<FacetAccordionState>(() => ({
      opened: new Set(),
      closed: new Set(),
    }));
  const accordion = controlledAccordion ?? internalAccordion;
  const setAccordion = controlledSetAccordion ?? setInternalAccordion;

  if (!safeFacets || safeFacets.length === 0) {
    return <div className="text-gray-500">No facets available</div>;
  }

  if (orderedFacets.length === 0) {
    return (
      <div className="text-gray-500">No facets available for this search</div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {orderedFacets.map((facet) => {
          // Special rendering for timeline facet
          if (facet.type === 'timeline') {
            const isOpen =
              forcedOpenFacetIds.has(facet.id) ||
              accordion.opened.has(facet.id) ||
              (DEFAULT_OPEN_FACET_IDS.has(facet.id) &&
                !accordion.closed.has(facet.id));

            return (
              <details
                key={facet.id}
                open={isOpen}
                onToggle={(e) => {
                  const nextOpen = (e.currentTarget as HTMLDetailsElement).open;
                  setAccordion((prev) => {
                    const opened = new Set(prev.opened);
                    const closed = new Set(prev.closed);
                    if (nextOpen) {
                      opened.add(facet.id);
                      closed.delete(facet.id);
                    } else {
                      opened.delete(facet.id);
                      closed.add(facet.id);
                    }
                    return { opened, closed };
                  });
                }}
                className="group border-b pb-4"
              >
                <summary className="flex items-center justify-between cursor-pointer select-none py-2">
                  <h3 className="font-semibold text-gray-900">Year</h3>
                  <ChevronDown className="h-4 w-4 text-gray-500 transition-transform group-open:rotate-180" />
                </summary>
                <div>
                  <TimelineFacet
                    facet={{
                      type: 'timeline',
                      id: facet.id,
                      attributes: {
                        label: facet.label,
                        items: facet.items.map((i) => ({
                          attributes: {
                            value: i.value,
                            hits: i.hits,
                          },
                        })) as any,
                      },
                    }}
                    onChange={applyYearRange}
                    selectedRange={
                      yearRangeStart || yearRangeEnd
                        ? {
                            start: yearRangeStart
                              ? parseInt(yearRangeStart, 10)
                              : null,
                            end: yearRangeEnd
                              ? parseInt(yearRangeEnd, 10)
                              : null,
                          }
                        : null
                    }
                  />
                </div>
              </details>
            );
          }

          const facetLabel = FACET_LABELS[facet.id] || facet.label;
          const limit = facet.id === 'dct_spatial_sm' ? 5 : 10;
          const displayItems = facet.items.slice(0, limit);
          const hasMore = facet.items.length > limit;
          const isForcedOpen = forcedOpenFacetIds.has(facet.id);
          const isOpen = isForcedOpen
            ? true
            : accordion.opened.has(facet.id)
              ? true
              : accordion.closed.has(facet.id)
                ? false
                : DEFAULT_OPEN_FACET_IDS.has(facet.id);

          return (
            <details
              key={facet.id}
              open={isOpen}
              onToggle={(e) => {
                const nextOpen = (e.currentTarget as HTMLDetailsElement).open;
                setAccordion((prev) => {
                  if (!nextOpen && isForcedOpen) return prev;

                  const opened = new Set(prev.opened);
                  const closed = new Set(prev.closed);

                  if (nextOpen) {
                    opened.add(facet.id);
                    closed.delete(facet.id);
                  } else {
                    opened.delete(facet.id);
                    // Only track "closed" overrides for default-open facets.
                    if (DEFAULT_OPEN_FACET_IDS.has(facet.id))
                      closed.add(facet.id);
                    else closed.delete(facet.id);
                  }

                  return { opened, closed };
                });
              }}
              className="group border-b pb-4"
            >
              <summary className="flex items-center justify-between cursor-pointer select-none py-2">
                <h3 className="font-semibold text-gray-900">{facetLabel}</h3>
                <ChevronDown className="h-4 w-4 text-gray-500 transition-transform group-open:rotate-180" />
              </summary>

              <div className="pt-1">
                <ul className="space-y-1">
                  {displayItems.map((item) => {
                    const isActive = isFacetActive(facet.rawId, item.value);
                    const excluded = isFacetExcluded(facet.rawId, item.value);

                    return (
                      <li
                        key={`${facet.id}-${item.value}`}
                        className="group flex items-center gap-2"
                      >
                        <button
                          onClick={() =>
                            handleFacetClick(facet.rawId, item.value)
                          }
                          className={`text-sm flex items-center gap-2 w-full text-left py-1 pr-2 rounded hover:bg-gray-100 ${
                            isActive
                              ? 'text-blue-600 font-medium bg-blue-50 hover:bg-blue-100'
                              : 'text-gray-600 hover:text-gray-900'
                          }`}
                        >
                          <span>{item.label}</span>
                          <span
                            className={`${
                              isActive ? 'text-blue-600' : 'text-gray-600'
                            }`}
                          >
                            ({formatCount(item.hits)})
                          </span>
                          {isActive && (
                            <span className="text-blue-600 ml-auto">×</span>
                          )}
                        </button>
                        <button
                          onClick={() =>
                            handleFacetExclude(facet.rawId, item.value)
                          }
                          className={`ml-1 p-1 rounded transition-colors ${
                            excluded
                              ? 'text-red-600 bg-red-50 hover:bg-red-100'
                              : 'text-gray-400 hover:text-red-600 hover:bg-gray-100'
                          } ${excluded ? '' : 'opacity-0 group-hover:opacity-100'}`}
                          aria-label={
                            excluded
                              ? `Remove exclusion: ${facetLabel}: ${item.label}`
                              : `Exclude ${facetLabel}: ${item.label}`
                          }
                          title={
                            excluded
                              ? `Remove exclusion: ${facetLabel}: ${item.label}`
                              : `Exclude ${facetLabel}: ${item.label}`
                          }
                        >
                          <MinusCircle className="w-4 h-4" />
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {hasMore && (
                  <button
                    onClick={() =>
                      setActiveFacetModal({
                        id: facet.rawId,
                        label: facetLabel,
                      })
                    }
                    className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    More &raquo;
                  </button>
                )}
              </div>
            </details>
          );
        })}
      </div>
      {activeFacetModal && (
        <FacetMoreModal
          facetId={activeFacetModal.id}
          facetLabel={activeFacetModal.label}
          isOpen
          onClose={() => setActiveFacetModal(null)}
          searchParams={searchParams}
          onToggleInclude={(value) =>
            handleFacetClick(activeFacetModal.id, value)
          }
          onToggleExclude={(value) =>
            handleFacetExclude(activeFacetModal.id, value)
          }
          onToggleFacetInclude={(field, value) =>
            handleFacetClick(field, value)
          }
          onToggleFacetExclude={(field, value) =>
            handleFacetExclude(field, value)
          }
          isValueIncluded={(value) => isFacetActive(activeFacetModal.id, value)}
          isValueExcluded={(value) =>
            isFacetExcluded(activeFacetModal.id, value)
          }
        />
      )}
    </>
  );
}
