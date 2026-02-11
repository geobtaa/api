import { useEffect, useState, Suspense, lazy } from 'react';
import { useNavigate } from 'react-router';
import { useTheme } from '../hooks/useTheme';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';

const HomePageHexMapBackground = lazy(() =>
  import('../components/home/HomePageHexMapBackground.client').then((m) => ({
    default: m.HomePageHexMapBackground,
  }))
);
import { MapPin, Search } from 'lucide-react';
import { fetchSearchResults } from '../services/api';
import { formatCount } from '../utils/formatNumber';
import { getResourceIcon } from '../utils/resourceIcons';

type FacetItem = { value: string; label: string; count: number };

export function HomePage() {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [resourceTypeList, setResourceTypeList] = useState<FacetItem[]>([]);
  const [placeList, setPlaceList] = useState<FacetItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  function parseFacetItems(rawItems: unknown): FacetItem[] {
    const items: FacetItem[] = [];
    if (!Array.isArray(rawItems)) return items;
    if (rawItems.length > 0 && Array.isArray(rawItems[0])) {
      (rawItems as Array<[string | number, number]>).forEach(
        ([value, hits]) => {
          const v = String(value);
          items.push({ value: v, label: v, count: Number(hits) || 0 });
        }
      );
    } else {
      (rawItems as Array<any>).forEach((item) => {
        const value = item?.attributes?.value;
        const hits = item?.attributes?.hits;
        const label = item?.attributes?.label ?? value;
        if (value !== undefined) {
          items.push({
            value: String(value),
            label: String(label ?? value),
            count: Number(hits) || 0,
          });
        }
      });
    }
    return items;
  }

  function topItems(items: FacetItem[], limit: number): FacetItem[] {
    const otherItem = items.find(
      (item) =>
        item.value.toLowerCase() === 'other' ||
        item.label.toLowerCase() === 'other'
    );
    const regularItems = items.filter(
      (item) =>
        item.value.toLowerCase() !== 'other' &&
        item.label.toLowerCase() !== 'other'
    );
    regularItems.sort((a, b) => b.count - a.count);
    const top = regularItems.slice(0, limit);
    return otherItem ? [...top, otherItem] : top;
  }

  useEffect(() => {
    const fetchFacets = async () => {
      try {
        const results = await fetchSearchResults('', 1, 1);
        const resourceTypeFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'gbl_resourceType_sm' ||
              item.id === 'resource_type_agg')
        );
        const placeFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'dct_spatial_sm' || item.id === 'spatial_agg')
        );

        const resourceTypeItems = parseFacetItems(
          (resourceTypeFacet as any)?.attributes?.items
        );
        const placeItems = parseFacetItems(
          (placeFacet as any)?.attributes?.items
        );

        setResourceTypeList(topItems(resourceTypeItems, 10));
        setPlaceList(topItems(placeItems, 10));
      } catch (error) {
        console.error('Error fetching facets:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchFacets();
  }, []);

  const handleResourceTypeClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[gbl_resourceType_sm][]=${encodeURIComponent(value)}`
    );
  };

  const handlePlaceClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[dct_spatial_sm][]=${encodeURIComponent(value)}`
    );
  };

  const handleBrowseAll = () => {
    navigate('/search?q=');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 bg-gray-50 flex flex-col">
        <h1 className="sr-only">{theme.institution.name}</h1>
        {/* Map (full viewport minus header) */}
        <div className="flex-shrink-0 relative h-[calc(100vh-4rem)] overflow-hidden">
          {mounted && (
            <Suspense fallback={null}>
              <HomePageHexMapBackground />
            </Suspense>
          )}
          {/* Description box - introduces the site; search is in header */}
          <div className="absolute inset-0 z-30 pointer-events-none flex items-start justify-center pt-4 px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl w-full bg-white/70 backdrop-blur-sm rounded-lg p-6 lg:p-4 shadow-sm">
              <p className="text-lg lg:text-xl text-gray-600">
                {theme.institution.hero_text ||
                  'Search geospatial resources from Big Ten Academic Alliance institutions'}
              </p>
              <p className="text-sm text-gray-500 mt-2">
                {theme.institution.hero_description ||
                  'Browse and download GIS data, maps, and other geospatial resources.'}
              </p>
            </div>
          </div>
        </div>

        {/* Browse by Resource Type and Place - full width panel below map. */}
        <div className="flex-shrink-0 w-full bg-white/80 backdrop-blur-sm border-t border-gray-200 px-4 sm:px-6 lg:px-8 py-6 z-10">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <button
              onClick={handleBrowseAll}
              className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-gray-200 hover:border-brand-active hover:shadow-sm transition-all group"
            >
              <Search className="w-5 h-5 text-gray-400 group-hover:text-brand-active" />
              <span className="text-gray-700 group-hover:text-gray-900">
                Browse All Resources
              </span>
            </button>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Column 1: Resource Type */}
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">
                Resource Type
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {resourceTypeList.map((resource) => (
                  <button
                    key={`type-${resource.value}`}
                    onClick={() => handleResourceTypeClick(resource.value)}
                    className="flex items-center gap-3 px-4 py-3 bg-white rounded-lg border border-gray-200 hover:border-brand-active hover:shadow-sm transition-all group"
                  >
                    <div className="text-gray-400 group-hover:text-brand-active">
                      {getResourceIcon(resource.value, {
                        className: 'w-6 h-6 text-gray-400',
                      })}
                    </div>
                    <span className="text-gray-700 group-hover:text-gray-900 truncate">
                      {resource.label}
                    </span>
                    <span className="text-sm text-gray-500 group-hover:text-gray-700 ml-auto shrink-0">
                      {!isLoading ? formatCount(resource.count) : ''}
                    </span>
                  </button>
                ))}
              </div>
            </div>
            {/* Column 2: Place */}
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">
                Place
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {placeList.map((place) => (
                  <button
                    key={`place-${place.value}`}
                    onClick={() => handlePlaceClick(place.value)}
                    className="flex items-center gap-3 px-4 py-3 bg-white rounded-lg border border-gray-200 hover:border-brand-active hover:shadow-sm transition-all group"
                  >
                    <div className="text-gray-400 group-hover:text-brand-active shrink-0">
                      <MapPin className="w-6 h-6" />
                    </div>
                    <span className="text-gray-700 group-hover:text-gray-900 truncate">
                      {place.label}
                    </span>
                    <span className="text-sm text-gray-500 group-hover:text-gray-700 ml-auto shrink-0">
                      {!isLoading ? formatCount(place.count) : ''}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
