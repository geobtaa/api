import { useEffect, useState, Suspense, lazy } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { SearchField } from '../components/SearchField';

const HomePageHexMapBackground = lazy(() =>
  import('../components/home/HomePageHexMapBackground.client').then((m) => ({
    default: m.HomePageHexMapBackground,
  }))
);
import { useTheme } from '../hooks/useTheme';
import { Search } from 'lucide-react';
import { fetchSearchResults } from '../services/api';
import { formatCount } from '../utils/formatNumber';
import { getResourceIcon } from '../utils/resourceIcons';

type ResourceClassItem = { value: string; label: string; count: number };

export function HomePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const [resourceClassList, setResourceClassList] = useState<
    ResourceClassItem[]
  >([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const fetchResourceClasses = async () => {
      try {
        const results = await fetchSearchResults('', 1, 1);
        const resourceClassFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'gbl_resourceClass_sm' ||
              item.id === 'resource_class_agg')
        );

        const rawItems = (resourceClassFacet as any)?.attributes?.items;
        let items: ResourceClassItem[] = [];

        if (Array.isArray(rawItems)) {
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
        }

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
        setResourceClassList(
          otherItem ? [...regularItems, otherItem] : regularItems
        );
      } catch (error) {
        console.error('Error fetching resource classes:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchResourceClasses();
  }, []);

  const handleSearch = (query: string) => {
    if (query.trim()) {
      const newParams = new URLSearchParams();
      newParams.set('q', query);

      // Preserve geo filters from current URL
      const geoType = searchParams.get('include_filters[geo][type]');
      if (geoType === 'bbox') {
        const topLeftLat = searchParams.get(
          'include_filters[geo][top_left][lat]'
        );
        const topLeftLon = searchParams.get(
          'include_filters[geo][top_left][lon]'
        );
        const bottomRightLat = searchParams.get(
          'include_filters[geo][bottom_right][lat]'
        );
        const bottomRightLon = searchParams.get(
          'include_filters[geo][bottom_right][lon]'
        );

        if (topLeftLat && topLeftLon && bottomRightLat && bottomRightLon) {
          newParams.set('include_filters[geo][type]', 'bbox');
          newParams.set('include_filters[geo][field]', 'dcat_bbox');
          newParams.set('include_filters[geo][top_left][lat]', topLeftLat);
          newParams.set('include_filters[geo][top_left][lon]', topLeftLon);
          newParams.set(
            'include_filters[geo][bottom_right][lat]',
            bottomRightLat
          );
          newParams.set(
            'include_filters[geo][bottom_right][lon]',
            bottomRightLon
          );
        }
      }

      // Preserve category filters from current URL (if any)
      const categoryFilters = searchParams.getAll(
        'include_filters[gbl_resourceClass_sm][]'
      );
      const legacyCategoryFilters = searchParams.getAll(
        'fq[gbl_resourceClass_sm][]'
      );

      // Use include_filters format (preferred)
      if (categoryFilters.length > 0) {
        categoryFilters.forEach((value) => {
          newParams.append('include_filters[gbl_resourceClass_sm][]', value);
        });
      } else if (legacyCategoryFilters.length > 0) {
        // Fall back to legacy format if present
        legacyCategoryFilters.forEach((value) => {
          newParams.append('include_filters[gbl_resourceClass_sm][]', value);
        });
      }

      navigate(`/search?${newParams.toString()}`);
    }
  };

  const handleAdvancedSearchClick = () => {
    // Always open advanced search when coming from home page
    navigate('/search?showAdvanced=true');
  };

  const handleResourceClassClick = (aggValue: string) => {
    navigate(
      `/search?include_filters[gbl_resourceClass_sm][]=${encodeURIComponent(aggValue)}`
    );
  };

  const handleBrowseAll = () => {
    navigate('/search?q=');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 bg-gray-50 flex flex-col">
        {/* Map (full viewport minus header) with search form overlaid */}
        <div className="flex-shrink-0 relative h-[calc(100vh-4rem)] overflow-hidden">
          {mounted && (
            <Suspense fallback={null}>
              <HomePageHexMapBackground />
            </Suspense>
          )}
          {/* Search form overlay - pointer-events-none so map receives hover; card has pointer-events-auto. Padding matches Header/Footer grid. */}
          <div className="absolute inset-0 z-10 pointer-events-none px-4 sm:px-6 lg:px-8 py-4 lg:py-4">
            <div className="max-w-3xl space-y-6 lg:space-y-2 bg-white/70 backdrop-blur-sm rounded-lg p-6 lg:p-4 shadow-sm pointer-events-auto">
              <h1 className="sr-only">{theme.institution.name}</h1>
              <p className="text-lg lg:text-xl text-gray-600">
                {theme.institution.hero_text ||
                  'Search geospatial resources from Big Ten Academic Alliance institutions'}
              </p>
              <div className="w-full">
                <SearchField
                  onSearch={handleSearch}
                  placeholder="Search for maps, data, imagery..."
                  autoFocus
                  showAdvancedButton={true}
                  onAdvancedSearchClick={handleAdvancedSearchClick}
                />
              </div>
              <div className="text-sm text-gray-500">
                <p>
                  {theme.institution.hero_description ||
                    'Browse and download GIS data, maps, and other geospatial resources.'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Browse by Resource Class - full width panel below map. Padding matches Header/Footer grid. */}
        <div className="flex-shrink-0 w-full bg-white/80 backdrop-blur-sm border-t border-gray-200 px-4 sm:px-6 lg:px-8 py-6 z-10">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Browse by Resource Class
            </h2>
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
          <div className="grid grid-cols-2 gap-3">
            {resourceClassList.map((resource) => (
              <button
                key={resource.value}
                onClick={() => handleResourceClassClick(resource.value)}
                className="flex items-center gap-3 px-4 py-3 bg-white rounded-lg border border-gray-200 hover:border-brand-active hover:shadow-sm transition-all group"
              >
                <div className="text-gray-400 group-hover:text-brand-active">
                  {getResourceIcon(resource.value, {
                    className: 'w-6 h-6 text-gray-400',
                  })}
                </div>
                <span className="text-gray-700 group-hover:text-gray-900">
                  {resource.label}
                </span>
                <span className="text-sm text-gray-500 group-hover:text-gray-700 ml-auto">
                  {!isLoading ? formatCount(resource.count) : ''}
                </span>
              </button>
            ))}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
