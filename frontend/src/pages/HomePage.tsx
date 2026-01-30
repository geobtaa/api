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
import {
  Database,
  Map,
  Globe,
  Library,
  Image,
  Folder,
  Globe2,
  Search,
} from 'lucide-react';
import { fetchSearchResults } from '../services/api';
import { formatCount } from '../utils/formatNumber';

export function HomePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const [resourceCounts, setResourceCounts] = useState<Record<string, number>>(
    {}
  );
  const [isLoading, setIsLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const fetchCounts = async () => {
      try {
        const results = await fetchSearchResults('', 1, 1);
        const resourceClassFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'gbl_resourceClass_sm' ||
              item.id === 'resource_class_agg')
        );

        const facetCounts: Record<string, number> = {};
        const rawItems = (resourceClassFacet as any)?.attributes?.items;

        if (Array.isArray(rawItems)) {
          // New compact encoding: [[value, hits], ...]
          if (rawItems.length > 0 && Array.isArray(rawItems[0])) {
            (rawItems as Array<[string | number, number]>).forEach(([value, hits]) => {
              facetCounts[String(value)] = Number(hits) || 0;
            });
          } else {
            // Legacy encoding: [{ attributes: { value, hits, ... } }, ...]
            (rawItems as Array<any>).forEach((item) => {
              const value = item?.attributes?.value;
              const hits = item?.attributes?.hits;
              if (value !== undefined) {
                facetCounts[String(value)] = Number(hits) || 0;
              }
            });
          }
        }

        setResourceCounts(facetCounts);
      } catch (error) {
        console.error('Error fetching resource counts:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCounts();
  }, []);

  const resourceClasses = [
    {
      id: 'Dataset',
      label: 'Datasets',
      count: resourceCounts['Datasets'] || 0,
      icon: <Database className="w-6 h-6" />,
      aggValue: 'Datasets',
    },
    {
      id: 'Map',
      label: 'Maps',
      count: resourceCounts['Maps'] || 0,
      icon: <Map className="w-6 h-6" />,
      aggValue: 'Maps',
    },
    {
      id: 'Web service',
      label: 'Web Services',
      count: resourceCounts['Web services'] || 0,
      icon: <Globe className="w-6 h-6" />,
      aggValue: 'Web services',
    },
    {
      id: 'Collection',
      label: 'Collections',
      count: resourceCounts['Collections'] || 0,
      icon: <Library className="w-6 h-6" />,
      aggValue: 'Collections',
    },
    {
      id: 'Imagery',
      label: 'Imagery',
      count: resourceCounts['Imagery'] || 0,
      icon: <Image className="w-6 h-6" />,
      aggValue: 'Imagery',
    },
    {
      id: 'Other',
      label: 'Other',
      count: resourceCounts['Other'] || 0,
      icon: <Folder className="w-6 h-6" />,
      aggValue: 'Other',
    },
    {
      id: 'Website',
      label: 'Websites',
      count: resourceCounts['Websites'] || 0,
      icon: <Globe2 className="w-6 h-6" />,
      aggValue: 'Websites',
    },
  ];

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
      `/search?fq[gbl_resourceClass_sm][]=${encodeURIComponent(aggValue)}`
    );
  };

  const handleBrowseAll = () => {
    navigate('/search?q=');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 bg-gray-50 relative min-h-[calc(100vh-4rem)] overflow-hidden">
        {mounted && (
          <Suspense fallback={null}>
            <HomePageHexMapBackground />
          </Suspense>
        )}
        <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[calc(100vh-4rem)] relative z-10">
          <div className="col-span-1 lg:col-span-8 flex flex-col">
            <div className="flex flex-col flex-1 px-4 md:px-8 lg:px-12 py-4 lg:py-4">
              <div className="space-y-6 lg:space-y-2 max-w-3xl bg-white/60 backdrop-blur-sm rounded-lg p-6 lg:p-8 shadow-sm">
              <h1 className="sr-only">
                {theme.institution.name}
              </h1>

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

          <div className="col-span-1 lg:col-span-4 bg-white/60 backdrop-blur-sm px-4 md:px-8 lg:px-12 py-8 lg:py-12 border-t lg:border-l lg:border-t-0 border-gray-200/50">
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Browse by Resource Class
              </h2>
              <div className="space-y-3">
                <button
                  onClick={handleBrowseAll}
                  className="w-full flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:border-brand-active hover:shadow-sm transition-all group"
                >
                  <div className="flex items-center gap-3">
                    <div className="text-gray-400 group-hover:text-brand-active">
                      <Search className="w-6 h-6" />
                    </div>
                    <span className="text-gray-700 group-hover:text-gray-900">
                      Browse All Resources
                    </span>
                  </div>
                </button>

                {resourceClasses.map((resource) => (
                  <button
                    key={resource.id}
                    onClick={() => handleResourceClassClick(resource.aggValue)}
                    className="w-full flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:border-brand-active hover:shadow-sm transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-gray-400 group-hover:text-brand-active">
                        {resource.icon}
                      </div>
                      <span className="text-gray-700 group-hover:text-gray-900">
                        {resource.label}
                      </span>
                    </div>
                    <span className="text-sm text-gray-500 group-hover:text-gray-700">
                      {!isLoading ? formatCount(resource.count) : ''}
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
