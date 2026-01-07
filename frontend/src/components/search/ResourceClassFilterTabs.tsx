import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { fetchSearchResults } from '../../services/api';
import { normalizeFacetId } from '../../utils/facetLabels';

interface ResourceClassItem {
  value: string;
  label: string;
  hits: number;
}

const CACHE_KEY = 'resource_classes_cache';
const CACHE_TIMESTAMP_KEY = 'resource_classes_cache_timestamp';
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

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

export function ResourceClassFilterTabs() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [resourceClasses, setResourceClasses] = useState<ResourceClassItem[]>(
    []
  );
  const [isLoading, setIsLoading] = useState(true);

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
          const items: ResourceClassItem[] =
            resourceClassFacet.attributes.items?.map((item) => ({
              value: item.attributes.value as string,
              label: item.attributes.label || (item.attributes.value as string),
              hits: item.attributes.hits,
            })) || [];

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

    // Ensure we have a query parameter (even if empty) to trigger search
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

  return (
    <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
      <button
        onClick={() => handleTabClick(null)}
        className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 ${
          !currentResourceClass
            ? 'text-blue-600 border-blue-600 mb-[-2px]'
            : 'text-gray-600 border-transparent hover:text-gray-900 hover:border-gray-300'
        }`}
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
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 ${
              isActive
                ? 'text-blue-600 border-blue-600 mb-[-2px]'
                : 'text-gray-600 border-transparent hover:text-gray-900 hover:border-gray-300'
            }`}
            aria-label={`Filter by ${resourceClass.label}`}
            aria-current={isActive ? 'page' : undefined}
          >
            {resourceClass.label}
          </button>
        );
      })}
    </div>
  );
}
