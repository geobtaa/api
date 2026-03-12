import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { fetchSearchResults } from '../../services/api';
import { normalizeFacetId } from '../../utils/facetLabels';

interface ResourceClassItem {
  value: string;
  label: string;
  hits: number;
}

const CACHE_KEY = 'resource_classes_cache_v2'; // Bump to invalidate when exclusions change
const CACHE_TIMESTAMP_KEY = 'resource_classes_cache_timestamp';
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

/** Resource class values to hide from the header tabs (still searchable via filters). */
const EXCLUDED_RESOURCE_CLASSES = ['Collections', 'Series', 'Other'];

type FacetItemTuple = [value: string | number, hits: number];
type FacetItemObject = {
  attributes: {
    value: string | number;
    hits: number;
    label?: string;
  };
};

function isFacetItemTuple(item: unknown): item is FacetItemTuple {
  return (
    Array.isArray(item) &&
    item.length >= 2 &&
    (typeof item[0] === 'string' || typeof item[0] === 'number') &&
    typeof item[1] === 'number'
  );
}

function isFacetItemObject(item: unknown): item is FacetItemObject {
  if (!item || typeof item !== 'object') return false;
  const obj = item as { attributes?: unknown };
  if (!obj.attributes || typeof obj.attributes !== 'object') return false;
  const attrs = obj.attributes as { value?: unknown; hits?: unknown };
  return (
    (typeof attrs.value === 'string' || typeof attrs.value === 'number') &&
    typeof attrs.hits === 'number'
  );
}

function getCachedResourceClasses(): ResourceClassItem[] | null {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    const timestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY);

    if (cached && timestamp) {
      const age = Date.now() - parseInt(timestamp, 10);
      if (age < CACHE_DURATION) {
        return JSON.parse(cached);
      }
    }
  } catch (error) {
    console.error('Error reading cached resource classes:', error);
  }
  return null;
}

function setCachedResourceClasses(items: ResourceClassItem[]): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(items));
    localStorage.setItem(CACHE_TIMESTAMP_KEY, Date.now().toString());
  } catch (error) {
    console.error('Error caching resource classes:', error);
  }
}

function sortResourceClasses(items: ResourceClassItem[]): ResourceClassItem[] {
  // Separate "Other" from the rest
  const otherItem = items.find(
    (item) =>
      item.value.toLowerCase() === 'other' ||
      item.label.toLowerCase() === 'other'
  );
  const otherItems = otherItem ? [otherItem] : [];
  const regularItems = items.filter(
    (item) =>
      item.value.toLowerCase() !== 'other' &&
      item.label.toLowerCase() !== 'other'
  );

  // Sort regular items by hits (descending)
  regularItems.sort((a, b) => b.hits - a.hits);

  // Return regular items first, then "Other" at the end
  return [...regularItems, ...otherItems];
}

export function ResourceClassFilterTabs({
  variant = 'header',
  layout = 'horizontal',
}: {
  variant?: 'header' | 'content';
  layout?: 'horizontal' | 'vertical';
}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [resourceClasses, setResourceClasses] = useState<ResourceClassItem[]>(
    []
  );
  const [isLoading, setIsLoading] = useState(true);

  const styles =
    variant === 'content'
      ? {
          active: 'text-brand border-brand',
          inactive:
            'text-gray-600 border-transparent hover:text-gray-900 hover:border-gray-300',
        }
      : {
          active: 'text-white border-white',
          inactive: 'text-white border-transparent hover:border-white/70',
        };

  // Get current query and Resource Class filter from URL
  const currentQuery = searchParams.get('q') || '';
  const currentResourceClass =
    searchParams.getAll('include_filters[gbl_resourceClass_sm][]')[0] ||
    searchParams.getAll('fq[gbl_resourceClass_sm][]')[0] ||
    null;

  useEffect(() => {
    const fetchResourceClasses = async () => {
      // Check cache first
      const cached = getCachedResourceClasses();
      if (cached) {
        setResourceClasses(cached);
        setIsLoading(false);
        return;
      }

      try {
        // Fetch a minimal search to get Resource Class facets
        const results = await fetchSearchResults('', 1, 1);
        const resourceClassFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (normalizeFacetId(item.id) === 'gbl_resourceClass_sm' ||
              item.id === 'resource_class_agg')
        );

        if (
          resourceClassFacet?.attributes &&
          'items' in resourceClassFacet.attributes
        ) {
          const rawItems = (
            resourceClassFacet.attributes as { items?: unknown }
          ).items;

          const items: ResourceClassItem[] = Array.isArray(rawItems)
            ? rawItems
                .map((item: unknown): ResourceClassItem | null => {
                  // Backend may return compact tuples: [value, hits]
                  if (isFacetItemTuple(item)) {
                    const [value, hits] = item;
                    const v = String(value);
                    return { value: v, label: v, hits };
                  }

                  // Or verbose objects: { attributes: { value, hits, label? } }
                  if (isFacetItemObject(item)) {
                    const v = String(item.attributes.value);
                    const label = String(
                      item.attributes.label ?? item.attributes.value
                    );
                    return { value: v, label, hits: item.attributes.hits };
                  }

                  return null;
                })
                .filter(
                  (x): x is ResourceClassItem =>
                    x !== null && x.value.length > 0
                )
                .filter(
                  (x) =>
                    !EXCLUDED_RESOURCE_CLASSES.some(
                      (excl) =>
                        x.value.toLowerCase() === excl.toLowerCase() ||
                        x.label.toLowerCase() === excl.toLowerCase()
                    )
                )
            : [];

          // Sort by hits (descending), with "Other" placed last
          const sortedItems = sortResourceClasses(items);
          setResourceClasses(sortedItems);
          setCachedResourceClasses(sortedItems);
        }
      } catch (error) {
        console.error('Error fetching resource classes:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchResourceClasses();
  }, []);

  const handleTabClick = (resourceClassValue: string | null) => {
    const newParams = new URLSearchParams(searchParams);

    // Remove all Resource Class filters (both new and legacy format)
    const keysToRemove: string[] = [];
    newParams.forEach((_, key) => {
      if (
        key.startsWith('include_filters[gbl_resourceClass_sm]') ||
        key.startsWith('fq[gbl_resourceClass_sm]')
      ) {
        keysToRemove.push(key);
      }
    });
    keysToRemove.forEach((key) => newParams.delete(key));

    // If a specific Resource Class is selected, add it
    if (resourceClassValue) {
      newParams.append(
        'include_filters[gbl_resourceClass_sm][]',
        resourceClassValue
      );
    }

    // Ensure we have a query parameter (even if empty) so the loader fetches.
    // On homepage, currentQuery is ''; on search page, preserve existing query.
    if (!newParams.has('q')) {
      newParams.set('q', currentQuery || '');
    }

    // Reset to page 1 when changing filters
    newParams.delete('page');

    navigate(`/search?${newParams.toString()}`);
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 text-sm text-gray-500">
        Loading categories...
      </div>
    );
  }

  if (resourceClasses.length === 0) {
    return null;
  }

  const tabClass = (active: boolean) =>
    `px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
      layout === 'vertical'
        ? `w-full text-left rounded-md ${
            active ? 'bg-white/20' : 'hover:bg-white/10'
          } ${active ? styles.active : styles.inactive}`
        : `border-b-2 ${active ? styles.active : styles.inactive}`
    }`;

  const tabButtons = (
    <>
      <button
        onClick={() => handleTabClick(null)}
        className={tabClass(!currentResourceClass)}
        aria-label="Show all resources"
        aria-current={!currentResourceClass ? 'page' : undefined}
      >
        All
      </button>
      {resourceClasses.map((resourceClass) => {
        const isActive = currentResourceClass === resourceClass.value;
        return (
          <button
            key={resourceClass.value}
            onClick={() => handleTabClick(resourceClass.value)}
            className={tabClass(isActive)}
            aria-label={`Filter by ${resourceClass.label}`}
            aria-current={isActive ? 'page' : undefined}
          >
            {resourceClass.label}
          </button>
        );
      })}
    </>
  );

  if (layout === 'vertical') {
    return (
      <div className="flex flex-col gap-1">
        <p className="text-white/80 text-xs font-medium uppercase tracking-wider px-4 py-2">
          Browse by type
        </p>
        {tabButtons}
      </div>
    );
  }

  return (
    <div className="flex w-full min-w-0 items-center justify-center gap-1 overflow-x-auto scrollbar-hide">
      {tabButtons}
    </div>
  );
}
